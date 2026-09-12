"""Тести клієнта MCP «Сільпо» — без мережі й без токена Люміаль.

Перевіряють рівно те, що вранці не має підвести: розбір SSE, пагінацію
tools/list, тихе поновлення токена на 401, відкат на 429, і найголовніше —
що ланцюг трасувань ловить підміну запису.

    python test_silpo_mcp.py
"""
from __future__ import annotations

import json
import os
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

_TMP = tempfile.mkdtemp(prefix="silpo-test-")
os.environ["SILPO_SECRETS_DIR"] = str(Path(_TMP) / "secrets")
os.environ["SILPO_TRACE_DIR"] = str(Path(_TMP) / "trace")

from silpo_mcp import client as client_mod  # noqa: E402
from silpo_mcp import config, oauth, trace  # noqa: E402


class FakeResponse:
    def __init__(self, status: int, body: object = None,
                 headers: dict | None = None, ctype: str = "application/json"):
        self.status_code = status
        self.headers = {"Content-Type": ctype, **(headers or {})}
        if isinstance(body, str):
            self.text = body
            self._json = None
        else:
            self.text = json.dumps(body or {}, ensure_ascii=False)
            self._json = body

    def json(self):
        return self._json if self._json is not None else json.loads(self.text)


class FakeHttp:
    """Підміна requests.Session: віддає заготовлені відповіді по черзі."""

    def __init__(self, script: list[FakeResponse]):
        self.script = list(script)
        self.sent: list[dict] = []
        self.headers_seen: list[dict] = []

    def post(self, url, headers=None, data=None, timeout=None):
        self.sent.append(json.loads(data.decode()) if data else {})
        self.headers_seen.append(dict(headers or {}))
        return self.script.pop(0)

    def delete(self, *a, **kw):
        return FakeResponse(200)

    def close(self):
        pass


def _rpc(result: object, rid: int = 1) -> FakeResponse:
    return FakeResponse(200, {"jsonrpc": "2.0", "id": rid, "result": result})


def _make_client(script: list[FakeResponse]) -> client_mod.SilpoMCP:
    mcp = client_mod.SilpoMCP(trace.TraceLog(Path(_TMP) / "t.jsonl"))
    mcp.http = FakeHttp(script)
    # initialize вже пройдено: тести цілять у поведінку транспорту
    mcp._initialized = True
    mcp.server_info = {}
    return mcp


class TestTraceChain(unittest.TestCase):
    def setUp(self):
        self.path = Path(_TMP) / f"chain-{self.id().split('.')[-1]}.jsonl"
        self.path.unlink(missing_ok=True)

    def test_chain_is_verifiable(self):
        log = trace.TraceLog(self.path)
        log.record("mcp_call", tool="silpo_get_my_profile", статус="успіх")
        log.record("mcp_call", tool="silpo_get_my_family", статус="успіх")
        ok, note = trace.verify_chain(self.path)
        self.assertTrue(ok, note)
        self.assertIn("2 записів", note)

    def test_tampering_is_detected(self):
        log = trace.TraceLog(self.path)
        log.record("mcp_call", tool="silpo_get_loyalty_info", сума=10)
        log.record("mcp_call", tool="silpo_get_my_profile")
        lines = self.path.read_text(encoding="utf-8").splitlines()
        first = json.loads(lines[0])
        first["сума"] = 9999  # хтось переписав історію
        lines[0] = json.dumps(first, ensure_ascii=False)
        self.path.write_text("\n".join(lines) + "\n", encoding="utf-8")
        ok, note = trace.verify_chain(self.path)
        self.assertFalse(ok)
        self.assertIn("#1", note)

    def test_deleted_link_breaks_chain(self):
        log = trace.TraceLog(self.path)
        for i in range(3):
            log.record("mcp_call", tool=f"t{i}")
        lines = self.path.read_text(encoding="utf-8").splitlines()
        del lines[1]  # ланку вирізано
        self.path.write_text("\n".join(lines) + "\n", encoding="utf-8")
        ok, _ = trace.verify_chain(self.path)
        self.assertFalse(ok)

    def test_secrets_never_reach_the_log(self):
        log = trace.TraceLog(self.path)
        log.record("oauth", step="token_issued",
                   access_token="дуже-таємний", nested={"refresh_token": "теж"})
        body = self.path.read_text(encoding="utf-8")
        self.assertNotIn("дуже-таємний", body)
        self.assertNotIn("теж", body)
        self.assertIn("приховано", body)

    def test_receipt_counts_tools(self):
        log = trace.TraceLog(self.path)
        log.record("mcp_call", method="tools/call", tool="silpo_get_my_profile")
        log.record("mcp_call", method="tools/call", tool="silpo_get_my_profile")
        log.record("mcp_call", method="tools/call", tool="silpo_get_my_family")
        r = trace.receipt(self.path)
        self.assertEqual(r["викликів_інструментів"], 3)
        self.assertEqual(r["інструменти"]["silpo_get_my_profile"], 2)
        self.assertTrue(r["ланцюг_цілий"])


class TestTransport(unittest.TestCase):
    def setUp(self):
        # Токен «дійсний» — щоб _headers не ходив у мережу.
        oauth._store_token({"access_token": "test-token", "expires_in": 3600,
                            "refresh_token": "test-refresh"})

    def test_sse_response_is_parsed(self):
        sse = ('event: message\n'
               'data: {"jsonrpc":"2.0","id":1,"result":{"tools":[]}}\n\n')
        mcp = _make_client([FakeResponse(200, sse, ctype="text/event-stream")])
        self.assertEqual(mcp.list_tools(), [])

    def test_tools_list_follows_pagination(self):
        mcp = _make_client([
            _rpc({"tools": [{"name": "a"}], "nextCursor": "c1"}),
            _rpc({"tools": [{"name": "b"}]}),
        ])
        names = [t["name"] for t in mcp.list_tools()]
        self.assertEqual(names, ["a", "b"])

    def test_session_id_is_remembered(self):
        mcp = _make_client([
            _rpc({"tools": []}, 1),
            _rpc({"tools": []}, 2),
        ])
        mcp.http.script[0].headers["Mcp-Session-Id"] = "sess-42"
        mcp.list_tools()
        mcp.list_tools()
        self.assertEqual(mcp.session_id, "sess-42")
        self.assertEqual(mcp.http.headers_seen[-1]["Mcp-Session-Id"], "sess-42")

    def test_401_triggers_single_refresh_and_retry(self):
        calls = {"n": 0}

        def fake_refresh(_trace=None):
            calls["n"] += 1
            return oauth._store_token({"access_token": "fresh",
                                       "expires_in": 3600,
                                       "refresh_token": "test-refresh"})

        original = oauth.refresh
        client_mod.oauth.refresh = fake_refresh
        try:
            mcp = _make_client([FakeResponse(401), _rpc({"tools": []})])
            mcp.list_tools()
        finally:
            client_mod.oauth.refresh = original
        self.assertEqual(calls["n"], 1)
        self.assertEqual(mcp.http.headers_seen[-1]["Authorization"],
                         "Bearer fresh")

    def test_429_backs_off_then_succeeds(self):
        slept: list[float] = []
        original_sleep = client_mod.time.sleep
        client_mod.time.sleep = slept.append
        try:
            mcp = _make_client([
                FakeResponse(429, {}, {"Retry-After": "2"}),
                _rpc({"tools": [{"name": "ok"}]}),
            ])
            tools = mcp.list_tools()
        finally:
            client_mod.time.sleep = original_sleep
        self.assertEqual(slept, [2.0])
        self.assertEqual(tools[0]["name"], "ok")

    def test_jsonrpc_error_is_raised_and_logged(self):
        mcp = _make_client([FakeResponse(200, {
            "jsonrpc": "2.0", "id": 1,
            "error": {"code": -32601, "message": "Method not found"}})])
        with self.assertRaises(client_mod.McpError) as ctx:
            mcp.call("silpo_get_my_profile")
        self.assertEqual(ctx.exception.code, -32601)
        body = mcp.trace.path.read_text(encoding="utf-8")
        self.assertIn("silpo_get_my_profile", body)

    def test_call_is_traced_with_digest(self):
        mcp = _make_client([_rpc({"content": [{"type": "text",
                                               "text": "Наталія"}]})])
        result = mcp.call("silpo_get_my_profile")
        self.assertEqual(mcp.text_of(result), "Наталія")
        last = json.loads(mcp.trace.path.read_text(
            encoding="utf-8").strip().splitlines()[-1])
        self.assertEqual(last["tool"], "silpo_get_my_profile")
        self.assertEqual(len(last["відповідь_sha256"]), 64)

    def test_notification_accepts_202(self):
        mcp = _make_client([FakeResponse(202)])
        mcp._notify("notifications/initialized")  # не має кинути


class TestPkceAndConfig(unittest.TestCase):
    def test_pkce_pair_is_valid_s256(self):
        import base64
        import hashlib
        verifier, challenge = oauth._pkce_pair()
        expected = base64.urlsafe_b64encode(
            hashlib.sha256(verifier.encode()).digest()).decode().rstrip("=")
        self.assertEqual(challenge, expected)
        self.assertGreaterEqual(len(verifier), 43)
        self.assertLessEqual(len(verifier), 128)
        self.assertNotIn("=", challenge)

    def test_state_mismatch_is_rejected(self):
        with self.assertRaises(oauth.AuthError) as ctx:
            oauth._finish({}, {"client_id": "x"},
                          {"code": "abc", "state": "чуже"},
                          "verifier", "наше", trace.TraceLog(Path(_TMP) / "s.jsonl"))
        self.assertIn("state", str(ctx.exception))

    def test_expired_token_is_not_fresh(self):
        self.assertFalse(oauth.token_is_fresh(
            {"access_token": "a", "expires_at": 0}))
        self.assertTrue(oauth.token_is_fresh(
            {"access_token": "a", "expires_at": 2 ** 31}))
        self.assertFalse(oauth.token_is_fresh(None))

    def test_redirect_uri_matches_registered_port(self):
        self.assertEqual(config.REDIRECT_URI,
                         f"http://127.0.0.1:{config.CALLBACK_PORT}/callback")


if __name__ == "__main__":
    unittest.main(verbosity=2)
