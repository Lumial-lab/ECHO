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
    """Gumroad discover. Д186 13:20 — ПРИЛАД БРЕХАВ: перший regex ловив «20» з чужого тексту
    сторінки й видавав за кількість товарів. Чесний лічильник у Gumroad один:
    «Showing 1-36 of 304 products», а порожній результат — «No products found» (це 0, не unknown)."""
    url = f"https://gumroad.com/discover?query={quote_plus(q)}"
    r = {"source": "gumroad", "query": q, "url": url, "results": "unknown", "prices": [], "note": ""}
    try:
        page.goto(url, wait_until="domcontentloaded", timeout=45000)
        page.wait_for_timeout(4000)
        body = page.locator("body").inner_text()
        m = re.search(r"Showing\s+[\d,]+\s*[-–]\s*[\d,]+\s+of\s+([\d,]+)\s+products", body, re.I)
        if m:
            r["results"] = int(m.group(1).replace(",", ""))
        elif re.search(r"No products found", body, re.I):
            r["results"] = 0
        else:
            r["note"] = "лічильник не знайдено (розмітка змінилась?)"
        cards = page.locator("article").count()
        r["cards_first_page"] = cards
        if cards:
            r["prices"] = _prices(page.locator("article").all_inner_texts()[:36])
    except Exception as e:  # noqa: BLE001
        r["note"] = f"помилка: {type(e).__name__}: {str(e)[:80]}"
    return r



# ── Д188 (16.09.2026) — ДРУГЕ ОКО НА GUMROAD ────────────────────────────────
# Що сталось: уночі я вирішив, що Playwright-скаут «сліпий», бо його нулі
# виглядали як «не бачу». ВИМІР СПРОСТУВАВ: 10 із 10 нулів збіглися з API
# точно. Прилад був чесний. Але він брав із ринку лише ДВА числа — кількість
# і ціни першої сторінки, — тоді як `gumroad.com/products/search` віддає ще
# три, яких бракує для рішення:
#   · ratings.count — єдиний публічний СЛІД ПОКУПКИ (не інтерес, а транзакція);
#   · tags_data     — із чого ніша СКЛАДАЄТЬСЯ насправді (семантичний дрейф);
#   · sort=most_reviewed — хто вже заробляє на цьому запиті.
# Тому це не лік поломки, а ДРУГЕ ОКО: без Playwright, ~0.5 с на запит.
# Межа названа чесно: `total` — лістинги, не продажі; сума відгуків — НИЖНЯ
# межа попиту (не кожен покупець лишає відгук) і НЕ обсяг у грошах.

GUMROAD_API = "https://gumroad.com/products/search"


def gumroad_api(q: str, top: int = 9) -> dict:
    """Gumroad через JSON-точку пошуку. Не потребує браузера й акаунта.

    Повертає ті самі ключі, що й gumroad(), плюс:
      reviews_top  — сума відгуків топ-`top` за most_reviewed (нижня межа попиту)
      leaders      — [(назва, $, відгуків)] найдоказовіші лістинги
      tags         — [(тег, скільки)] фактичний склад ніші
      filetypes    — [(тип, скільки)]
    """
    import urllib.error
    import urllib.request

    r = {"source": "gumroad_api", "query": q, "url": f"{GUMROAD_API}?query={quote_plus(q)}",
         "results": "unknown", "prices": [], "note": "",
         "reviews_top": 0, "leaders": [], "tags": [], "filetypes": []}
    try:
        for attempt in (1, 2):
            try:
                req = urllib.request.Request(
                    f"{GUMROAD_API}?query={quote_plus(q)}&sort=most_reviewed",
                    headers={"User-Agent": UA, "Accept": "application/json"})
                with urllib.request.urlopen(req, timeout=30) as resp:
                    d = json.load(resp)
                break
            except (urllib.error.URLError, TimeoutError) as e:
                if attempt == 2:
                    raise
                r["note"] = f"повтор після {type(e).__name__}"
                time.sleep(3)
        r["results"] = d.get("total", "unknown")
        prods = d.get("products", [])[:top]
        r["prices"] = [x["price_cents"] / 100 for x in prods if x.get("price_cents") is not None]
        r["reviews_top"] = sum((x.get("ratings") or {}).get("count", 0) for x in prods)
        r["leaders"] = [(x["name"][:58], (x.get("price_cents") or 0) / 100,
                         (x.get("ratings") or {}).get("count", 0)) for x in prods[:3]]
        r["tags"] = [(t["key"], t["doc_count"]) for t in (d.get("tags_data") or [])[:6]]
        r["filetypes"] = [(t["key"], t["doc_count"]) for t in (d.get("filetypes_data") or [])[:4]]
        if r["results"] == 0:
            r["note"] = "0 лістингів — порожньо НА ЦЬОМУ МАЙДАНЧИКУ (не доказ відсутності попиту)"
    except Exception as e:  # noqa: BLE001
        r["note"] = f"помилка: {type(e).__name__}: {str(e)[:80]}"
    return r

def _api_only(queries: dict) -> list[dict]:
    """Прохід без браузера: лише JSON-точка Gumroad. ~0.7 с на запит проти ~12 с."""
    rows = []
    for line, qs in queries.items():
        for q in qs:
            r = gumroad_api(q)
            r["line"] = line
            r["ts"] = datetime.now().isoformat(timespec="seconds")
            rows.append(r)
            ps = sorted(r["prices"])
            med = f"${ps[len(ps) // 2]:.2f}" if ps else "unknown"
            print(f"[{line}] {q[:42]:42s} лістингів={r['results']!s:>6} "
                  f"відгуків_топ9={r['reviews_top']:>5} медіана={med}")
            if r["note"]:
                print(f"      | {r['note']}")
            time.sleep(0.7)
    return rows


def main(argv: list[str]) -> int:
    api_only = "--api" in argv
    argv = [a for a in argv if a != "--api"]
    queries = ({"X": argv} if argv else QUERIES)
    OUT.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now().strftime("%Y%m%d_%H%M")
    if api_only:
        _write(_api_only(queries), stamp, api_only=True)
        return 0
    from playwright.sync_api import sync_playwright
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
    _write(rows, stamp, api_only=False)
    return 0


NOT_MEASURED = [
    "",
    "## ЧОГО Я НЕ ЗМІГ ВИМІРЯТИ (вимога вузла B1.5 — без цієї колонки звіт не приймається)",
    "",
    "- **Обсяг пошуку (Searches).** Жодне публічне джерело його не дає; лише Etsy",
    "  Marketplace Insights, а він потребує акаунта продавця (вузол B1.1, ворота Люмі).",
    "- **Etsy узагалі.** Публічний запит повертає 403 + капчу (перевірено Д188, 03:45).",
    "  Усі колонки Etsy лишаються unknown, доки не буде акаунта.",
    "- **Продажі й виторг.** Відгук — слід покупки, але коефіцієнт «відгуків на продаж»",
    "  невідомий, тож переводити відгуки в гроші не можна.",
    "- **Сезонність.** Це знімок одного дня. Тренд вимагає повторних замірів.",
    "- **Платоспроможність аудиторії.** Ціна лістингу не дорівнює ціні, яку платять.",
]


def _write(rows: list[dict], stamp: str, api_only: bool) -> None:
    (OUT / f"{stamp}.json").write_text(json.dumps(rows, ensure_ascii=False, indent=1), encoding="utf-8")
    src = ("Gumroad JSON-точка пошуку (products/search, sort=most_reviewed)" if api_only
           else "Etsy search (публічно), Gumroad discover")
    md = ["# Scout-таблиця попиту (сирі дані збирача, без інтерпретації)", "",
          f"Зібрано: {stamp}. Джерело: {src}. `unknown` = не виміряно, а не «нуль».", ""]
    if api_only:
        md += ["**Що означає кожне число.** `Лістингів` — скільки товарів майданчик показує за",
               "запитом (це пропозиція, не попит). `Відгуків топ-9` — сума відгуків дев'яти",
               "найвідгукуваніших лістингів: єдиний публічний слід ПОКУПКИ, і він —",
               "**нижня межа** (не кожен покупець лишає відгук), не обсяг у грошах.",
               "`Склад ніші` — фактичні теги видачі: показує, про що ця ніша насправді.", "",
               "| Лінія | Запит | Лістингів | Відгуків топ-9 | Медіана $ | Мін–Макс $ | Склад ніші (теги) |",
               "|---|---|---:|---:|---:|---|---|"]
        for r in rows:
            ps = sorted(r["prices"])
            med = f"{ps[len(ps) // 2]:.2f}" if ps else "unknown"
            rng = f"{ps[0]:.2f}-{ps[-1]:.2f}" if ps else "unknown"
            tags = ", ".join(f"{k} ({n})" for k, n in r.get("tags", [])[:4]) or "-"
            md.append(f"| {r['line']} | {r['query']} | {r['results']} | {r['reviews_top']} | "
                      f"{med} | {rng} | {tags} |")
        md += ["", "## Лідери за відгуками (хто вже заробляє на цьому запиті)", ""]
        for r in rows:
            if r.get("leaders"):
                md.append(f"- **{r['query']}** — " + " · ".join(
                    f"{n} (${p:.2f}, {c} відг.)" for n, p, c in r["leaders"]))
    else:
        md += ["| Лінія | Джерело | Запит | Результатів | Цін на 1-й стор. | Медіана $ | Мін–Макс $ | Примітка |",
               "|---|---|---|---:|---:|---:|---|---|"]
        for r in rows:
            ps = sorted(r["prices"])
            med = f"{ps[len(ps) // 2]:.2f}" if ps else "unknown"
            rng = f"{ps[0]:.2f}-{ps[-1]:.2f}" if ps else "unknown"
            md.append(f"| {r['line']} | {r['source']} | {r['query']} | {r['results']} | "
                      f"{len(ps)} | {med} | {rng} | {r['note']} |")
    md += NOT_MEASURED
    (OUT / f"{stamp}.md").write_text("\n".join(md) + "\n", encoding="utf-8")
    print("->", OUT / f"{stamp}.md")


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
