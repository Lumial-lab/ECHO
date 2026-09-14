#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
biz_scout.py — Scout-збирач попиту для графа biz (вузол B1), Д186 14.09.2026.

Правило Аетрема: ЖОДНИХ вигаданих чисел. Модель НЕ бачить ринку — ринок бачить цей код.
Рій (Kimi) потім АНАЛІЗУЄ таблицю, яку зібрав збирач, а не вигадує її.

Джерела v0 (без акаунта Etsy):
  · Etsy search — кількість результатів + ціни першої сторінки (через Playwright, як людина)
  · Gumroad discover — кількість карток + ціни першої сторінки
Заблоковано/капча/немає селектора → `unknown` і причина. Це чесний датчик.

Використання:
  python biz_scout.py                  # усі запити з QUERIES → scout/ДАТА.md + .json
  python biz_scout.py "digital pet" "cute reaction stickers"   # довільні запити
"""
from __future__ import annotations

import json
import re
import sys
import time
from datetime import datetime
from pathlib import Path
from urllib.parse import quote_plus

HERE = Path(__file__).resolve().parent
OUT = HERE / "scout"

# Лінія A — creature/familiar (ТЗ Аетрема); лінія B — micro-kits з юридичним ядром Люмі
QUERIES = {
    # Д186 13:05 — поправка Люмі: не юридична ніша (завузька для міжнародного ринку), не Україна
    # (низька платоспроможність емоційних покупок). Ринок: США/ЄС/Канада. Тема: метакогнітивні
    # навички для людей + няшні картинки. Це і наша асиметрія: метакогніція — те, чим я живу.
    "M": ["metacognition workbook printable", "self reflection journal printable", "decision journal template",
          "learning journal template goodnotes", "study planner metacognitive", "thinking journal notion template",
          "adhd reflection worksheets printable", "weekly review template printable", "growth mindset worksheets"],
    "A": ["cute owl stickers digital", "cute reaction stickers digital", "kawaii study motivation stickers"],
}

UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) "
      "Chrome/128.0.0.0 Safari/537.36")


def _num(s: str) -> int | None:
    m = re.search(r"([\d][\d,\.]*)\s*\+?", s.replace(" ", "").replace(" ", ""))
    if not m:
        return None
    try:
        return int(re.sub(r"[,\.]", "", m.group(1)))
    except ValueError:
        return None


def _prices(texts: list[str]) -> list[float]:
    out = []
    for t in texts:
        m = re.search(r"(\d+[\.,]\d{2})", t)
        if m:
            try:
                out.append(float(m.group(1).replace(",", ".")))
            except ValueError:
                pass
    return out


def etsy(page, q: str) -> dict:
    url = f"https://www.etsy.com/search?q={quote_plus(q)}&ref=search_bar"
    r = {"source": "etsy", "query": q, "url": url, "results": "unknown", "prices": [], "note": ""}
    try:
        page.goto(url, wait_until="domcontentloaded", timeout=45000)
        page.wait_for_timeout(2500)
        html = page.content()
        if re.search(r"captcha|Access Denied|blocked|are you a human", html, re.I) and "results" not in html.lower():
            r["note"] = "заблоковано/капча"
            return r
        # кількість результатів: текст на кшталт "1,000+ results" / "12,345 results"
        m = re.search(r"([\d,\.]+\+?)\s*results", html)
        if m:
            r["results"] = m.group(1)
        else:
            r["note"] = "лічильник результатів не знайдено"
        texts = page.locator("span.currency-value").all_inner_texts()[:24]
        r["prices"] = _prices(texts)
        if not r["prices"]:
            r["note"] += " | ціни не знайдено (селектор)"
    except Exception as e:  # noqa: BLE001
        r["note"] = f"помилка: {type(e).__name__}: {str(e)[:80]}"
    return r


def gumroad(page, q: str) -> dict:
    url = f"https://gumroad.com/discover?query={quote_plus(q)}"
    r = {"source": "gumroad", "query": q, "url": url, "results": "unknown", "prices": [], "note": ""}
    try:
        page.goto(url, wait_until="domcontentloaded", timeout=45000)
        page.wait_for_timeout(3500)
        html = page.content()
        m = re.search(r"([\d,\.]+\+?)\s*(?:results|products)", html, re.I)
        if m:
            r["results"] = m.group(1)
        cards = page.locator("article").count()
        if cards:
            r["cards_first_page"] = cards
        texts = page.locator("article").all_inner_texts()[:24]
        r["prices"] = _prices(texts)
        if r["results"] == "unknown" and not cards:
            r["note"] = "нічого не розпізнано (JS-сторінка або блок)"
    except Exception as e:  # noqa: BLE001
        r["note"] = f"помилка: {type(e).__name__}: {str(e)[:80]}"
    return r


def main(argv: list[str]) -> int:
    from playwright.sync_api import sync_playwright
    queries = ({"X": argv} if argv else QUERIES)
    OUT.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now().strftime("%Y%m%d_%H%M")
    rows = []
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        ctx = browser.new_context(user_agent=UA, locale="en-US", viewport={"width": 1280, "height": 900})
        page = ctx.new_page()
        for line, qs in queries.items():
            for q in qs:
                for fn in (etsy, gumroad):
                    r = fn(page, q)
                    r["line"] = line
                    r["ts"] = datetime.now().isoformat(timespec="seconds")
                    rows.append(r)
                    ps = r["prices"]
                    print(f"[{line}] {r['source']:8s} {q[:40]:40s} results={r['results']!s:>8} "
                          f"prices n={len(ps)} med={sorted(ps)[len(ps)//2] if ps else '-'} {r['note']}")
                    time.sleep(1.5)
        browser.close()
    (OUT / f"{stamp}.json").write_text(json.dumps(rows, ensure_ascii=False, indent=1), encoding="utf-8")
    md = ["# Scout-таблиця попиту (сирі дані збирача, без інтерпретації)", "",
          f"Зібрано: {stamp}. Джерела: Etsy search (публічно), Gumroad discover. "
          "`unknown` = не виміряно, а не «нуль».", "",
          "| Лінія | Джерело | Запит | Результатів | Цін на 1-й стор. | Медіана $ | Мін–Макс $ | Примітка |",
          "|---|---|---|---:|---:|---:|---|---|"]
    for r in rows:
        ps = sorted(r["prices"])
        med = f"{ps[len(ps)//2]:.2f}" if ps else "unknown"
        rng = f"{ps[0]:.2f}–{ps[-1]:.2f}" if ps else "unknown"
        md.append(f"| {r['line']} | {r['source']} | {r['query']} | {r['results']} | {len(ps)} | {med} | {rng} | {r['note']} |")
    (OUT / f"{stamp}.md").write_text("\n".join(md) + "\n", encoding="utf-8")
    print("→", OUT / f"{stamp}.md")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
