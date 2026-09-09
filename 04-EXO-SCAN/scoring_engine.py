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
    digital_substrate_level: int  # 0-4
    digital_substrate_code: str   # D0-D4
    tags: list[str]               # зібрані теги рекомендацій
    answers_count: int
    total_questions: int


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
    return ops.get(op, lambda a, e: False)(actual, expected)


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
    total_questions = 0

    # Обхід екранів і питань
    for screen in config["screens"]:
        if not _check_condition(screen.get("show_if"), answers):
            continue

        for q in screen["questions"]:
            total_questions += 1
            if not _check_condition(q.get("show_if"), answers):
                continue

            answer = answers.get(q["id"])
            if answer is None:
                continue

            # Scoring rules → axes
            for rule in q.get("scoring_rules", []):
                if not _check_condition(rule.get("condition"), answers):
                    continue

                axis_id = rule["axis_id"]
                if axis_id not in axes:
                    continue

                weight = rule.get("weight", 1.0)
                points_spec = rule["points"]

                if isinstance(points_spec, dict):
                    # mapping: answer_value → points
                    key = str(answer) if not isinstance(answer, list) else None
                    if key and key in points_spec:
                        pts = points_spec[key] * weight
                    elif isinstance(answer, list):
                        # multi_choice: сума по обраних
                        pts = sum(points_spec.get(str(v), 0) for v in answer) * weight
                    else:
                        pts = 0
                else:
                    pts = float(points_spec) * weight

                axes[axis_id].raw_points += pts
                axes[axis_id].total_weight += weight * 4.0  # нормалізація до 0-4
                axes[axis_id].question_count += 1

                all_tags.extend(rule.get("tags", []))

            # Digital substrate rule
            ds_rule = q.get("digital_substrate_rule")
            if ds_rule:
                ds_w = ds_rule.get("weight", 1.0)
                ds_pts = ds_rule["points"]
                if isinstance(ds_pts, dict):
                    key = str(answer) if not isinstance(answer, list) else None
                    if key and key in ds_pts:
                        ds_points += ds_pts[key] * ds_w
                        ds_weight += ds_w
                else:
                    ds_points += float(ds_pts) * ds_w
                    ds_weight += ds_w

    # Digital Substrate Level
    if ds_weight > 0:
        ds_raw = ds_points / ds_weight
    else:
        ds_raw = 0

    # Округлення до найближчого рівня D0-D4
    ds_level = max(0, min(4, round(ds_raw)))
    ds_code = f"D{ds_level}"

    # Правило з брифу: D0-D1 → тег DIGITAL_FOUNDATION_REQUIRED
    if ds_level <= 1:
        all_tags.append("DIGITAL_FOUNDATION_REQUIRED")

    return ScanResult(
        scoring_version=scoring_version,
        axes=axes,
        digital_substrate_level=ds_level,
        digital_substrate_code=ds_code,
        tags=sorted(set(all_tags)),
        answers_count=len(answers),
        total_questions=total_questions,
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
