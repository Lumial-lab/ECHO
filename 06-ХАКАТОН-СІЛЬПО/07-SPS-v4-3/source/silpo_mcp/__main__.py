"""Командний рядок клієнта MCP «Сільпо».

    python -m silpo_mcp status                    # чи все готове до входу
    python -m silpo_mcp login                     # вхід гостя (телефон + код)
    python -m silpo_mcp login --manual            # видати посилання вручну
    python -m silpo_mcp login --paste-url "..."   # завершити ручний вхід
    python -m silpo_mcp tools --grep family       # перелік інструментів
    python -m silpo_mcp call silpo_get_my_profile
    python -m silpo_mcp scenario                  # демо-сценарій Одарки
    python -m silpo_mcp trace                     # квитанція + перевірка
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import requests

from . import config, oauth
from .client import McpError, SilpoMCP
from .trace import TraceLog, receipt


def _latest_trace() -> Path | None:
    config.ensure_dirs()
    files = sorted(config.TRACE_DIR.glob("mcp-*.jsonl"))
    return files[-1] if files else None


def cmd_status(_: argparse.Namespace) -> int:
    print("Ендпоінт:", config.MCP_URL)
    try:
        r = requests.get(config.MCP_URL, timeout=20)
        print("  відповідь без токена: HTTP", r.status_code,
              "(401 - це правильно)" if r.status_code == 401 else "")
    except Exception as exc:
        print("  недосяжний:", exc)

    client = oauth.load_client()
    if client:
        print("Клієнт зареєстрований:", client["client_id"])
        print("  redirect_uris:", ", ".join(client.get("redirect_uris", [])))
    else:
        print("Клієнт ще не зареєстрований (зробиться сам при першому вході)")

    token = oauth.load_token()
    if not token:
        print("Токена немає - потрібен вхід Люміаль:"
              " python -m silpo_mcp login")
    elif oauth.token_is_fresh(token):
        print("Токен дійсний, refresh_token:",
              "є" if token.get("refresh_token") else "немає")
    else:
        print("Токен протух; поновлення",
              "можливе" if token.get("refresh_token") else "неможливе")

    trace_file = _latest_trace()
    print("Журнал трасувань:", trace_file or "ще порожній")
    print("Сховище токена:", config.TOKEN_FILE, "(поза git)")
    return 0


def cmd_login(args: argparse.Namespace) -> int:
    trace = TraceLog()
    try:
        if args.paste_url:
            token = oauth.login_from_url(args.paste_url, trace)
        elif args.manual:
            url = oauth.start_manual(trace)
            print("\nВідкрий це посилання, увійди телефоном + одноразовим кодом,")
            print("а потім скопіюй адресу, на яку тебе перекине, і виконай:")
            print('  python -m silpo_mcp login --paste-url "<та адреса>"\n')
            print(url + "\n")
            return 0
        else:
            token = oauth.login(open_browser=not args.no_browser,
                                timeout_s=args.timeout, trace=trace)
    except oauth.AuthError as exc:
        print("Вхід не вдався:", exc, file=sys.stderr)
        return 1
    print("Готово. Токен збережено в", config.TOKEN_FILE)
    print("Термін дії, с:", token.get("expires_in", "не оголошено"))
    return 0


def cmd_tools(args: argparse.Namespace) -> int:
    with SilpoMCP() as mcp:
        tools = mcp.list_tools()
    if args.grep:
        needle = args.grep.lower()
        tools = [t for t in tools
                 if needle in t["name"].lower()
                 or needle in (t.get("description") or "").lower()]
    if args.json:
        print(json.dumps(tools, ensure_ascii=False, indent=2))
        return 0
    print(f"Інструментів: {len(tools)}\n")
    for tool in tools:
        desc = (tool.get("description") or "").split("\n")[0][:90]
        print(f"  {tool['name']:<42} {desc}")
    return 0


def cmd_call(args: argparse.Namespace) -> int:
    arguments = json.loads(args.args) if args.args else {}
    with SilpoMCP() as mcp:
        try:
            result = mcp.call(args.tool, arguments)
        except McpError as exc:
            print(f"Помилка виклику {args.tool}: {exc}", file=sys.stderr)
            return 1
        print(mcp.text_of(result) or json.dumps(result, ensure_ascii=False,
                                                indent=2))
    return 0


#: Сцена 1 концепту: Одарка знайомиться з гостем, нічого не змінюючи.
#: Усі інструменти - лише читання; жодного write-виклику без згоди гостя.
SCENARIO = [
    ("silpo_get_my_profile", {}, "хто наш гість"),
    ("silpo_get_my_family", {}, "склад родини - Одарка стартує не з нуля"),
    ("silpo_get_my_food_restrictions", {}, "харчові обмеження"),
    ("silpo_get_loyalty_info", {}, "балабонуси й статус"),
    ("silpo_get_my_offline_orders", {}, "історія покупок у магазинах"),
    ("silpo_get_my_shopping_cart", {}, "чи є активний кошик"),
]


def cmd_scenario(args: argparse.Namespace) -> int:
    trace = TraceLog()
    with SilpoMCP(trace) as mcp:
        info = mcp.initialize()
        server = info.get("serverInfo", {})
        print(f"Сервер: {server.get('name')} {server.get('version')}, "
              f"протокол {info.get('protocolVersion')}\n")
        for tool, arguments, why in SCENARIO:
            print(f"── {tool}  ({why})")
            try:
                result = mcp.call(tool, arguments)
            except McpError as exc:
                print(f"   помилка: {exc}\n")
                continue
            text = mcp.text_of(result)
            print("   " + (text[:args.limit].replace("\n", "\n   ") or "(порожньо)"))
            if len(text) > args.limit:
                print(f"   … ще {len(text) - args.limit} символів")
            print()
    print(json.dumps(receipt(trace.path), ensure_ascii=False, indent=2))
    return 0


def cmd_trace(args: argparse.Namespace) -> int:
    path = Path(args.file) if args.file else _latest_trace()
    if not path or not path.exists():
        print("Журналу ще немає.")
        return 1
    print(json.dumps(receipt(path), ensure_ascii=False, indent=2))
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="silpo_mcp", description="Клієнт офіційного MCP «Сільпо»")
    sub = parser.add_subparsers(dest="cmd", required=True)

    sub.add_parser("status", help="що готове, чого бракує").set_defaults(
        func=cmd_status)

    p_login = sub.add_parser("login", help="вхід гостя через OAuth 2.1 + PKCE")
    p_login.add_argument("--manual", action="store_true",
                         help="видати посилання замість автоматичного потоку")
    p_login.add_argument("--paste-url", help="адреса повернення після входу")
    p_login.add_argument("--no-browser", action="store_true")
    p_login.add_argument("--timeout", type=int, default=300)
    p_login.set_defaults(func=cmd_login)

    p_tools = sub.add_parser("tools", help="перелік інструментів із tools/list")
    p_tools.add_argument("--grep", help="фільтр за назвою чи описом")
    p_tools.add_argument("--json", action="store_true")
    p_tools.set_defaults(func=cmd_tools)

    p_call = sub.add_parser("call", help="виклик одного інструмента")
    p_call.add_argument("tool")
    p_call.add_argument("--args", help="аргументи у JSON")
    p_call.set_defaults(func=cmd_call)

    p_scen = sub.add_parser("scenario", help="демо-сценарій знайомства Одарки")
    p_scen.add_argument("--limit", type=int, default=600,
                        help="скільки символів відповіді показувати")
    p_scen.set_defaults(func=cmd_scenario)

    p_trace = sub.add_parser("trace", help="квитанція й перевірка ланцюга")
    p_trace.add_argument("--file")
    p_trace.set_defaults(func=cmd_trace)

    args = parser.parse_args(argv)
    try:
        return args.func(args)
    except oauth.AuthError as exc:
        print("Потрібна авторизація:", exc, file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
