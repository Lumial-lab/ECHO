"""OAuth 2.1 + PKCE для MCP «Сільпо».

Потік рівно такий, як описаний у документації «Сільпо»:
динамічна реєстрація клієнта → PKCE-пара → /authorize у браузері →
вхід гостя на auth.silpo.ua → код повертається на loopback →
обмін коду на MCP-токен → далі клієнт сам поновлюється через refresh_token.

Що тут важливо для нашої правової позиції: Silpo JWT гостя ми не бачимо
ніколи. У нас лише MCP-токен, і він лежить на боці сервера (файл у .secrets,
поза git), як вимагають правила хакатону.
"""
from __future__ import annotations

import base64
import hashlib
import json
import os
import secrets
import threading
import time
import urllib.parse
import webbrowser
from http.server import BaseHTTPRequestHandler, HTTPServer
from typing import Any

import requests

from . import config
from .trace import TraceLog


class AuthError(RuntimeError):
    pass


# -- метадані та реєстрація ---------------------------------------------

def fetch_metadata() -> dict:
    r = requests.get(config.AS_METADATA_URL, timeout=config.HTTP_TIMEOUT_S)
    r.raise_for_status()
    return r.json()


def load_client() -> dict | None:
    if config.CLIENT_FILE.exists():
        return json.loads(config.CLIENT_FILE.read_text(encoding="utf-8"))
    return None


def register_client(meta: dict, trace: TraceLog | None = None) -> dict:
    """Динамічна реєстрація (RFC 7591). Робиться один раз, без участі гостя."""
    payload = {
        "client_name": config.CLIENT_NAME,
        "redirect_uris": [
            config.REDIRECT_URI,
            f"http://localhost:{config.CALLBACK_PORT}/callback",
        ],
        "grant_types": ["authorization_code", "refresh_token"],
        "response_types": ["code"],
        "token_endpoint_auth_method": "none",
        "application_type": "native",
    }
    r = requests.post(meta["registration_endpoint"], json=payload,
                      timeout=config.HTTP_TIMEOUT_S)
    if r.status_code not in (200, 201):
        raise AuthError(f"реєстрація не вдалась: HTTP {r.status_code} {r.text[:300]}")
    client = r.json()
    config.ensure_dirs()
    _write_private(config.CLIENT_FILE, client)
    if trace:
        trace.record("oauth", step="register", client_id=client.get("client_id"),
                     redirect_uris=client.get("redirect_uris"))
    return client


def ensure_client(trace: TraceLog | None = None) -> tuple[dict, dict]:
    meta = fetch_metadata()
    client = load_client() or register_client(meta, trace)
    return meta, client


# -- PKCE ---------------------------------------------------------------

def _pkce_pair() -> tuple[str, str]:
    verifier = base64.urlsafe_b64encode(os.urandom(64)).decode().rstrip("=")
    challenge = base64.urlsafe_b64encode(
        hashlib.sha256(verifier.encode()).digest()
    ).decode().rstrip("=")
    return verifier, challenge


# -- loopback-приймач коду ----------------------------------------------

class _CallbackHandler(BaseHTTPRequestHandler):
    result: dict[str, Any] = {}

    def do_GET(self) -> None:  # noqa: N802 - назву диктує базовий клас
        parsed = urllib.parse.urlparse(self.path)
        if parsed.path not in ("/callback", "/"):
            self.send_response(404)
            self.end_headers()
            return
        params = {k: v[0] for k, v in urllib.parse.parse_qs(parsed.query).items()}
        _CallbackHandler.result = params
        ok = "code" in params
        inner = (
            "<h2>Готово</h2><p>Пані Одарка отримала доступ. "
            "Можна закрити вкладку й повернутись у застосунок.</p>"
            if ok else
            f"<h2>Не вдалося</h2><pre>{params}</pre>"
        )
        body = (
            '<meta charset="utf-8"><body style="font:16px/1.5 system-ui;'
            'padding:3rem;max-width:34rem;margin:auto">' + inner + "</body>"
        )
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.end_headers()
        self.wfile.write(body.encode("utf-8"))

    def log_message(self, *args: Any) -> None:
        pass  # тиша: свій слід ми пишемо у власний журнал


def _serve_until(server: HTTPServer, timeout_s: int) -> None:
    deadline = time.time() + timeout_s
    while time.time() < deadline and not _CallbackHandler.result:
        server.handle_request()


def _wait_for_code(timeout_s: int) -> dict:
    _CallbackHandler.result = {}
    server = HTTPServer((config.CALLBACK_HOST, config.CALLBACK_PORT),
                        _CallbackHandler)
    server.timeout = 1
    thread = threading.Thread(target=_serve_until, args=(server, timeout_s),
                              daemon=True)
    thread.start()
    thread.join(timeout_s + 2)
    server.server_close()
    return _CallbackHandler.result


# -- основний потік -----------------------------------------------------

def login(open_browser: bool = True, timeout_s: int = 300,
          trace: TraceLog | None = None) -> dict:
    """Повний потік авторизації гостя. Повертає збережений токен."""
    trace = trace or TraceLog()
    meta, client = ensure_client(trace)
    verifier, challenge = _pkce_pair()
    state = secrets.token_urlsafe(24)

    query = {
        "response_type": "code",
        "client_id": client["client_id"],
        "redirect_uri": config.REDIRECT_URI,
        "code_challenge": challenge,
        "code_challenge_method": "S256",
        "state": state,
        "resource": "https://mcp.silpo.ua",
    }
    auth_url = meta["authorization_endpoint"] + "?" + urllib.parse.urlencode(query)
    trace.record("oauth", step="authorize_open",
                 client_id=client["client_id"], challenge_method="S256")

    print("\n  Відкрий у браузері й увійди телефоном + одноразовим кодом:\n")
    print("  " + auth_url + "\n")
    if open_browser:
        try:
            webbrowser.open(auth_url)
        except Exception:
            pass

    params = _wait_for_code(timeout_s)
    if not params:
        raise AuthError(
            "код авторизації не надійшов за відведений час. "
            "Якщо браузер відкривався на іншій машині - скопіюй адресу, на яку "
            "тебе перекинуло (http://127.0.0.1:8765/callback?...), і передай її "
            "в `python -m silpo_mcp login --paste-url ...`."
        )
    return _finish(meta, client, params, verifier, state, trace)


def start_manual(trace: TraceLog | None = None) -> str:
    """Готує посилання й відкладає PKCE-верифікатор для ручного завершення."""
    trace = trace or TraceLog()
    meta, client = ensure_client(trace)
    verifier, challenge = _pkce_pair()
    state = secrets.token_urlsafe(24)
    _write_private(config.SECRETS_DIR / "pending.json",
                   {"verifier": verifier, "state": state})
    query = {
        "response_type": "code",
        "client_id": client["client_id"],
        "redirect_uri": config.REDIRECT_URI,
        "code_challenge": challenge,
        "code_challenge_method": "S256",
        "state": state,
        "resource": "https://mcp.silpo.ua",
    }
    return meta["authorization_endpoint"] + "?" + urllib.parse.urlencode(query)


def login_from_url(redirect_url: str, trace: TraceLog | None = None) -> dict:
    """Запасний шлях: гість вручну приносить адресу, на яку його перекинуло.

    Потрібен, коли браузер відкривається не на тій машині, де працює клієнт.
    Верифікатор PKCE у цьому разі лежить у .secrets/pending.json.
    """
    trace = trace or TraceLog()
    pending_file = config.SECRETS_DIR / "pending.json"
    if not pending_file.exists():
        raise AuthError("немає незавершеного входу: спершу запусти `login --manual`")
    pending = json.loads(pending_file.read_text(encoding="utf-8"))
    meta, client = ensure_client(trace)
    query = urllib.parse.urlparse(redirect_url).query
    params = {k: v[0] for k, v in urllib.parse.parse_qs(query).items()}
    token = _finish(meta, client, params, pending["verifier"], pending["state"], trace)
    pending_file.unlink(missing_ok=True)
    return token


def _finish(meta: dict, client: dict, params: dict, verifier: str,
            state: str, trace: TraceLog) -> dict:
    if params.get("error"):
        raise AuthError(f"сервер відмовив: {params['error']} "
                        f"{params.get('error_description', '')}")
    if params.get("state") != state:
        raise AuthError("state не збігається - відповідь могла бути підмінена")
    code = params.get("code")
    if not code:
        raise AuthError(f"у відповіді немає коду: {params}")

    data = {
        "grant_type": "authorization_code",
        "code": code,
        "redirect_uri": config.REDIRECT_URI,
        "client_id": client["client_id"],
        "code_verifier": verifier,
        "resource": "https://mcp.silpo.ua",
    }
    if client.get("client_secret"):
        data["client_secret"] = client["client_secret"]
    r = requests.post(meta["token_endpoint"], data=data,
                      timeout=config.HTTP_TIMEOUT_S)
    if r.status_code != 200:
        raise AuthError(f"обмін коду не вдався: HTTP {r.status_code} {r.text[:300]}")
    token = _store_token(r.json())
    trace.record("oauth", step="token_issued",
                 expires_in=token.get("expires_in"),
                 has_refresh=bool(token.get("refresh_token")),
                 scope=token.get("scope"))
    return token


def refresh(trace: TraceLog | None = None) -> dict:
    token = load_token()
    if not token or not token.get("refresh_token"):
        raise AuthError("немає refresh_token - потрібен повторний вхід гостя")
    meta, client = ensure_client(trace)
    data = {
        "grant_type": "refresh_token",
        "refresh_token": token["refresh_token"],
        "client_id": client["client_id"],
        "resource": "https://mcp.silpo.ua",
    }
    if client.get("client_secret"):
        data["client_secret"] = client["client_secret"]
    r = requests.post(meta["token_endpoint"], data=data,
                      timeout=config.HTTP_TIMEOUT_S)
    if r.status_code != 200:
        raise AuthError(f"поновлення не вдалось: HTTP {r.status_code} {r.text[:300]}")
    fresh = r.json()
    # Сервер може не повернути новий refresh_token - тоді лишається старий.
    fresh.setdefault("refresh_token", token["refresh_token"])
    new = _store_token(fresh)
    if trace:
        trace.record("oauth", step="token_refreshed",
                     expires_in=new.get("expires_in"))
    return new


# -- сховище токена -----------------------------------------------------

def _write_private(path, payload: dict) -> None:
    config.ensure_dirs()
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2),
                    encoding="utf-8")
    try:
        os.chmod(path, 0o600)
    except OSError:
        pass  # Windows: права керуються ACL теки .secrets


def _store_token(raw: dict) -> dict:
    token = dict(raw)
    if "expires_in" in token:
        token["expires_at"] = time.time() + float(token["expires_in"])
    _write_private(config.TOKEN_FILE, token)
    return token


def load_token() -> dict | None:
    if config.TOKEN_FILE.exists():
        return json.loads(config.TOKEN_FILE.read_text(encoding="utf-8"))
    return None


def token_is_fresh(token: dict | None) -> bool:
    if not token or not token.get("access_token"):
        return False
    exp = token.get("expires_at")
    if exp is None:
        return True  # сервер не оголосив термін - вважаємо дійсним до 401
    return time.time() < exp - config.TOKEN_EXPIRY_MARGIN_S


def valid_access_token(trace: TraceLog | None = None) -> str:
    token = load_token()
    if token_is_fresh(token):
        return token["access_token"]
    if token and token.get("refresh_token"):
        return refresh(trace)["access_token"]
    raise AuthError("немає дійсного токена - потрібен `python -m silpo_mcp login`")
