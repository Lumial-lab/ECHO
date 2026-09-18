#!/usr/bin/env python3
"""EXO Scan — детермінований рушій оцінки v0.1

Однакові відповіді → однаковий результат. Завжди. Без LLM.

Правила (ваги, пороги, питання) зчитуються з questions.json —
методологія Люміаль і Аетрема, код не вигадує нічого.

Використання:
    from scoring_engine import score
    result = score(questions_config, answers)
"""
from __future__ import annotations
import json
import math
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


# ── Типи ────────────────────────────────────────────────────

@dataclass
class AxisScore:
    """Бал по одній вісі радару."""
    axis_id: str
    label: str
    raw_points: float = 0.0
    total_weight: float = 0.0
    question_count: int = 0
    min_questions: int = 1
    tags: list[str] = field(default_factory=list)

    @property
    def has_enough_data(self) -> bool:
        return self.question_count >= self.min_questions

    @property
    def normalized(self) -> float | None:
        """Бал 0-4 (шкала з брифу). None якщо недостатньо даних."""
        if not self.has_enough_data or self.total_weight == 0:
            return None
        raw = self.raw_points / self.total_weight
        return max(0.0, min(4.0, raw))

    @property
    def status(self) -> str:
        """⚪ недостатньо даних / 🔴 0-1 / 🟡 2 / 🟢 3-4."""
        n = self.normalized
        if n is None:
            return "⚪"
        if n < 1.5:
            return "🔴"
        if n < 2.5:
            return "🟡"
        return "🟢"


@dataclass
class ScanResult:
    """Повний результат сканування."""
    scoring_version: str
    axes: dict[str, AxisScore]
    digital_substrate_level: int | None  # None means not measured
    digital_substrate_code: str   # D0-D4 or UNKNOWN
    tags: list[str]               # зібрані теги рекомендацій
    answers_count: int
    total_questions: int
    consultation_topics: list[dict[str, str]] = field(default_factory=list)


# ── Перевірка умов (branching / gating) ──────────────────────

def _check_condition(condition: dict | None, answers: dict[str, Any]) -> bool:
    """Перевіряє умову show_if / gating condition."""
    if condition is None:
        return True

    if "and" in condition:
        return all(_check_condition(c, answers) for c in condition["and"])
    if "or" in condition:
        return any(_check_condition(c, answers) for c in condition["or"])
    if "not" in condition:
        return not _check_condition(condition["not"], answers)

    qid = condition["question_id"]
    op = condition["op"]
    expected = condition["value"]
    actual = answers.get(qid)

    if actual is None:
        return False

    ops = {
        "eq": lambda a, e: a == e,
        "neq": lambda a, e: a != e,
        "gt": lambda a, e: a > e,
        "gte": lambda a, e: a >= e,
        "lt": lambda a, e: a < e,
        "lte": lambda a, e: a <= e,
        "in": lambda a, e: a in e,
        "not_in": lambda a, e: a not in e,
        "contains": lambda a, e: e in a if isinstance(a, (list, str)) else False,
    }
    try:
        return ops.get(op, lambda a, e: False)(actual, expected)
    except (TypeError, ValueError):
        return False


def visible_questions(config: dict, answers: dict[str, Any]) -> tuple[list[dict], dict]:
    """Resolve forward-only branches using validated, visible answers only."""
    visible, active = [], {}
    for screen in config["screens"]:
        if not _check_condition(screen.get("show_if"), active):
            continue
        for question in screen["questions"]:
            if not _check_condition(question.get("show_if"), active):
                continue
            visible.append(question)
            value = answers.get(question["id"])
            if value is None or value == "" or value == []:
                continue
            _validate_answer(question, value)
            active[question["id"]] = value
    return visible, active


def _validate_answer(question: dict, value: Any) -> None:
    kind = question["type"]
    valid = True
    if kind in ("single_choice", "multi_choice"):
        options = {option["value"]: option for option in question.get("options", [])}
        values = value if kind == "multi_choice" else [value]
        valid = isinstance(values, list) and all(isinstance(v, str) and v in options for v in values)
        if valid:
            valid = len(values) == len(set(values))
            valid = valid and not (len(values) > 1 and any(options[v].get("exclusive") for v in values))
    elif kind in ("number", "scale"):
        valid = not isinstance(value, bool) and isinstance(value, (int, float)) and math.isfinite(value)
        if valid:
            valid = question.get("minimum", -math.inf) <= value <= question.get("maximum", math.inf)
    elif kind == "text":
        valid = isinstance(value, str) and len(value) <= question.get("max_length", 1000)
    if not valid:
        raise ValueError(f"Invalid answer: {question['id']}")


def _points(spec: float | dict, answer: Any, question: dict) -> float | None:
    excluded = {o["value"] for o in question.get("options", []) if o.get("non_scoring")}
    values = answer if isinstance(answer, list) else [answer]
    values = [v for v in values if v not in excluded]
    if not values:
        return None
    if isinstance(spec, dict):
        mapped = [spec[str(v)] for v in values if str(v) in spec]
        if not mapped:
            return None
        return max(0.0, min(4.0, sum(mapped)))
    return max(0.0, min(4.0, float(spec)))


# ── Основний рушій ───────────────────────────────────────────

def score(config: dict, answers: dict[str, Any]) -> ScanResult:
    """Детерміновано оцінює відповіді за конфігурацією.

    Args:
        config: вміст questions.json (відповідає questions_schema.json)
        answers: словник {question_id: відповідь}

    Returns:
        ScanResult з балами по вісях, рівнем D і тегами
    """
    scoring_version = config["scoring_version"]

    # Ініціалізація осей
    axes: dict[str, AxisScore] = {}
    for axis_def in config["axes"]:
        axes[axis_def["id"]] = AxisScore(
            axis_id=axis_def["id"],
            label=axis_def["label"],
            min_questions=axis_def.get("min_questions_for_score", 1),
        )

    # Digital substrate accumulator
    ds_points = 0.0
    ds_weight = 0.0

    all_tags: list[str] = []
    questions, active = visible_questions(config, answers)
    counted: dict[str, set[str]] = {axis: set() for axis in axes}
    topics = []
    comments = answers.get("_comments", {})
    if not isinstance(comments, dict):
        raise ValueError("Invalid comments")
    for q in questions:
        answer = active.get(q["id"])
        comment = comments.get(q["id"], "")
        if not isinstance(comment, str) or len(comment) > 1000:
            raise ValueError(f"Invalid comment: {q['id']}")
        other = answer == "other" or isinstance(answer, list) and "other" in answer
        if comment.strip() or other:
            topics.append({"question_id": q["id"], "question": q["text"], "text": comment.strip(),
                           "status": "INDIVIDUAL_CONSULTATION_TOPIC"})
        if answer is None:
            continue
        for rule in q.get("scoring_rules", []):
            if not _check_condition(rule.get("condition"), active):
                continue
            axis_id, weight = rule["axis_id"], rule.get("weight", 1.0)
            if axis_id not in axes or weight <= 0:
                continue
            points = _points(rule["points"], answer, q)
            if points is None:
                continue
            axes[axis_id].raw_points += points * weight
            axes[axis_id].total_weight += weight
            counted[axis_id].add(q["id"])
            all_tags.extend(rule.get("tags", []))
        ds_rule = q.get("digital_substrate_rule")
        if ds_rule:
            weight = ds_rule.get("weight", 1.0)
            points = _points(ds_rule["points"], answer, q)
            if points is not None and weight > 0:
                ds_points += points * weight
                ds_weight += weight

    for axis_id, ids in counted.items():
        axes[axis_id].question_count = len(ids)
    ds_level = max(0, min(4, round(ds_points / ds_weight))) if ds_weight else None
    ds_code = f"D{ds_level}" if ds_level is not None else "UNKNOWN"

    # Правило з брифу: D0-D1 → тег DIGITAL_FOUNDATION_REQUIRED
    if ds_level is not None and ds_level <= 1:
        all_tags.append("DIGITAL_FOUNDATION_REQUIRED")

    return ScanResult(
        scoring_version=scoring_version,
        axes=axes,
        digital_substrate_level=ds_level,
        digital_substrate_code=ds_code,
        tags=sorted(set(all_tags)),
        answers_count=len(active),
        total_questions=len(questions),
        consultation_topics=topics,
    )


def score_from_files(config_path: str | Path, answers_path: str | Path) -> ScanResult:
    """Зручна обгортка: зчитує JSON-файли і оцінює."""
    config = json.loads(Path(config_path).read_text(encoding="utf-8"))
    answers = json.loads(Path(answers_path).read_text(encoding="utf-8"))
    return score(config, answers)


# ── CLI ──────────────────────────────────────────────────────

if __name__ == "__main__":
    import sys
    if len(sys.argv) < 3:
        print("Використання: python scoring_engine.py questions.json answers.json")
        sys.exit(1)
    result = score_from_files(sys.argv[1], sys.argv[2])
    print(f"Версія методики: {result.scoring_version}")
    print(f"Digital Substrate: {result.digital_substrate_code}")
    print(f"Відповідей: {result.answers_count}/{result.total_questions}")
    print()
    for ax in result.axes.values():
        n = ax.normalized
        score_str = f"{n:.1f}/4" if n is not None else "⚪ недостатньо даних"
        print(f"  {ax.status} {ax.label}: {score_str} ({ax.question_count} відп.)")
    if result.tags:
        print(f"\nТеги: {', '.join(result.tags)}")
