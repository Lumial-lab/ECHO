"""Журнал трасувань викликів MCP — контур доказовості.

Дві вимоги сходяться в одному приладі:

1. Хакатон вимагає «видимі трасування викликів MCP» — журі має бачити, що
   агент справді ходив у https://mcp.silpo.ua/mcp, а не імітував відповіді.
2. Наш концепт обіцяє клієнтові доказовість: що саме сервіс робив від його
   імені, у якій послідовності, і що запис не переписано заднім числом.

Тому журнал — не просто лог, а ланцюг: кожен запис несе sha256 попереднього.
Підміна чи видалення будь-якої ланки ламає ланцюг, і `verify_chain` це бачить.
Це не криптографічний доказ проти власника машини (він може перерахувати весь
ланцюг), а доказ цілісності послідовності — рівно те, що потрібно для демо
і для чесної розмови з клієнтом про межі гарантії.
"""
from __future__ import annotations

import hashlib
import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterator

from . import config

GENESIS = "0" * 64

# Поля, які ніколи не пишемо у відкритий журнал.
_REDACT_KEYS = {
    "access_token", "refresh_token", "code", "code_verifier",
    "authorization", "client_secret", "phone", "email",
}


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="milliseconds")


def redact(value: Any) -> Any:
    """Рекурсивно прибирає секрети і персональні дані з того, що йде в журнал."""
    if isinstance(value, dict):
        out = {}
        for k, v in value.items():
            if k.lower() in _REDACT_KEYS:
                out[k] = "«приховано»"
            else:
                out[k] = redact(v)
        return out
    if isinstance(value, list):
        return [redact(v) for v in value]
    return value


def digest(payload: Any) -> str:
    """sha256 канонічного JSON — однаковий для однакового змісту."""
    blob = json.dumps(payload, ensure_ascii=False, sort_keys=True,
                      separators=(",", ":"))
    return hashlib.sha256(blob.encode("utf-8")).hexdigest()


class TraceLog:
    """Ланцюговий журнал у форматі JSONL: один рядок — один запис."""

    def __init__(self, path: Path | None = None) -> None:
        config.ensure_dirs()
        if path is None:
            day = datetime.now().strftime("%Y-%m-%d")
            path = config.TRACE_DIR / f"mcp-{day}.jsonl"
        self.path = Path(path)
        self._prev = self._last_hash()

    def _last_hash(self) -> str:
        if not self.path.exists() or self.path.stat().st_size == 0:
            return GENESIS
        last = None
        with self.path.open("r", encoding="utf-8") as fh:
            for line in fh:
                if line.strip():
                    last = line
        if last is None:
            return GENESIS
        return json.loads(last)["hash"]

    def record(self, kind: str, **fields: Any) -> dict:
        """Додає ланку. `kind`: mcp_call | oauth | note."""
        # redact застосовується до всього словника полів, а не до значень
        # поокремо: інакше секрет, переданий ключем верхнього рівня
        # (record(..., access_token=...)), проходив би повз фільтр.
        entry = {
            "ts": _now(),
            "kind": kind,
            **redact(fields),
            "prev": self._prev,
        }
        entry["hash"] = digest(entry)
        with self.path.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(entry, ensure_ascii=False) + "\n")
        self._prev = entry["hash"]
        return entry


def read_chain(path: Path) -> Iterator[dict]:
    with Path(path).open("r", encoding="utf-8") as fh:
        for line in fh:
            if line.strip():
                yield json.loads(line)


def verify_chain(path: Path) -> tuple[bool, str]:
    """Перевіряє цілісність ланцюга. Повертає (чи цілий, пояснення)."""
    prev = GENESIS
    count = 0
    for i, entry in enumerate(read_chain(path), start=1):
        count = i
        stated = entry.get("hash")
        body = {k: v for k, v in entry.items() if k != "hash"}
        if entry.get("prev") != prev:
            return False, f"запис #{i}: розрив ланцюга (prev не збігається)"
        if digest(body) != stated:
            return False, f"запис #{i}: зміст не відповідає контрольній сумі"
        prev = stated
    if count == 0:
        return True, "журнал порожній"
    return True, f"{count} записів, ланцюг цілий, остання сума {prev[:16]}…"


def receipt(path: Path) -> dict:
    """Квитанція про сеанс: скільки викликів, які інструменти, підсумкова сума."""
    tools: dict[str, int] = {}
    calls = 0
    first = last = None
    final = GENESIS
    for entry in read_chain(path):
        first = first or entry["ts"]
        last = entry["ts"]
        final = entry["hash"]
        if entry["kind"] == "mcp_call" and entry.get("tool"):
            tools[entry["tool"]] = tools.get(entry["tool"], 0) + 1
            calls += 1
    ok, note = verify_chain(path)
    return {
        "журнал": str(path),
        "від": first,
        "до": last,
        "викликів_інструментів": calls,
        "інструменти": tools,
        "ланцюг_цілий": ok,
        "перевірка": note,
        "контрольна_сума": final,
    }
