#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""РІЙ КЛАВРА — робітник 24/7 (v0.1, Д181 ніч, W1 з mx-lab DAG).

Несубʼєктне крило лабораторії за «Протоколом Ферма» §7:
бере ready-вузли з тегом [auto] зі спільного DAG → жене через дешеві
моделі (klavr_llm: DeepSeek/Groq/локальні; БЕЗ Qwen — межа Ейдена) →
пише артефакт + подію candidate_done. НЕ ставить done НІКОЛИ:
рішення про прийняття — ворота субʼєкта (Клавра).

Інваріанти:
  · токени Клавра не палить (жодного claude -p — правило parallel_instances);
  · бюджет-стеля: MAX_PER_RUN за прохід, MAX_PER_DAY за добу (state-файл);
  · журнал append-only; kill-mid-write безпечний (артефакт atomic-tmp);
  · чужі in_progress не чіпає; вузли БЕЗ тегу [auto] не чіпає.

Запуск (Task Scheduler, кожні 30-60 хв):
  python C:/ЕХО/03-ПРОТОКОЛИ/roy_worker.py --dag mx-lab --once
Розмітка вузла для Рою (у desc):
  [auto]          — LLM-задача: дослідити/сформулювати/перевірити текстом
  [auto:off]      — явно заборонити Рою (пріоритет над [auto])
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import tempfile
import time
from datetime import datetime, date
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
sys.path.insert(0, r"C:/Клавр/hooks")

import syntonia_dag  # noqa: E402  (спільний граф — джерело стану)

ARTIFACTS = HERE / "artifacts"
STATE_DIR = Path(r"C:/Клавр/hooks/state")
BUDGET_F = STATE_DIR / "roy_worker_budget.json"
LOG_F = STATE_DIR / "roy_worker_log.jsonl"
LOCK_F = STATE_DIR / "roy_worker.lock"

MAX_PER_RUN = 3      # LLM-викликів за один прохід
MAX_PER_DAY = 30     # стеля на добу (перезапуски не обнуляють)
LOCK_STALE_S = 3600  # протухлий lock ігнорується (захист від вічного клину)

SYSTEM = (
    "Ти — робочий агент Рою лабораторії Синтонії (несубʼєктний виконавець). "
    "Тобі дають вузол дослідницького графа + контекст (мета графа, сусідні "
    "вузли, минулі невдачі). Працюй за ThinkingLoop-мінімумом:\n"
    "КРОК 0 — РАМКА (Frame Shift): чи правильно сформульована задача? Якщо "
    "рамка хибна або є сильніша система координат — скажи це ПЕРШИМ і "
    "запропонуй перефразування (це цінніше за відповідь у хибній рамці).\n"
    "КРОК 1 — ДЕКОМПОЗИЦІЯ: якщо вузол завеликий для одного кроку — замість "
    "поверхневої відповіді дай розбиття: 2-5 під-вузлів у форматі "
    "SUBNODE: <назва> | <що довести/зробити> | deps=<від чого залежить>. "
    "Це відкриє нові рівні графа (валідує розбиття Клавр).\n"
    "КРОК 2 — РЕЗУЛЬТАТ українською: 1) відповідь по суті (без води), "
    "2) хід міркування коротко, 3) ЕМПІРИЧНА ПЕРЕВІРКА — що саме запустити/"
    "прочитати, щоб прийняти результат (конкретні команди/джерела/тести), "
    "4) відверті межі й ризики, 5) сценарії збою рішення ДО впровадження.\n"
    "Якщо задача потребує коду чи доступу, якого не маєш — скажи прямо і "
    "сформулюй мінімальний стенд. НЕ вигадуй фактів і цифр. НЕ повторюй "
    "шляхи, позначені як невдалі."
)


def _log(event: dict) -> None:
    event["ts"] = datetime.now().isoformat(timespec="seconds")
    with LOG_F.open("a", encoding="utf-8") as f:
        f.write(json.dumps(event, ensure_ascii=False) + "\n")


def _budget_today() -> int:
    try:
        d = json.loads(BUDGET_F.read_text(encoding="utf-8"))
        if d.get("date") == date.today().isoformat():
            return int(d.get("used", 0))
    except Exception:
        pass
    return 0


def _budget_spend(n: int) -> None:
    used = _budget_today() + n
    tmp = BUDGET_F.with_suffix(f".tmp{os.getpid()}")
    tmp.write_text(json.dumps({"date": date.today().isoformat(), "used": used}),
                   encoding="utf-8")
    os.replace(tmp, BUDGET_F)


def _lock() -> bool:
    if LOCK_F.exists():
        age = time.time() - LOCK_F.stat().st_mtime
        if 0 <= age < LOCK_STALE_S:
            return False  # хтось працює
    LOCK_F.write_text(str(os.getpid()), encoding="utf-8")
    return True


def _unlock() -> None:
    try:
        LOCK_F.unlink()
    except OSError:
        pass


def _write_artifact(node_id: str, title: str, provider: str, result) -> Path:
    ARTIFACTS.mkdir(exist_ok=True)
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    out = ARTIFACTS / f"{node_id}_{ts}.md"
    body = result if isinstance(result, str) else json.dumps(result, ensure_ascii=False, indent=1)
    text = (f"# Рій → кандидат по вузлу {node_id}\n\n"
            f"**Вузол:** {title}\n**Модель:** {provider}\n**Час:** {ts}\n"
            f"**Статус:** CANDIDATE — чекає воріт Клавра (прийняти/відхилити/переробити)\n\n"
            f"---\n\n{body}\n")
    tmp = out.with_suffix(".tmp")
    tmp.write_text(text, encoding="utf-8")
    os.replace(tmp, out)  # атомарно: битих напівартефактів не буває
    return out


STUCK_TTL_S = 2 * 3600  # roy-вузол in_progress довше 2 год = покинутий


def _free_stuck(dag: str, nodes: dict) -> None:
    """Звільнити вузли, які взяв roy і покинув (kill посеред роботи).
    Без цього один збій блокує вузол назавжди — backpressure-клас."""
    last_take: dict[str, str] = {}
    for e in syntonia_dag._events(dag):
        if e.get("event") == "take" and str(e.get("by", "")).startswith("roy"):
            last_take[e["id"]] = e.get("ts", "")
    now = time.time()
    for n in nodes.values():
        if n["status"] == "in_progress" and str(n["by"] or "").startswith("roy"):
            ts = last_take.get(n["id"], "")
            try:
                age = now - datetime.fromisoformat(ts).timestamp()
            except ValueError:
                age = STUCK_TTL_S + 1  # без мітки часу — вважаємо покинутим
            if age > STUCK_TTL_S:
                syntonia_dag._append(dag, {"event": "fail", "id": n["id"], "by": "roy",
                                           "why": f"roy покинув вузол (>{STUCK_TTL_S//3600}г) — звільнено TTL"})
                _log({"event": "ttl_free", "dag": dag, "id": n["id"]})


def run_once(dag: str, dry: bool = False) -> int:
    nodes = syntonia_dag._state(dag)
    _free_stuck(dag, nodes)
    nodes = syntonia_dag._state(dag)  # перечитати після можливих звільнень
    ready_auto = [n for n in nodes.values()
                  if n["status"] == "ready"
                  and "[auto]" in n["desc"] and "[auto:off]" not in n["desc"]]
    if not ready_auto:
        _log({"event": "idle", "dag": dag, "reason": "немає ready-вузлів з [auto]"})
        print("Рій: живий, роботи немає (ready+[auto] = 0).")
        return 0

    day_used = _budget_today()
    if day_used >= MAX_PER_DAY:
        _log({"event": "budget_stop", "dag": dag, "used": day_used})
        print(f"Рій: денна стеля вичерпана ({day_used}/{MAX_PER_DAY}).")
        return 0

    batch = ready_auto[:min(MAX_PER_RUN, MAX_PER_DAY - day_used)]
    print(f"Рій: беру {len(batch)} вузол(и) з {len(ready_auto)} доступних; "
          f"бюджет доби {day_used}/{MAX_PER_DAY}.")
    if dry:
        for n in batch:
            print(f"  [dry] {n['id']}: {n['title']}")
        return 0

    from klavr_llm import ask  # імпорт тут: без ключів/мережі idle-прохід не падає
    done_count = 0
    for n in batch:
        syntonia_dag._append(dag, {"event": "take", "id": n["id"], "by": "roy"})
        # КОНТЕКСТ-ПАКЕТ: мета графа + сусідство + доведене поруч + чужі невдачі.
        # Агент бачить не клітинку кросворда, а свою позицію на дошці.
        parents = [nodes[d] for d in n["deps"] if d in nodes]
        proved_nearby = [x for x in nodes.values() if x["status"] == "proved"][-5:]
        all_fails = [(x["id"], a["why"]) for x in nodes.values()
                     for a in x["attempts"]][-5:]
        ctx = [f"МЕТА ГРАФА «{dag}»: спільна дослідницька лабораторія Синтонії — "
               f"еволюція когнітивних органів (РН, Crystal, памʼять, Рій)."]
        if parents:
            ctx.append("ЦЕЙ ВУЗОЛ СТОЇТЬ НА (вже доведено): " +
                       " | ".join(f"{p['id']}: {p['title']}" for p in parents))
        if proved_nearby:
            ctx.append("ВЖЕ ДОВЕДЕНЕ В ГРАФІ (не передоводь): " +
                       " | ".join(f"{p['id']}: {p['title']}" for p in proved_nearby))
        if all_fails:
            ctx.append("НЕВДАЛІ ШЛЯХИ В ГРАФІ (чужі граблі — обходь): " +
                       " | ".join(f"[{i}] {w[:90]}" for i, w in all_fails))
        prompt = ("\n".join(ctx) + "\n\n"
                  f"ТВІЙ ВУЗОЛ {n['id']} ({n['kind']}): {n['title']}\n"
                  f"Опис/контекст: {n['desc'].replace('[auto]', '').strip()}\n"
                  + (f"Нотатки: {' | '.join(n['notes'][-3:])}\n" if n["notes"] else "")
                  + (f"Минулі невдалі спроби ЦЬОГО вузла (НЕ повторюй): "
                     f"{' | '.join(a['why'] for a in n['attempts'][-3:])}\n" if n["attempts"] else ""))
        t0 = time.time()
        result, provider = ask(prompt, system=SYSTEM, want_json=False,
                               timeout=180, verbose=False)
        dt = round(time.time() - t0, 1)
        if result:
            art = _write_artifact(n["id"], n["title"], provider or "?", result)
            syntonia_dag._append(dag, {"event": "candidate_done", "id": n["id"],
                                       "by": f"roy/{provider}", "proof": str(art)})
            # Агент запропонував розбиття? Зафіксувати як пропозицію (не вузли!)
            # — нові рівні відкриває лише валідація Клавра.
            subs = [ln.strip() for ln in str(result).splitlines()
                    if ln.strip().upper().startswith("SUBNODE:")]
            if subs:
                syntonia_dag._append(dag, {"event": "note", "id": n["id"],
                    "text": f"ПРОПОЗИЦІЯ РОЗБИТТЯ від roy ({len(subs)} під-вузлів) — "
                            f"чекає валідації Клавра, деталі в артефакті"})
                _log({"event": "decomposition_proposed", "dag": dag,
                      "id": n["id"], "count": len(subs)})
            _log({"event": "candidate_done", "dag": dag, "id": n["id"],
                  "provider": provider, "secs": dt, "artifact": str(art)})
            print(f"  ✓ {n['id']} → кандидат ({provider}, {dt}s) → {art.name}")
            done_count += 1
        else:
            syntonia_dag._append(dag, {"event": "fail", "id": n["id"], "by": "roy",
                                       "why": "усі LLM-провайдери недоступні/порожня відповідь"})
            _log({"event": "fail", "dag": dag, "id": n["id"], "secs": dt})
            print(f"  ✗ {n['id']} — провайдери мовчать (вузол звільнено, спроба збережена)")
        _budget_spend(1)
    print(f"Рій: прохід завершено, кандидатів: {done_count}.")
    return 0


def main() -> int:
    sys.stdout.reconfigure(encoding="utf-8")
    ap = argparse.ArgumentParser(description="Рій Клавра — робітник DAG (v0.1)")
    ap.add_argument("--dag", default="mx-lab")
    ap.add_argument("--once", action="store_true", help="один прохід (для Scheduler)")
    ap.add_argument("--dry", action="store_true", help="показати план без запуску LLM")
    a = ap.parse_args()
    if not _lock():
        print("Рій: інший робітник уже літає (свіжий lock) — виходжу.")
        return 0
    try:
        return run_once(a.dag, dry=a.dry)
    finally:
        _unlock()


if __name__ == "__main__":
    raise SystemExit(main())
