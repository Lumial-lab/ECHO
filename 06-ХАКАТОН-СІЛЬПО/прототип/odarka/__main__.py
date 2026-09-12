"""Демонстрація другого ярусу.

    python -m odarka demo

Сценарій — той, що назвала Люміаль: картопля на зиму, де для колективного
споживача ціна фіксується як оптова, а до групи приєднується малий бізнес.
Показує рівно те, що відрізняє нас від звичайного маркетплейс-асистента:
рівні попиту не змішуються, група не видає учасника, а звернення до «Сільпо» —
запрошення, не набір умов замість них.
"""
from __future__ import annotations

import argparse
from datetime import date

from .tier2 import (AggregationRules, Declaration, Level, aggregate,
                    negotiation_brief)

HORIZON = date(2026, 12, 15)


def _winter_potatoes() -> list[Declaration]:
    """Шість родин і дві кав'ярні — правдоподібна, а не кругла картина."""
    people = [
        # Одарка вивела з історії покупок: це ще лише прогноз, не слова гостя.
        Declaration("родина-1", "картопля", 60, Level.FORECAST, HORIZON,
                    derived=True),
        Declaration("родина-2", "картопля", 40, Level.FORECAST, HORIZON,
                    derived=True),
        # Гості відгукнулись: «потенційно цікаво».
        Declaration("родина-1", "картопля", 50, Level.INTEREST, HORIZON),
        Declaration("родина-3", "картопля", 45, Level.INTEREST, HORIZON),
        Declaration("родина-4", "картопля", 30, Level.INTEREST, HORIZON),
        # Умовна готовність: «візьму, якщо не дорожче».
        Declaration("родина-2", "картопля", 80, Level.INTENT, HORIZON,
                    max_price=14.50),
        Declaration("родина-5", "картопля", 60, Level.INTENT, HORIZON,
                    max_price=13.90),
        Declaration("родина-6", "картопля", 40, Level.INTENT, HORIZON,
                    max_price=15.00),
        Declaration("кавʼярня-Зерно", "картопля", 120, Level.INTENT, HORIZON,
                    max_price=14.00, business=True),
        Declaration("кавʼярня-Пласт", "картопля", 90, Level.INTENT, HORIZON,
                    max_price=14.20, business=True),
    ]
    return people


def cmd_demo(args: argparse.Namespace) -> int:
    rules = AggregationRules(min_clients=args.min_clients,
                             max_single_share=args.max_share)
    items = _winter_potatoes()

    print("СЦЕНА 7 — ДРУГИЙ ЯРУС: картопля на зиму\n")
    print(f"Волевиявлень: {len(items)} від "
          f"{len({d.client_id for d in items})} клієнтів")
    print(f"Пороги: не менше {rules.min_clients} осіб, "
          f"частка найбільшого — до {rules.max_single_share:.0%}\n")

    agg = aggregate(items, "картопля", rules)
    print(negotiation_brief(agg))

    print("\n" + "─" * 68)
    print("А тепер те саме, але група мала — троє сусідів:\n")
    small = [d for d in items if d.client_id in
             {"родина-1", "родина-2", "родина-3"}]
    print(negotiation_brief(aggregate(small, "картопля", rules)))

    print("\n" + "─" * 68)
    print("І випадок, коли група є, але одна кавʼярня дає більшість обсягу:\n")
    skewed = [d for d in items if not d.business and d.level is Level.INTENT]
    skewed.append(Declaration("кавʼярня-Зерно", "картопля", 4000, Level.INTENT,
                              HORIZON, max_price=13.00, business=True))
    skewed += [Declaration(f"родина-{i}", "картопля", 20, Level.INTENT, HORIZON,
                           max_price=15.0) for i in range(7, 10)]
    print(negotiation_brief(aggregate(skewed, "картопля", rules)))
    print("\nГрупа формально є, але за числами впізнати кавʼярню — тривіально.")
    print("Тому не показуємо нічого: це і є професійна таємниця на практиці.")
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="odarka", description="Другий ярус: сукупний попит і представництво")
    sub = parser.add_subparsers(dest="cmd", required=True)
    p_demo = sub.add_parser("demo", help="сценарій «картопля на зиму»")
    p_demo.add_argument("--min-clients", type=int, default=5)
    p_demo.add_argument("--max-share", type=float, default=0.5)
    p_demo.set_defaults(func=cmd_demo)
    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
