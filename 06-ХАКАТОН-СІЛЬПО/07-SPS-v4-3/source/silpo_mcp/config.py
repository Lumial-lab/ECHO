"""Налаштування клієнта MCP «Сільпо».

Усе, що стосується адрес сервера, шляхів до секретів і журналу трасувань,
живе тут — щоб решта модулів не знала про файлову систему.
"""
from __future__ import annotations

import os
from pathlib import Path

MCP_URL = os.environ.get("SILPO_MCP_URL", "https://mcp.silpo.ua/mcp")
AS_METADATA_URL = "https://mcp.silpo.ua/.well-known/oauth-authorization-server"

# Версія протоколу, яку оголошує наш клієнт при initialize.
PROTOCOL_VERSION = "2025-06-18"

CLIENT_NAME = "Pani Odarka (hackathon prototype)"
CLIENT_VERSION = "0.1.0"

# Порт loopback-приймача коду авторизації. Він зафіксований, бо саме ці
# redirect_uri зареєстровані на сервері «Сільпо» — змінювати можна лише
# разом із повторною реєстрацією клієнта.
CALLBACK_HOST = "127.0.0.1"
CALLBACK_PORT = int(os.environ.get("SILPO_CALLBACK_PORT", "8765"))
REDIRECT_URI = f"http://{CALLBACK_HOST}:{CALLBACK_PORT}/callback"

BASE_DIR = Path(__file__).resolve().parent.parent
SECRETS_DIR = Path(os.environ.get("SILPO_SECRETS_DIR", BASE_DIR / ".secrets"))
TRACE_DIR = Path(os.environ.get("SILPO_TRACE_DIR", BASE_DIR / "трасування"))

CLIENT_FILE = SECRETS_DIR / "client.json"
TOKEN_FILE = SECRETS_DIR / "token.json"

# Скільки секунд до кінця життя токена вважати його вже протухлим.
TOKEN_EXPIRY_MARGIN_S = 60

# 429 і мережеві збої: скільки разів і з якою базою відкочуватись.
MAX_RETRIES = 5
BACKOFF_BASE_S = 1.5
HTTP_TIMEOUT_S = 60


def ensure_dirs() -> None:
    SECRETS_DIR.mkdir(parents=True, exist_ok=True)
    TRACE_DIR.mkdir(parents=True, exist_ok=True)
