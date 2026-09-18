"""Local, deterministic diagnostic draft. No network, model or lead submission."""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from scoring_engine import score, visible_questions

ROOT = Path(__file__).resolve().parent


def build_report(config: dict, answers: dict) -> dict:
    result = score(config, answers)
    questions, active = visible_questions(config, answers)
    labels = {q["id"]: {o["value"]: o["label"] for o in q.get("options", [])} for q in questions}
    process = active.get("priority_process")
    route = config["pilot_routes"].get(process)
    steps = []
    if result.digital_substrate_level is None:
        steps.append("Уточнити стан даних обраного процесу; невідоме не означає низьку готовність.")
    elif result.digital_substrate_level <= 1:
        steps.append("Почати з підготовки невеликої вибірки даних і перевірки її якості, а не з повного впровадження.")
    elif result.digital_substrate_level == 2:
        steps.append("Узгодити джерело актуальних даних, версії та спосіб обміну.")
    else:
        steps.append("Перевірити доступність даних і почати обмежений пілот у наявній системі.")
    if route:
        steps.append(route["prerequisite"])
    if active.get("process_owner") != "ready":
        steps.append("Визначити фахівця та реальний час для перевірки результатів пілота.")
    steps.append("Уточнити допустимі дані, права доступу та межі автоматичних дій до інтеграції.")
    if process == "customer_service" and active.get("approved_answers") != "yes":
        steps.append("Спочатку підготувати й погодити базу відповідей; зовнішні відповіді залишити під перевіркою людини.")

    return {
        "scoring_version": result.scoring_version,
        "methodology_status": config["methodology_status"],
        "basis": "Самооцінка респондента. Документи, сайт і фактичні процеси не перевірені.",
        "scope": "Перший пріоритетний процес і попередній огляд, не повний аудит підприємства.",
        "profile": {qid: labels[qid].get(active.get(qid), "Не визначено")
                    for qid in ("goal", "sector", "team_size")},
        "axes": {key: {"label": axis.label, "score": axis.normalized,
                       "evidence_questions": axis.question_count,
                       "interpretation": "Недостатньо даних" if axis.normalized is None else "Попередня оцінка за відповідями"}
                 for key, axis in result.axes.items()},
        "process_data_level": result.digital_substrate_code,
        "coverage": {"answered": result.answers_count, "visible": result.total_questions},
        "pilot": route or {"label": "Спочатку визначити один процес для пілота",
                           "metric": "Погодити результат і спосіб його вимірювання"},
        "sector_examples": config["sector_examples"].get(active.get("sector"), config["sector_examples"]["other"]),
        "workload": labels.get("monthly_hours", {}).get(active.get("monthly_hours"), "Не визначено"),
        "preparation": steps,
        "success_check": "Порівняти однакові типові завдання до і після пілота: час, якість, вартість та навантаження перевірки. Цілі погодити після вимірювання вихідного стану.",
        "configurations": [
            {"name":"Фокусна","scope":"Один процес, необхідна підготовка, пілот і вимірювання ефекту."},
            {"name":"Пов'язана","scope":"Кілька суміжних процесів, узгоджені дані та відповідальні; після перевірки першого пілота."},
            {"name":"Системна","scope":"Поетапний ЕХО: база знань, аналітика та супровід. Передумови перевіряються на кожному етапі."}
        ],
        "pricing": "Вартість визначається після уточнення обсягу, даних, інтеграцій та участі команди. Розмір компанії сам по собі не визначає пакет.",
        "consultation_topics": result.consultation_topics,
        "contact_required": False,
        "automatic_contact_or_booking": False,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Local EXO diagnostic draft")
    parser.add_argument("answers", type=Path)
    args = parser.parse_args()
    config = json.loads((ROOT / "questions.json").read_text(encoding="utf-8"))
    answers = json.loads(args.answers.read_text(encoding="utf-8"))
    print(json.dumps(build_report(config, answers), ensure_ascii=False, indent=2, allow_nan=False))


if __name__ == "__main__":
    main()
