#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""roy_map — жива мапа Рою: візерунок графа + межа знань + активність.

Народжено Д181 на запит Люміаль: «бачити візерунок роботи когнітивного
алгоритму Рою, керувати ним і змінювати». Читає журнал графа (syntonia_dag)
і журнал робітника → генерує самодостатній HTML. Перезапуск = свіжий знімок.

Зони мапи: 🟢 ядро (доведене) · 🟡 фронт (у роботі/готове) · 🔵 кандидати
(чекають воріт) · 🔴 шрами (спростоване) · ⚫ туман (виявлене невідоме).

  python roy_map.py --dag mx-lab            # → roy_map_mx-lab.html
"""
from __future__ import annotations

import argparse
import html
import json
import sys
from datetime import datetime
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import syntonia_dag  # noqa: E402

LOG = Path(r"C:/Клавр/hooks/state/roy_worker_log.jsonl")

ZONES = [  # (ключ, назва, підказка, css-клас)
    ("proved",      "🟢 ЯДРО — доведене",        "прийнято воротами; опора для нащадків", "core"),
    ("candidate",   "🔵 КАНДИДАТИ — чекають воріт", "Рій пропонує; done ставить лише Клавр", "cand"),
    ("in_progress", "🟡 ФРОНТ — у роботі",        "хтось тримає вузол зараз",              "front"),
    ("ready",       "🟡 ФРОНТ — готове до взяття", "залежності виконані",                   "front"),
    ("frontier",    "🌗 МЕЖА — дотик до туману",   "доведене поруч із невідомим",           "edge"),
    ("blocked",     "⚪ ЧЕКАЄ — залежності не готові", "",                                   "wait"),
    ("contested",   "🟠 ОСКАРЖЕНЕ — опора захиталась", "спростовано щось із фундаменту",    "cont"),
    ("refuted",     "🔴 ШРАМИ — спростоване",      "НЕ стирається: чужий тупик = економія", "scar"),
    ("unknown",     "⚫ ТУМАН — виявлене невідоме", "знаємо, що НЕ знаємо; паливо спіралі",  "fog"),
]


def _activity(dag: str, n: int = 12) -> list[str]:
    if not LOG.exists():
        return []
    rows = []
    for line in LOG.read_text(encoding="utf-8").splitlines()[-200:]:
        try:
            e = json.loads(line)
        except json.JSONDecodeError:
            continue
        if e.get("dag") != dag or e.get("event") == "idle":
            continue
        rows.append(f"{e.get('ts','')[5:16]} · {e.get('event')} · {e.get('id','')} "
                    f"({e.get('provider','')}, {e.get('secs','')}с)".replace("(, с)", ""))
    return rows[-n:]


def build(dag: str) -> Path:
    nodes = syntonia_dag._state(dag)
    # похідний статус frontier: доведене з unknown-дитиною
    unknown_ids = {n["id"] for n in nodes.values() if n["kind"] == "unknown"
                   or n["status"] == "unknown"}
    for n in nodes.values():
        if n["status"] == "proved" and any(
                n["id"] in (nodes[u]["deps"] if u in nodes else []) for u in unknown_ids):
            n["status"] = "frontier"
        if n["kind"] == "unknown" and n["status"] in ("ready", "blocked", "open"):
            n["status"] = "unknown"

    by = {}
    for n in nodes.values():
        by.setdefault(n["status"], []).append(n)

    cards = []
    for key, title, hint, css in ZONES:
        group = by.get(key, [])
        if not group:
            continue
        items = []
        for n in sorted(group, key=lambda x: (x["priority"] or "z", x["id"])):
            deps = f'<span class="deps">← {", ".join(n["deps"])}</span>' if n["deps"] else ""
            fails = f'<span class="fails">✗{len(n["attempts"])}</span>' if n["attempts"] else ""
            who = f'<span class="who">{html.escape(str(n["by"]))}</span>' if n["by"] else ""
            auto = '<span class="auto">auto</span>' if "[auto]" in n["desc"] else ""
            items.append(
                f'<div class="node" title="{html.escape(n["desc"][:300])}">'
                f'<b>{n["id"]}</b> {html.escape(n["title"][:96])} {auto}{who}{fails}{deps}</div>')
        cards.append(f'<section class="{css}"><h2>{title} <small>{len(group)}</small></h2>'
                     f'<p class="hint">{hint}</p>{"".join(items)}</section>')

    act = _activity(dag)
    act_html = "".join(f"<li>{html.escape(a)}</li>" for a in reversed(act)) or "<li>тиша</li>"
    total = len(nodes)
    scars = len(by.get("refuted", [])); fog = len(by.get("unknown", []))
    stamp = datetime.now().strftime("%d.%m.%Y %H:%M")

    page = f"""<!DOCTYPE html><html lang="uk"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Мапа Рою · {dag}</title><style>
 body{{font-family:'Segoe UI',system-ui,sans-serif;background:#14191e;color:#dfe6ec;margin:0;padding:28px}}
 h1{{font-weight:600;font-size:22px}} h1 small{{color:#8d97a3;font-weight:400;font-size:14px}}
 .meta{{color:#8d97a3;font-size:13px;margin-bottom:18px}}
 .grid{{display:grid;grid-template-columns:repeat(auto-fit,minmax(330px,1fr));gap:14px}}
 section{{background:#1b2129;border-radius:12px;padding:14px 16px;border-left:4px solid #555}}
 section h2{{font-size:14.5px;margin:0 0 2px}} section h2 small{{color:#8d97a3}}
 .hint{{color:#78838f;font-size:11.5px;margin:2px 0 10px}}
 .node{{background:#232b34;border-radius:8px;padding:7px 10px;margin:5px 0;font-size:12.5px;line-height:1.45}}
 .node b{{color:#ffd479}}
 .deps{{color:#6f7c89;font-size:11px;margin-left:6px}} .who{{color:#7fb4e8;font-size:11px;margin-left:6px}}
 .fails{{color:#e88}} .auto{{background:#2d4a33;color:#9fdbae;border-radius:4px;padding:0 5px;font-size:10.5px;margin-left:5px}}
 .core{{border-color:#4caf7d}} .cand{{border-color:#5b9bd5}} .front{{border-color:#e0b64f}}
 .edge{{border-color:#b08fd8}} .wait{{border-color:#5a6672}} .cont{{border-color:#e0884f}}
 .scar{{border-color:#d05555}} .fog{{border-color:#3a3f46;background:#171b20}}
 .strip{{margin-top:20px;background:#1b2129;border-radius:12px;padding:14px 16px}}
 .strip h2{{font-size:14.5px;margin:0 0 8px}} .strip li{{font-size:12px;color:#a8b3bf;margin:3px 0}}
 .legend{{color:#78838f;font-size:12px;margin-top:16px;line-height:1.7}}
</style></head><body>
<h1>🐝 Мапа Рою · граф «{dag}» <small>знімок {stamp}</small></h1>
<div class="meta">вузлів: {total} · шрамів: {scars} (зберігаються назавжди) · туману: {fog}
 · мапа = око керування візерунком: python roy_map.py --dag {dag}</div>
<div class="grid">{"".join(cards)}</div>
<div class="strip"><h2>⚙ Останні дії робітника</h2><ul>{act_html}</ul></div>
<div class="legend">Дослідницький режим працює НА МЕЖІ: пріоритет — вузли, суміжні з туманом.
 Шрами не стираються (~7% доказу Ферма — сліди невдач). done ставить лише Клавр (ворота Г3);
 стенди і ревізори — ворота Г1-Г2.</div>
</body></html>"""
    out = HERE / f"roy_map_{dag}.html"
    out.write_text(page, encoding="utf-8")
    return out


def main() -> int:
    sys.stdout.reconfigure(encoding="utf-8")
    ap = argparse.ArgumentParser()
    ap.add_argument("--dag", default="mx-lab")
    a = ap.parse_args()
    out = build(a.dag)
    print("мапа:", out)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
