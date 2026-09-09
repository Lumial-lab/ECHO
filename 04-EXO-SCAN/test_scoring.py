#!/usr/bin/env python3
"""Тести рушія оцінки EXO Scan — правила D0-D4 з брифу.

Кожен тест перевіряє КОНКРЕТНЕ правило з брифу Аетрема:
- D0-D1 → тег DIGITAL_FOUNDATION_REQUIRED (не пропонувати повний EXO)
- D2+ → можна пропонувати перший EXO-контур
- Однакові відповіді → однаковий результат (детермінованість)
- Вісь з недостатньою кількістю відповідей → ⚪, не вигаданий бал
"""
import sys
sys.path.insert(0, "C:/ЕХО/04-EXO-SCAN")

from scoring_engine import score, AxisScore, _check_condition


# ── Мінімальна тестова конфігурація ──────────────────────────
# НЕ методологія — тільки структура для перевірки рушія.

MINI_CONFIG = {
    "scoring_version": "0.0.1-test",
    "axes": [
        {"id": "operations", "label": "Операції", "description": "S1", "min_questions_for_score": 2},
        {"id": "coordination", "label": "Координація", "description": "S2", "min_questions_for_score": 1},
    ],
    "digital_substrate_levels": [
        {"level": 0, "code": "D0", "label": "Analog", "description": "Паперові"},
        {"level": 1, "code": "D1", "label": "Scanned", "description": "Скани"},
        {"level": 2, "code": "D2", "label": "Digital", "description": "Цифрові"},
        {"level": 3, "code": "D3", "label": "Managed", "description": "СЕД"},
        {"level": 4, "code": "D4", "label": "Connected", "description": "API"},
    ],
    "screens": [
        {
            "id": "profile",
            "title": "Профіль",
            "questions": [
                {
                    "id": "doc_digital_share",
                    "type": "single_choice",
                    "text": "Частка електронного документообігу?",
                    "options": [
                        {"value": "lt25", "label": "<25%"},
                        {"value": "25_50", "label": "25-50%"},
                        {"value": "50_75", "label": "50-75%"},
                        {"value": "gt75", "label": ">75%"},
                        {"value": "full", "label": "~100%"},
                    ],
                    "scoring_rules": [
                        {
                            "axis_id": "operations",
                            "points": {"lt25": 0, "25_50": 1, "50_75": 2, "gt75": 3, "full": 4},
                            "weight": 1.0,
                            "tags": [],
                        }
                    ],
                    "digital_substrate_rule": {
                        "points": {"lt25": 0, "25_50": 1, "50_75": 2, "gt75": 3, "full": 4},
                        "weight": 2.0,
                    },
                },
                {
                    "id": "doc_meaning",
                    "type": "single_choice",
                    "text": "Що означає 'електронний документ'?",
                    "options": [
                        {"value": "scan", "label": "Скан/PDF"},
                        {"value": "structured", "label": "Структурований файл"},
                        {"value": "sed", "label": "СЕД"},
                        {"value": "workflow", "label": "Workflow"},
                    ],
                    "scoring_rules": [
                        {
                            "axis_id": "operations",
                            "points": {"scan": 1, "structured": 2, "sed": 3, "workflow": 4},
                            "weight": 1.0,
                        }
                    ],
                    "digital_substrate_rule": {
                        "points": {"scan": 1, "structured": 2, "sed": 3, "workflow": 4},
                        "weight": 1.0,
                    },
                },
                {
                    "id": "task_control",
                    "type": "single_choice",
                    "text": "Як контролюються задачі?",
                    "options": [
                        {"value": "none", "label": "Ніяк"},
                        {"value": "manual", "label": "Вручну"},
                        {"value": "system", "label": "У системі"},
                    ],
                    "scoring_rules": [
                        {
                            "axis_id": "coordination",
                            "points": {"none": 0, "manual": 2, "system": 4},
                            "weight": 1.0,
                        }
                    ],
                },
            ],
        },
        {
            "id": "advanced",
            "title": "Інтеграції",
            "show_if": {"question_id": "doc_digital_share", "op": "in", "value": ["50_75", "gt75", "full"]},
            "questions": [
                {
                    "id": "api_available",
                    "type": "single_choice",
                    "text": "Чи є API?",
                    "options": [
                        {"value": "yes", "label": "Так"},
                        {"value": "no", "label": "Ні"},
                    ],
                    "scoring_rules": [
                        {
                            "axis_id": "coordination",
                            "points": {"yes": 4, "no": 1},
                            "weight": 0.5,
                        }
                    ],
                },
            ],
        },
    ],
}


def test_d0_d1_requires_foundation():
    """Правило брифу: D0-D1 → тег DIGITAL_FOUNDATION_REQUIRED."""
    # D0: усе паперове
    answers = {"doc_digital_share": "lt25", "doc_meaning": "scan", "task_control": "manual"}
    result = score(MINI_CONFIG, answers)
    assert result.digital_substrate_level <= 1, f"Expected D0 or D1, got D{result.digital_substrate_level}"
    assert "DIGITAL_FOUNDATION_REQUIRED" in result.tags, "Missing DIGITAL_FOUNDATION_REQUIRED tag"
    print("  PASS: D0-D1 → DIGITAL_FOUNDATION_REQUIRED")


def test_d2_plus_no_foundation_tag():
    """Правило брифу: D2+ → можна пропонувати EXO (немає тегу блоку)."""
    answers = {"doc_digital_share": "gt75", "doc_meaning": "sed", "task_control": "system"}
    result = score(MINI_CONFIG, answers)
    assert result.digital_substrate_level >= 2, f"Expected D2+, got D{result.digital_substrate_level}"
    assert "DIGITAL_FOUNDATION_REQUIRED" not in result.tags, "D2+ should not have DIGITAL_FOUNDATION_REQUIRED"
    print("  PASS: D2+ → без тегу DIGITAL_FOUNDATION_REQUIRED")


def test_deterministic():
    """Критична вимога: однакові відповіді → однаковий результат."""
    answers = {"doc_digital_share": "50_75", "doc_meaning": "structured", "task_control": "system"}
    r1 = score(MINI_CONFIG, answers)
    r2 = score(MINI_CONFIG, answers)
    for ax_id in r1.axes:
        assert r1.axes[ax_id].normalized == r2.axes[ax_id].normalized, \
            f"Non-deterministic on axis {ax_id}"
    assert r1.digital_substrate_level == r2.digital_substrate_level
    assert r1.tags == r2.tags
    print("  PASS: детермінованість")


def test_insufficient_data_shows_unknown():
    """Вісь з < min_questions відповідей → ⚪, не вигаданий бал."""
    # operations потребує 2 відповіді, даємо тільки 1
    answers = {"doc_digital_share": "gt75", "task_control": "system"}
    result = score(MINI_CONFIG, answers)
    ops = result.axes["operations"]
    assert ops.question_count < ops.min_questions, "Should have insufficient data"
    assert ops.normalized is None, "Should return None for insufficient data"
    assert ops.status == "⚪", "Status should be ⚪"
    print("  PASS: недостатньо даних → ⚪")


def test_branching_skips_screen():
    """Branching: якщо документообіг <25%, екран 'advanced' не показується."""
    answers = {"doc_digital_share": "lt25", "doc_meaning": "scan", "task_control": "none",
               "api_available": "yes"}  # відповідь є, але екран прихований
    result = score(MINI_CONFIG, answers)
    # coordination має тільки task_control (з основного екрану), не api_available
    coord = result.axes["coordination"]
    assert coord.question_count == 1, f"Expected 1 question for coordination, got {coord.question_count}"
    print("  PASS: branching ховає екран")


def test_condition_logic():
    """Перевірка логічних операторів умов."""
    answers = {"a": "x", "b": 5}

    assert _check_condition(None, answers) is True, "None → True"
    assert _check_condition({"question_id": "a", "op": "eq", "value": "x"}, answers)
    assert not _check_condition({"question_id": "a", "op": "neq", "value": "x"}, answers)
    assert _check_condition({"question_id": "b", "op": "gt", "value": 3}, answers)
    assert _check_condition({"question_id": "a", "op": "in", "value": ["x", "y"]}, answers)
    assert _check_condition(
        {"and": [
            {"question_id": "a", "op": "eq", "value": "x"},
            {"question_id": "b", "op": "gt", "value": 3},
        ]},
        answers,
    )
    assert _check_condition(
        {"not": {"question_id": "a", "op": "eq", "value": "z"}},
        answers,
    )
    # Missing answer → condition fails
    assert not _check_condition({"question_id": "missing", "op": "eq", "value": "x"}, answers)
    print("  PASS: логіка умов")


def test_multi_choice_scoring():
    """Multi-choice: бали рахуються як сума по обраних варіантах."""
    config = {
        "scoring_version": "0.0.1-test",
        "axes": [{"id": "systems", "label": "Системи", "description": "test", "min_questions_for_score": 1}],
        "digital_substrate_levels": [],
        "screens": [{
            "id": "sys",
            "title": "Системи",
            "questions": [{
                "id": "systems_used",
                "type": "multi_choice",
                "text": "Які системи?",
                "options": [
                    {"value": "crm", "label": "CRM"},
                    {"value": "sed", "label": "СЕД"},
                    {"value": "erp", "label": "ERP"},
                ],
                "scoring_rules": [{
                    "axis_id": "systems",
                    "points": {"crm": 1, "sed": 2, "erp": 2},
                    "weight": 1.0,
                }],
            }],
        }],
    }
    answers = {"systems_used": ["crm", "erp"]}
    result = score(config, answers)
    ax = result.axes["systems"]
    # crm=1 + erp=2 = 3, weight=1.0, total_weight=4.0, normalized=3/4=0.75
    assert ax.raw_points == 3.0, f"Expected 3.0, got {ax.raw_points}"
    print("  PASS: multi_choice сума")


def test_partial_completion_saved():
    """Часткове проходження: результат створюється навіть без усіх відповідей."""
    answers = {"doc_digital_share": "50_75"}  # тільки 1 відповідь з ~4
    result = score(MINI_CONFIG, answers)
    assert result.answers_count == 1
    assert result.scoring_version == "0.0.1-test"
    print("  PASS: часткове проходження")


# ── Запуск ───────────────────────────────────────────────────

if __name__ == "__main__":
    tests = [
        test_d0_d1_requires_foundation,
        test_d2_plus_no_foundation_tag,
        test_deterministic,
        test_insufficient_data_shows_unknown,
        test_branching_skips_screen,
        test_condition_logic,
        test_multi_choice_scoring,
        test_partial_completion_saved,
    ]
    passed = 0
    failed = 0
    for t in tests:
        try:
            t()
            passed += 1
        except AssertionError as e:
            print(f"  FAIL: {t.__name__} — {e}")
            failed += 1
        except Exception as e:
            print(f"  ERROR: {t.__name__} — {type(e).__name__}: {e}")
            failed += 1

    print(f"\n{'='*40}")
    print(f"Результат: {passed}/{passed+failed} тестів пройшли")
    if failed:
        sys.exit(1)
    print("Рушій оцінки працює правильно.")
