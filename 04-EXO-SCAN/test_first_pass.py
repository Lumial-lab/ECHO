"""Acceptance boundaries for the draft, not evidence of commercial efficacy."""
import copy
import json
from pathlib import Path

import jsonschema
import pytest

from first_pass import build_report
from scoring_engine import score, visible_questions
from test_scoring import MINI_CONFIG

ROOT = Path(__file__).resolve().parent
CONFIG = json.loads((ROOT / "questions.json").read_text(encoding="utf-8"))


def example(name):
    return json.loads((ROOT / "examples" / f"{name}.json").read_text(encoding="utf-8"))


def refs(condition):
    if not condition:
        return set()
    if "question_id" in condition:
        return {condition["question_id"]}
    return set().union(*(refs(c) for k in ("and", "or") for c in condition.get(k, [])),
                       refs(condition.get("not")))


def test_catalog_schema_and_forward_routes():
    schema = json.loads((ROOT / "questions_schema.json").read_text(encoding="utf-8"))
    jsonschema.Draft202012Validator.check_schema(schema)
    jsonschema.validate(CONFIG, schema)
    known = set()
    axis_ids = {a["id"] for a in CONFIG["axes"]}
    assert len(axis_ids) == 8
    for screen in CONFIG["screens"]:
        assert refs(screen.get("show_if")) <= known
        for q in screen["questions"]:
            assert q["id"] not in known
            assert refs(q.get("show_if")) <= known
            known.add(q["id"])
            assert q["type"] in ("single_choice", "multi_choice")
            assert "default" not in q
            values = [o["value"] for o in q["options"]]
            assert len(values) == len(set(values))
            assert {"unknown", "other"} <= set(values)
            for rule in q.get("scoring_rules", []):
                assert rule["axis_id"] in axis_ids
                assert refs(rule.get("condition")) <= known
    assert CONFIG["methodology_status"] == "DRAFT_FOR_CALIBRATION"


def test_maximum_scores_are_four_not_one():
    result = score(MINI_CONFIG, {"doc_digital_share":"full", "doc_meaning":"workflow",
                                 "task_control":"system", "api_available":"yes"})
    assert all(a.normalized == 4.0 for a in result.axes.values())


def test_weighted_mean_keeps_zero_to_four_scale():
    result = score(MINI_CONFIG, {"task_control":"none", "doc_digital_share":"full", "api_available":"yes"})
    assert result.axes["coordination"].normalized == pytest.approx(4 * .5 / 1.5)


def test_empty_does_not_mean_low_readiness():
    result = score(CONFIG, {})
    assert result.digital_substrate_level is None
    assert result.digital_substrate_code == "UNKNOWN"
    assert "DIGITAL_FOUNDATION_REQUIRED" not in result.tags
    assert all(a.normalized is None for a in result.axes.values())
    report = build_report(CONFIG, {})
    assert not report["contact_required"]
    assert len(report["configurations"]) == 3


@pytest.mark.parametrize("value", ["unknown", "other", "na"])
def test_unknown_own_and_not_applicable_are_not_zero(value):
    result = score(CONFIG, {"priority_process":"documents", "process_data":value})
    assert result.digital_substrate_level is None
    assert result.axes["digital"].normalized is None


def test_unique_question_not_rule_count():
    config = copy.deepcopy(MINI_CONFIG)
    question = config["screens"][0]["questions"][0]
    question["scoring_rules"].append(copy.deepcopy(question["scoring_rules"][0]))
    result = score(config, {"doc_digital_share":"full"})
    assert result.axes["operations"].question_count == 1
    assert result.axes["operations"].normalized is None


def test_changing_route_discards_hidden_scores_comments_and_counts():
    answers = example("large_paper")
    answers["priority_process"] = "unknown"
    answers["_comments"] = {"process_data":"Old hidden note"}
    result = score(CONFIG, answers)
    assert result.digital_substrate_level is None
    assert result.consultation_topics == []
    _, active = visible_questions(CONFIG, answers)
    assert "process_data" not in active
    assert result.answers_count == len(active)
    assert result.answers_count <= result.total_questions


def test_hidden_answer_cannot_open_descendant():
    config = copy.deepcopy(MINI_CONFIG)
    config["screens"].append({"id":"child", "show_if":{"question_id":"api_available","op":"eq","value":"yes"},
                              "questions":[{"id":"child", "type":"text", "text":"Hidden descendant"}]})
    questions, active = visible_questions(config, {"doc_digital_share":"lt25", "api_available":"yes", "child":"old"})
    assert "api_available" not in active
    assert "child" not in {q["id"] for q in questions}


@pytest.mark.parametrize("qid,value", [
    ("goal", "fabricated"), ("team_size", 9), ("customers", "people"),
    ("customers", ["people", "people"]), ("customers", ["people", "unknown"]),
    ("external_topics", ["none", "law"]), ("external_topics", ["law", ["market"]])])
def test_invalid_answers_fail_explicitly(qid, value):
    with pytest.raises(ValueError, match="Invalid answer"):
        score(CONFIG, {qid:value})


def test_unmapped_valid_choice_is_missing_evidence():
    config = copy.deepcopy(MINI_CONFIG)
    config["screens"][0]["questions"][2]["options"].append({"value":"unknown", "label":"Unknown"})
    result = score(config, {"task_control":"unknown"})
    assert result.axes["coordination"].normalized is None


def test_comments_preserve_standard_score_without_invented_text_score():
    answers = {"process_visibility":"owned", "_comments":{"process_visibility":"Особлива потреба"}}
    result = score(CONFIG, answers)
    assert result.axes["process"].normalized == 3
    assert result.consultation_topics[0]["text"] == "Особлива потреба"
    answers["process_visibility"] = "other"
    assert score(CONFIG, answers).axes["process"].normalized is None


def test_other_without_text_never_blocks_result():
    result = score(CONFIG, {"goal":"other"})
    assert result.consultation_topics[0]["text"] == ""
    assert result.answers_count == 1


def test_unknown_extra_keys_are_not_answers():
    result = score(CONFIG, {"rogue":"ignored", "_comments":{"rogue":"not a question"}})
    assert result.answers_count == 0
    assert not result.consultation_topics


def test_other_in_multi_choice_does_not_erase_standard_score():
    config = copy.deepcopy(MINI_CONFIG)
    q = config["screens"][0]["questions"][2]
    q["type"] = "multi_choice"
    q["options"].append({"value":"other", "label":"Other", "non_scoring":True})
    result = score(config, {"task_control":["system", "other"]})
    assert result.axes["coordination"].normalized == 4


def test_multi_choice_points_are_bounded_before_aggregation():
    config = copy.deepcopy(MINI_CONFIG)
    q = config["screens"][0]["questions"][2]
    q["type"] = "multi_choice"
    result = score(config, {"task_control":["manual", "system"]})
    assert result.axes["coordination"].raw_points == 4


@pytest.mark.parametrize("value", [True, float("nan"), float("inf"), -1, 101, "7"])
def test_number_validation_rejects_invalid_values(value):
    config = {"screens":[{"questions":[{"id":"n","type":"number","minimum":0,"maximum":100}]}]}
    with pytest.raises(ValueError):
        visible_questions(config, {"n":value})


@pytest.mark.parametrize("name,code,pilot", [
    ("small_digital", "D4", "Пошук відповідей"),
    ("large_paper", "D0", "Підготовка даних"),
    ("fragmented_trade", "D2", "Чернетки відповідей")])
def test_three_businesses(name, code, pilot):
    answers = example(name)
    untouched = copy.deepcopy(answers)
    report = build_report(CONFIG, answers)
    assert report == build_report(CONFIG, answers)
    assert answers == untouched
    assert report["process_data_level"] == code
    assert report["pilot"]["label"].startswith(pilot)
    assert len(report["configurations"]) == 3
    assert report["coverage"]["answered"] == report["coverage"]["visible"]
    assert not report["automatic_contact_or_booking"]
    assert "Самооцінка" in report["basis"]


def test_size_sector_site_do_not_inflate_readiness():
    base = example("small_digital")
    changed = {**base, "team_size":"enterprise", "sector":"mixed", "website":"no_site"}
    a, b = build_report(CONFIG, base), build_report(CONFIG, changed)
    assert a["axes"] == b["axes"]
    assert a["process_data_level"] == b["process_data_level"]
    assert a["configurations"] == b["configurations"]


def test_fragments_need_curated_answers_and_keep_consultation_topic():
    report = build_report(CONFIG, example("fragmented_trade"))
    assert any("базу відповідей" in s for s in report["preparation"])
    assert len(report["consultation_topics"]) == 1


def test_invalid_comments_rejected():
    with pytest.raises(ValueError, match="Invalid comment"):
        score(CONFIG, {"_comments":{"goal":"x" * 1001}})
    with pytest.raises(ValueError, match="Invalid comments"):
        score(CONFIG, {"_comments":"not a dictionary"})
