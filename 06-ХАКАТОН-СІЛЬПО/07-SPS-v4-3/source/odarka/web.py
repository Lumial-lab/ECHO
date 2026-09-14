"""Local presentation surface over the existing read-only MCP client."""
from __future__ import annotations

import asyncio
import json
import math
import re
import threading
from datetime import date, datetime, timezone
from pathlib import Path

from pydantic import BaseModel, Field, ValidationError
from starlette.applications import Starlette
from starlette.middleware.trustedhost import TrustedHostMiddleware
from starlette.requests import Request
from starlette.responses import FileResponse, JSONResponse
from starlette.routing import Mount, Route
from starlette.staticfiles import StaticFiles

from silpo_mcp import config, oauth
from silpo_mcp.client import SilpoMCP
from silpo_mcp.trace import TraceLog, digest
from .tier2 import AggregationRules, Declaration, Level, aggregate

STATIC = Path(__file__).parent / "static"
CALL_LOCK = threading.Lock()
BRANCHES: dict[str, dict] = {}


class PublicTrace(TraceLog):
    """Evidence records contain bounded metadata, never upstream error text."""
    def record(self, kind: str, **fields):
        safe = {}
        allowed = {
            "method": {"initialize", "tools/list", "tools/call"},
            "tool": {"silpo_list_branches", "silpo_get_categories", "silpo_get_time_slots", "silpo_get_products"},
            "статус": {"успіх", "помилка"},
        }
        for key, choices in allowed.items():
            value = fields.get(key)
            if isinstance(value, str) and value in choices:
                safe[key] = value
        for key in ("ms", "отримано", "код"):
            value = fields.get(key)
            if type(value) in (int, float) and math.isfinite(value):
                safe[key] = value
        if type(fields.get("is_error")) is bool:
            safe["is_error"] = fields["is_error"]
        value = fields.get("відповідь_sha256")
        if isinstance(value, str) and re.fullmatch(r"[0-9a-f]{64}", value):
            safe["відповідь_sha256"] = value
        if kind == "mcp_call":
            safe["endpoint"] = "https://mcp.silpo.ua/mcp"
        return super().record(kind if kind in {"mcp_call", "oauth", "note"} else "note", **safe)


def public_entries(entries: list, branches: bool) -> list[dict]:
    id_key = "branchId" if branches else "id"
    result = []
    for row in entries:
        if not isinstance(row, dict) or not isinstance(row.get(id_key), str) or not row[id_key].strip():
            raise ValueError("Missing catalog identifier")
        if branches:
            if not any(isinstance(row.get(k), str) and row[k].strip() for k in ("city", "address")):
                raise ValueError("Missing branch label")
            keys = ("branchId", "city", "address")
        else:
            if not isinstance(row.get("title"), str) or not row["title"].strip():
                raise ValueError("Missing category title")
            keys = ("id", "title", "parentId")
        if any(row.get(k) is not None and not isinstance(row[k], str) for k in keys):
            raise ValueError("Invalid label type")
        result.append({k: row.get(k) for k in keys})
    return result


class DemoPlan(BaseModel):
    participants: int = Field(default=12, ge=1, le=100)
    units: int = Field(default=20, ge=1, le=1000)
    max_price: float | None = Field(default=None, gt=0, le=10000, allow_inf_nan=False)


def group_preview(plan: DemoPlan) -> dict:
    # Every displayed subgroup has its own disclosure check, not only the union.
    rows = []
    for level in Level:
        declarations = []
        if level != Level.COMMITMENT and not (level == Level.INTENT and plan.max_price is None):
            declarations = [Declaration(
                client_id=f"demo-{level.value}-{i}", category="картопля",
                units=plan.units, level=level, horizon=date(2026, 12, 1),
                max_price=plan.max_price if level == Level.INTENT else None,
                derived=level == Level.FORECAST,
            ) for i in range(plan.participants)]
        result = aggregate(declarations, "картопля", AggregationRules())
        visible = result.disclosable
        rows.append({"level": level.name, "label": level.title,
                     "units": result.total(level) if visible else None,
                     "clients": result.clients(level) if visible else None,
                     "disclosable": visible,
                     "reason": "Бажану межу ціни ще не задано" if level == Level.INTENT and plan.max_price is None else result.withheld_reason,
                     "max_price": plan.max_price if visible and level == Level.INTENT else None})
    return {"mode": "synthetic", "unit": "кг", "category": "Картопля на зиму",
            "horizon": "2026-12-01", "rows": rows,
            "notice": "Умовні учасники. Це не реальний попит і не погоджені умови Сільпо."}


def connection_status() -> dict:
    try:
        token = oauth.load_token()
        present = bool(token and token.get("access_token"))
    except (ValueError, OSError):
        present = False
    return {"credential_present": present,
            "connection_verified": False,
            "agent_name": "Пані Одарка", "agent_connected": False,
            "service_name": "СПС", "service_full_name": "Спільнота покупців супермаркету",
            "endpoint": "https://mcp.silpo.ua/mcp"}


def unpack(result: dict) -> dict:
    if result.get("isError"):
        raise ValueError("MCP tool error")
    content = result.get("structuredContent")
    if content is None:
        content = json.loads(SilpoMCP.text_of(result))
    if not isinstance(content, dict) or content.get("success") is not True:
        raise ValueError("Unsuccessful tool result")
    return content


def probe_catalog(branch_id: str | None = None) -> dict:
    """Read only public category data with the schema returned by this server."""
    if not CALL_LOCK.acquire(blocking=False):
        return {"ok": False, "error": "Перевірка вже триває. Дочекайтеся результату."}
    try:
        stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%f")
        trace = PublicTrace(config.TRACE_DIR / f"web-catalog-{stamp}.jsonl")
        with SilpoMCP(trace) as mcp:
            tools = mcp.list_tools()
            tool_name = "silpo_get_categories" if branch_id is not None else "silpo_list_branches"
            tool = next((t for t in tools if t.get("name") == tool_name), None)
            if not tool:
                return {"ok": False, "error": "Сервер не надав читання категорій каталогу.",
                        "tools_count": len(tools)}
            schema = tool.get("inputSchema", {})
            arguments = {"branchId": branch_id, "limit": 1000} if branch_id is not None else {"limit": 500, "hasPickup": True}
            if set(schema.get("required", [])) - set(arguments):
                return {"ok": False, "error": "Для каталогу потрібен контекст магазину або кошика. Його ще не налаштовано.",
                        "tools_count": len(tools)}
            if branch_id is not None and branch_id not in BRANCHES:
                return {"ok": False, "error": "Спочатку оберіть магазин з отриманого переліку Сільпо."}
            result = mcp.call(tool_name, arguments)
            content = unpack(result)
            key = "categories" if branch_id is not None else "branches"
            entries = content.get(key)
            if not isinstance(entries, list) or not entries:
                return {"ok": False, "error": "Каталог порожній; робочий сценарій ще не підтверджений."}
            if branch_id is None:
                # Public branch addresses only. No customer/account fields cross this boundary.
                entries = public_entries(entries, branches=True)
                BRANCHES.clear()
                BRANCHES.update({row["branchId"]: row for row in entries if row.get("branchId")})
            else:
                entries = public_entries(entries, branches=False)
            return {"ok": True, "mode": "live", "tool": tool_name,
                    "at": datetime.now(timezone.utc).isoformat(),
                    "tools_count": len(tools), "sha256": digest(result), key: entries}
    except Exception:
        # Upstream error strings can contain account data. They are never browser output.
        return {"ok": False, "error": "Не вдалося з'єднатися із Сільпо. Перевірте вхід та Інтернет; демонстраційні дані не замінюють живу відповідь."}
    finally:
        CALL_LOCK.release()


def public_products(entries: list) -> list[dict]:
    products = []
    for row in entries:
        if not isinstance(row, dict):
            raise ValueError("Invalid product")
        if not all(isinstance(row.get(k), str) and row[k].strip() for k in ("name", "slug", "displayRatio")):
            raise ValueError("Missing product label or unit")
        if not re.fullmatch(r"[a-z0-9-]+", row["slug"]):
            raise ValueError("Invalid product slug")
        price = row.get("price")
        if type(price) not in (int, float) or not math.isfinite(price) or price <= 0:
            raise ValueError("Invalid product price")
        if type(row.get("weighted")) is not bool or type(row.get("available")) is not bool:
            raise ValueError("Missing product unit or availability")
        if not row["available"]:
            continue
        # MCP price is per kilogram for weighted goods; displayPrice can be per 100g.
        products.append({"name": row["name"], "slug": row["slug"], "price": price,
                         "unit": "кг" if row["weighted"] else row["displayRatio"],
                         "weighted": row["weighted"]})
    return products


def available_pickup_slot(slots: list) -> dict | None:
    now = datetime.now(timezone.utc)
    valid = []
    for slot in slots:
        if not isinstance(slot, dict) or slot.get("available") is not True or slot.get("deliveryType") != "SelfPickup":
            continue
        try:
            start = datetime.fromisoformat(slot["start"].replace("Z", "+00:00"))
            end = datetime.fromisoformat(slot["end"].replace("Z", "+00:00"))
            if start.tzinfo and end.tzinfo and now < start < end:
                valid.append((start, {"start": slot["start"], "end": slot["end"]}))
        except (ValueError, TypeError, KeyError, AttributeError):
            continue
    return min(valid, key=lambda pair: pair[0])[1] if valid else None


def probe_potato_prices(branch_id: str) -> dict:
    if not CALL_LOCK.acquire(blocking=False):
        return {"ok": False, "error": "Перевірка вже триває. Дочекайтеся результату."}
    try:
        branch = BRANCHES.get(branch_id)
        if not branch:
            return {"ok": False, "error": "Спочатку отримайте магазини та оберіть один з них."}
        stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%f")
        with SilpoMCP(PublicTrace(config.TRACE_DIR / f"web-prices-{stamp}.jsonl")) as mcp:
            tools = {t["name"]: t for t in mcp.list_tools()}

            def read(name, arguments):
                if name not in tools or set(tools[name].get("inputSchema", {}).get("required", [])) - set(arguments):
                    raise ValueError("Read tool schema changed")
                result = mcp.call(name, arguments)
                return unpack(result), digest(result)

            categories, _ = read("silpo_get_categories", {"branchId": branch_id, "limit": 1000})
            category = next((c for c in categories["categories"] if c.get("title") == "Картопля і батат"), None)
            if not category or not isinstance(category.get("slug"), str) or not category["slug"]:
                return {"ok": False, "error": "Категорію картоплі не знайдено в отриманому каталозі."}
            slots, _ = read("silpo_get_time_slots", {"branchId": branch_id, "deliveryTypes": ["SelfPickup"], "limit": 100})
            slot = available_pickup_slot(slots["slots"])
            if not slot:
                return {"ok": False, "error": "У відповіді магазину немає доступного майбутнього вікна самовивозу для перевірки ціни."}
            data, sha = read("silpo_get_products", {"branchId": branch_id, "deliveryType": "SelfPickup",
                "timeslotStart": slot["start"], "timeslotEnd": slot["end"],
                "category": category["slug"], "inStock": True, "limit": 100})
            if not isinstance(data.get("products"), list):
                raise ValueError("Missing products")
            return {"ok": True, "mode": "live", "tool": "silpo_get_products",
                    "at": datetime.now(timezone.utc).isoformat(), "sha256": sha,
                    "branch": public_entries([branch], branches=True)[0], "slot": slot,
                    "products": public_products(data["products"])}
    except Exception:
        return {"ok": False, "error": "Ціни не вдалося підтвердити. Умовні цифри не підставляються."}
    finally:
        CALL_LOCK.release()


async def home(request: Request):
    return FileResponse(STATIC / "index.html")


async def status(request: Request):
    return JSONResponse(connection_status(), headers={"Cache-Control": "no-store"})


async def demo(request: Request):
    if request.headers.get("origin") not in (None, str(request.base_url).rstrip("/")):
        return JSONResponse({"error": "Запит з іншої сторінки відхилено."}, status_code=403)
    try:
        if len(await request.body()) > 4096:
            raise ValueError("body too large")
        plan = DemoPlan.model_validate(await request.json())
        return JSONResponse(group_preview(plan))
    except (ValueError, ValidationError):
        return JSONResponse({"error": "Перевірте кількість учасників, обсяг і граничну ціну."}, status_code=400)


async def catalog(request: Request):
    if request.headers.get("origin") not in (None, str(request.base_url).rstrip("/")):
        return JSONResponse({"error": "Запит з іншої сторінки відхилено."}, status_code=403)
    try:
        if len(await request.body()) > 4096:
            raise ValueError("body too large")
        data = await request.json()
        branch_id = data.get("branch_id")
        if not isinstance(branch_id, str) or not branch_id or len(branch_id) > 128:
            raise ValueError("invalid branch")
    except (ValueError, AttributeError):
        return JSONResponse({"ok": False, "error": "Оберіть магазин для перегляду."}, status_code=400)
    probe = probe_potato_prices if request.url.path == "/api/potato-prices" else probe_catalog
    return JSONResponse(await asyncio.to_thread(probe, branch_id), headers={"Cache-Control": "no-store"})


async def branches(request: Request):
    if request.headers.get("origin") not in (None, str(request.base_url).rstrip("/")):
        return JSONResponse({"error": "Запит з іншої сторінки відхилено."}, status_code=403)
    return JSONResponse(await asyncio.to_thread(probe_catalog), headers={"Cache-Control": "no-store"})


async def agent_demo(request: Request):
    from .shopping_agent import DemoRequest, run_demo
    if request.headers.get("origin") not in (None, str(request.base_url).rstrip("/")):
        return JSONResponse({"ok": False, "error": "Запит з іншої сторінки відхилено."}, status_code=403)
    try:
        if len(await request.body()) > 4096:
            raise ValueError("body too large")
        data = DemoRequest.model_validate(await request.json())
    except (ValueError, ValidationError):
        return JSONResponse({"ok": False, "error": "Перевірте запит покупчині."}, status_code=400)
    return JSONResponse(await asyncio.to_thread(run_demo, data), headers={"Cache-Control": "no-store"})


app = Starlette(routes=[Route("/", home), Route("/api/status", status),
    Route("/api/agent-demo", agent_demo, methods=["POST"]),
    Route("/api/demo/group", demo, methods=["POST"]),
    Route("/api/catalog", catalog, methods=["POST"]),
    Route("/api/potato-prices", catalog, methods=["POST"]),
    Route("/api/branches", branches, methods=["POST"]),
    Mount("/static", app=StaticFiles(directory=str(STATIC)))])
app.add_middleware(TrustedHostMiddleware, allowed_hosts=["127.0.0.1", "localhost", "testserver"])
