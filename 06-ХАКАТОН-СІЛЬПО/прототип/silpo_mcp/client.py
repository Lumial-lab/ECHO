"""Клієнт MCP «Сільпо» поверх Streamable HTTP.

Свідомо написаний без офіційного SDK: транспорт тут — один POST із JSON-RPC,
а натомість ми отримуємо повний контроль над тим, що потрапляє у журнал
трасувань. Для хакатону це не дрібниця: «видимі трасування викликів MCP» —
пряма вимога, і зручніше, коли слід лишає сам транспорт, а не обгортка.

Сервер відповідає або звичайним JSON, або потоком SSE (`text/event-stream`) —
обидва випадки розбираються нижче.
"""
from __future__ import annotations

import json
import time
from typing import Any

import requests

from . import config, oauth
from .trace import TraceLog


class McpError(RuntimeError):
    """Помилка рівня JSON-RPC або транспорту."""

    def __init__(self, message: str, code: int | None = None,
                 data: Any = None) -> None:
        super().__init__(message)
        self.code = code
        self.data = data


def _parse_sse(text: str) -> dict:
    """Витягує останнє повідомлення з потоку SSE."""
    payload = None
    for line in text.splitlines():
        if line.startswith("data:"):
            chunk = line[5:].strip()
            if chunk:
                payload = chunk
    if payload is None:
        raise McpError(f"порожній потік SSE: {text[:200]}")
    return json.loads(payload)


class SilpoMCP:
    """Сеанс роботи з MCP «Сільпо». Тримає сесію, токен і журнал."""

    def __init__(self, trace: TraceLog | None = None) -> None:
        self.trace = trace or TraceLog()
        self.http = requests.Session()
        self.session_id: str | None = None
        self.server_info: dict | None = None
        self._id = 0
        self._initialized = False

    # -- низький рівень --------------------------------------------------

    def _headers(self) -> dict:
        headers = {
            "Content-Type": "application/json",
            "Accept": "application/json, text/event-stream",
            "MCP-Protocol-Version": config.PROTOCOL_VERSION,
            "Authorization": f"Bearer {oauth.valid_access_token(self.trace)}",
        }
        if self.session_id:
            headers["Mcp-Session-Id"] = self.session_id
        return headers

    def _next_id(self) -> int:
        self._id += 1
        return self._id

    def _post(self, payload: dict, expect_result: bool) -> Any:
        """Надсилає JSON-RPC, переживає 401 і 429, повертає result."""
        refreshed = False
        for attempt in range(config.MAX_RETRIES):
            response = self.http.post(config.MCP_URL, headers=self._headers(),
                                      data=json.dumps(payload,
                                                      ensure_ascii=False).encode(),
                                      timeout=config.HTTP_TIMEOUT_S)

            if response.status_code == 401 and not refreshed:
                # Токен протух посеред сеансу — одна спроба поновитись мовчки.
                refreshed = True
                self.trace.record("oauth", step="refresh_on_401")
                oauth.refresh(self.trace)
                continue

            if response.status_code == 429:
                wait = _retry_after(response, attempt)
                self.trace.record("mcp_call", event="rate_limited",
                                  method=payload.get("method"), wait_s=wait)
                time.sleep(wait)
                continue

            if response.status_code >= 500:
                wait = config.BACKOFF_BASE_S ** (attempt + 1)
                time.sleep(wait)
                continue

            sid = response.headers.get("Mcp-Session-Id") or \
                response.headers.get("mcp-session-id")
            if sid:
                self.session_id = sid

            if not expect_result:
                # Сповіщення: сервер відповідає 202 без тіла.
                if response.status_code not in (200, 202, 204):
                    raise McpError(f"сповіщення відхилено: HTTP "
                                   f"{response.status_code} {response.text[:200]}")
                return None

            if response.status_code != 200:
                raise McpError(f"HTTP {response.status_code}: "
                               f"{response.text[:400]}")

            ctype = response.headers.get("Content-Type", "")
            body = _parse_sse(response.text) if "text/event-stream" in ctype \
                else response.json()

            if "error" in body:
                err = body["error"]
                raise McpError(err.get("message", "невідома помилка"),
                               err.get("code"), err.get("data"))
            return body.get("result")

        raise McpError(f"вичерпано спроби для {payload.get('method')}")

    def _request(self, method: str, params: dict | None = None) -> Any:
        payload = {"jsonrpc": "2.0", "id": self._next_id(), "method": method}
        if params is not None:
            payload["params"] = params
        return self._post(payload, expect_result=True)

    def _notify(self, method: str, params: dict | None = None) -> None:
        payload = {"jsonrpc": "2.0", "method": method}
        if params is not None:
            payload["params"] = params
        self._post(payload, expect_result=False)

    # -- рівень протоколу ------------------------------------------------

    def initialize(self) -> dict:
        if self._initialized:
            return self.server_info or {}
        started = time.time()
        result = self._request("initialize", {
            "protocolVersion": config.PROTOCOL_VERSION,
            "capabilities": {},
            "clientInfo": {"name": config.CLIENT_NAME,
                           "version": config.CLIENT_VERSION},
        })
        self._notify("notifications/initialized")
        self._initialized = True
        self.server_info = result
        self.trace.record("mcp_call", method="initialize",
                          endpoint=config.MCP_URL,
                          session_id=self.session_id,
                          server=result.get("serverInfo"),
                          protocol=result.get("protocolVersion"),
                          ms=round((time.time() - started) * 1000))
        return result

    def list_tools(self) -> list[dict]:
        self.initialize()
        tools: list[dict] = []
        cursor = None
        while True:
            params = {"cursor": cursor} if cursor else {}
            started = time.time()
            result = self._request("tools/list", params)
            page = result.get("tools", [])
            tools.extend(page)
            self.trace.record("mcp_call", method="tools/list",
                              endpoint=config.MCP_URL,
                              отримано=len(page),
                              ms=round((time.time() - started) * 1000))
            cursor = result.get("nextCursor")
            if not cursor:
                break
        return tools

    def call(self, tool: str, arguments: dict | None = None) -> dict:
        """Виклик інструмента. Кожен виклик лишає ланку в журналі доказовості."""
        self.initialize()
        arguments = arguments or {}
        started = time.time()
        try:
            result = self._request("tools/call", {"name": tool,
                                                  "arguments": arguments})
        except McpError as exc:
            self.trace.record("mcp_call", method="tools/call", tool=tool,
                              arguments=arguments, endpoint=config.MCP_URL,
                              статус="помилка", помилка=str(exc), код=exc.code,
                              ms=round((time.time() - started) * 1000))
            raise
        self.trace.record("mcp_call", method="tools/call", tool=tool,
                          arguments=arguments, endpoint=config.MCP_URL,
                          статус="успіх",
                          is_error=bool(result.get("isError")),
                          відповідь_sha256=_digest_result(result),
                          ms=round((time.time() - started) * 1000))
        return result

    # -- зручності -------------------------------------------------------

    @staticmethod
    def text_of(result: dict) -> str:
        """Збирає текстові блоки відповіді інструмента в один рядок."""
        parts = []
        for block in result.get("content", []) or []:
            if block.get("type") == "text":
                parts.append(block.get("text", ""))
        if not parts and result.get("structuredContent"):
            parts.append(json.dumps(result["structuredContent"],
                                    ensure_ascii=False, indent=2))
        return "\n".join(parts)

    def close(self) -> None:
        if self.session_id:
            try:
                self.http.delete(config.MCP_URL, headers=self._headers(),
                                 timeout=10)
            except Exception:
                pass  # сервер має право не підтримувати завершення сесії
        self.http.close()

    def __enter__(self) -> "SilpoMCP":
        return self

    def __exit__(self, *exc: Any) -> None:
        self.close()


def _retry_after(response: requests.Response, attempt: int) -> float:
    header = response.headers.get("Retry-After")
    if header:
        try:
            return float(header)
        except ValueError:
            pass
    return config.BACKOFF_BASE_S ** (attempt + 1)


def _digest_result(result: dict) -> str:
    from .trace import digest
    return digest(result)
