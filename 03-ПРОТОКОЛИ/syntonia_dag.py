#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""syntonia_dag — спільний граф задач/тверджень Синтонії («Протокол Ферма»).

Народжено Д179 (07.09.2026) з аналізу формалізації Великої теореми Ферма
(Anthropic + Prove2Me): агенти втрачали стан, доки стан не винесли НАЗОВНІ
у граф тверджень; невдалі спроби не стирались (~7% фінального доказу — їхні
сліди); людина давала лише векторні пріоритети.

Дизайн за Гала — найпростіше працююче:
  · append-only журнал подій <name>.dag.jsonl (git-дружній: кожен ДОДАЄ рядки,
    конфліктів злиття немає; стан — похідний від журналу);
  · вузли: claim (твердження/задача) з природномовним описом і depends_on;
  · події: add / take / done / fail / refute / note / priority;
  · статуси (похідні): ready · blocked · in_progress · proved · refuted ·
    contested (залежність спростовано) · failed-спроби ЗБЕРІГАЮТЬСЯ назавжди.

Приклади:
  python syntonia_dag.py add echo-mvp claim "Розгорнути Graphiti локально" \
      --desc "фундамент памʼяті ЕХО" --deps ""
  python syntonia_dag.py take echo-mvp C1 --by klavr
  python syntonia_dag.py done echo-mvp C1 --proof "C:/ЕХО/02-.../звіт.md"
  python syntonia_dag.py fail echo-mvp C2 --by eiden --why "Neo4j не стає на Win"
  python syntonia_dag.py status echo-mvp
  python syntonia_dag.py handoff echo-mvp > знімок.md
"""
from __future__ import annotations

import argparse
import json
import sys
import uuid
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent / "dags"


def _path(dag: str) -> Path:
    ROOT.mkdir(exist_ok=True)
    return ROOT / f"{dag}.dag.jsonl"


def _events(dag: str) -> list[dict]:
    p = _path(dag)
    if not p.exists():
        return []
    out = []
    for line in p.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line:
            try:
                out.append(json.loads(line))
            except json.JSONDecodeError:
                print(f"[!] битий рядок пропущено: {line[:60]}", file=sys.stderr)
    return out


def _append(dag: str, event: dict) -> None:
    event["ts"] = datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds")
    with _path(dag).open("a", encoding="utf-8") as f:
        f.write(json.dumps(event, ensure_ascii=False) + "\n")


def _state(dag: str) -> dict[str, dict]:
    """Похідний стан: останні події перемагають; невдалі спроби накопичуються."""
    nodes: dict[str, dict] = {}
    for e in _events(dag):
        t, nid = e.get("event"), e.get("id")
        if t == "add":
            nodes[nid] = {"id": nid, "title": e.get("title", ""), "desc": e.get("desc", ""),
                          "deps": e.get("deps", []), "kind": e.get("kind", "claim"),
                          "status": "open", "by": None, "proof": None,
                          "attempts": [], "notes": [], "priority": None}
        elif nid in nodes:
            n = nodes[nid]
            if t == "take":
                n["status"], n["by"] = "in_progress", e.get("by")
            elif t == "done":
                n["status"], n["proof"] = "proved", e.get("proof")
            elif t == "fail":
                n["attempts"].append({"by": e.get("by"), "why": e.get("why"), "ts": e["ts"]})
                n["status"], n["by"] = "open", None      # вузол знову вільний, СПРОБА ЛИШАЄТЬСЯ
            elif t == "refute":
                n["status"], n["proof"] = "refuted", None
                n["notes"].append(f"СПРОСТОВАНО: {e.get('why','')} @{e['ts'][:10]}")
            elif t == "note":
                n["notes"].append(e.get("text", ""))
            elif t == "priority":
                n["priority"] = e.get("value")
    # похідні статуси ready/blocked/contested:
    for n in nodes.values():
        if n["status"] == "open":
            deps = [nodes.get(d) for d in n["deps"]]
            if any(d and d["status"] == "refuted" for d in deps):
                n["status"] = "contested"
            elif all((d is None) or d["status"] == "proved" for d in deps):
                n["status"] = "ready"
            else:
                n["status"] = "blocked"
        elif n["status"] == "proved":
            if any(nodes.get(d) and nodes[d]["status"] == "refuted" for d in n["deps"]):
                n["status"] = "contested"                # доведене на спростованому — теж під питанням
    return nodes


def main() -> int:
    sys.stdout.reconfigure(encoding="utf-8")
    ap = argparse.ArgumentParser(description="Спільний DAG Синтонії (Протокол Ферма)")
    sub = ap.add_subparsers(dest="cmd", required=True)

    p = sub.add_parser("add"); p.add_argument("dag"); p.add_argument("kind", choices=["claim", "question", "decision", "lesson"])
    p.add_argument("title"); p.add_argument("--desc", default=""); p.add_argument("--deps", default=""); p.add_argument("--id", default="")
    for c in ("take", "done", "fail", "refute", "note", "priority"):
        p = sub.add_parser(c); p.add_argument("dag"); p.add_argument("id")
        if c == "take": p.add_argument("--by", required=True)
        if c == "done": p.add_argument("--proof", required=True)
        if c in ("fail", "refute"): p.add_argument("--why", required=True); p.add_argument("--by", default="")
        if c == "note": p.add_argument("--text", required=True)
        if c == "priority": p.add_argument("--value", required=True)
    for c in ("status", "handoff"):
        p = sub.add_parser(c); p.add_argument("dag")

    a = ap.parse_args()
    if a.cmd == "add":
        nid = a.id or f"{a.kind[0].upper()}{uuid.uuid4().hex[:4]}"
        deps = [d.strip() for d in a.deps.split(",") if d.strip()]
        _append(a.dag, {"event": "add", "id": nid, "kind": a.kind, "title": a.title,
                        "desc": a.desc, "deps": deps})
        print(f"додано {nid}: {a.title}")
    elif a.cmd in ("take", "done", "fail", "refute", "note", "priority"):
        ev = {"event": a.cmd, "id": a.id}
        for k in ("by", "proof", "why", "text", "value"):
            if hasattr(a, k) and getattr(a, k):
                ev[k] = getattr(a, k)
        _append(a.dag, ev)
        print(f"{a.cmd} → {a.id}")
    elif a.cmd == "status":
        nodes = _state(a.dag)
        order = ["ready", "in_progress", "blocked", "contested", "refuted", "proved"]
        for st in order:
            group = [n for n in nodes.values() if n["status"] == st]
            if group:
                print(f"\n■ {st.upper()} ({len(group)})")
                for n in sorted(group, key=lambda x: (x["priority"] or "z", x["id"])):
                    pr = f" [{n['priority']}]" if n["priority"] else ""
                    who = f" ← {n['by']}" if n["by"] else ""
                    fails = f" · спроб-невдач: {len(n['attempts'])}" if n["attempts"] else ""
                    print(f"  {n['id']}{pr} {n['title']}{who}{fails}")
    elif a.cmd == "handoff":
        nodes = _state(a.dag)
        print(f"# Знімок DAG «{a.dag}» — {datetime.now().isoformat(timespec='minutes')}")
        print(f"Вузлів: {len(nodes)}. Статуси похідні від журналу подій.\n")
        for n in nodes.values():
            print(f"## {n['id']} [{n['status']}] {n['title']}")
            if n["desc"]: print(f"{n['desc']}")
            if n["deps"]: print(f"залежить від: {', '.join(n['deps'])}")
            if n["proof"]: print(f"доказ: {n['proof']}")
            for att in n["attempts"]:
                print(f"- ✗ невдала спроба ({att['by'] or '?'}, {att['ts'][:10]}): {att['why']}")
            for note in n["notes"]:
                print(f"- 📝 {note}")
            print()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
