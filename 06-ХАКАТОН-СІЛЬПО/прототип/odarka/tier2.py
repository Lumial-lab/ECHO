"""Другий ярус: сукупний попит і представництво.

Те, чого в MCP «Сільпо» немає за побудовою — і не повинно бути. MCP дає повний
інструментарій для ОДНОГО гостя. Наша цінність починається там, де він
закінчується: тривалі відносини, майбутній попит, група, право.

Модуль реалізує §17-19 концепту, і головна вимога там — не технічна, а правова:

    «Ці рівні не можна змішувати.»

Прогноз, заявлений інтерес, підтверджений намір і договірне зобов'язання —
різні за юридичною вагою речі. Змішати їх в одне число означало б принести
«Сільпо» цифру, за якою нічого не стоїть, і підставити і клієнтів, і адвокатку.
Тому агрегат тут структурно не вміє їх додавати: кожен рівень рахується окремо,
і тип підсумку це показує.

Друга вимога — §23: агрегований попит не повинен дозволяти впізнати клієнта.
Порога «не менше k осіб» для цього мало: якщо одна кав'ярня дала 80% обсягу,
група знеособлена лише на папері. Тому є і поріг частки найбільшого учасника.

Чого тут свідомо НЕМАЄ: конкретних значень порогів груп і обсягів — їх за
концептом визначає «Сільпо»; і конфігурації забезпечення (завдаток) — її
визначає адвокатка при узгодженні економічної частини. Код дає механізм і
місця для цих рішень, а не приймає їх замість людей.
"""
from __future__ import annotations

import enum
from dataclasses import dataclass, field
from datetime import date
from typing import Iterable


class Level(enum.IntEnum):
    """Чотири рівні §17. Порядок значущий: вище — юридично вагоміше."""

    FORECAST = 1           # прогноз: система припускає, що потреба виникне
    INTEREST = 2           # заявлений інтерес: «мені це потенційно цікаво»
    INTENT = 3             # підтверджений намір: «готовий купити, якщо умова»
    COMMITMENT = 4         # договірне зобов'язання: умови програми прийнято

    @property
    def title(self) -> str:
        return {
            Level.FORECAST: "прогноз",
            Level.INTEREST: "заявлений інтерес",
            Level.INTENT: "підтверджений намір",
            Level.COMMITMENT: "договірне зобов'язання",
        }[self]


class ConsentError(ValueError):
    """Порушення правил волевиявлення: спроба вирішити за клієнта."""


@dataclass(frozen=True)
class Declaration:
    """Одне волевиявлення одного клієнта щодо однієї категорії.

    `derived` означає «отримано з історії покупок, а не зі слів клієнта».
    Такий запис має право бути лише прогнозом: система може припускати, але
    не може заявляти інтерес від імені людини.
    """

    client_id: str
    category: str
    units: int
    level: Level
    horizon: date
    max_price: float | None = None      # «якщо буде не дорожче, ніж…»
    derived: bool = False               # виведено системою, не заявлено гостем
    program_id: str | None = None       # для рівня 4: яка саме програма
    business: bool = False              # малий бізнес (кав'ярні тощо), §4 уточнень

    def __post_init__(self) -> None:
        if self.units <= 0:
            raise ValueError("обсяг має бути додатним")
        if self.derived and self.level is not Level.FORECAST:
            raise ConsentError(
                f"виведений із історії запис не може мати рівень «{self.level.title}» — "
                "підвищити рівень може лише сам клієнт")
        if self.level is Level.INTENT and self.max_price is None:
            raise ConsentError(
                "підтверджений намір без граничної ціни беззмістовний: "
                "намір завжди умовний («готовий купити, якщо…»)")
        if self.level is Level.COMMITMENT and not self.program_id:
            raise ConsentError(
                "договірне зобов'язання має посилатись на конкретну програму закупівлі")


@dataclass(frozen=True)
class AggregationRules:
    """Пороги знеособлення й публікації.

    Значення за замовчуванням — обережні, не «правильні»: за концептом розміри
    груп і обсяги за кожною категорією визначає «Сільпо», а поріг знеособлення —
    наша зона відповідальності перед клієнтами.
    """

    min_clients: int = 5                 # менше — не показуємо нічого
    max_single_share: float = 0.5        # частка найбільшого учасника в обсязі
    min_units: int = 0                   # мінімальний обсяг, якщо його ставить «Сільпо»

    def __post_init__(self) -> None:
        if self.min_clients < 2:
            raise ValueError("група з однієї особи — це не група, а клієнт")
        if not 0 < self.max_single_share <= 1:
            raise ValueError("частка найбільшого учасника має бути в (0, 1]")


@dataclass
class LevelTotal:
    """Підсумок ОДНОГО рівня. Окремий тип, щоб рівні не злипались у число."""

    level: Level
    units: int = 0
    clients: int = 0
    businesses: int = 0
    price_ceiling: float | None = None   # найнижча з граничних цін учасників

    @property
    def title(self) -> str:
        return self.level.title


@dataclass
class Aggregate:
    """Знеособлена картина попиту по одній категорії.

    Свідомо не має властивості «загальний обсяг»: такого числа не існує —
    є чотири різні числа з різною юридичною вагою.
    """

    category: str
    horizon: date
    by_level: dict[Level, LevelTotal] = field(default_factory=dict)
    disclosable: bool = False
    withheld_reason: str | None = None

    def total(self, level: Level) -> int:
        entry = self.by_level.get(level)
        return entry.units if entry else 0

    def clients(self, level: Level) -> int:
        entry = self.by_level.get(level)
        return entry.clients if entry else 0


def _people(n: int) -> str:
    """«1 особа», «3 особи», «5 осіб» — звіт читає людина, не машина."""
    tail, hundred = n % 10, n % 100
    if tail == 1 and hundred != 11:
        form = "особа"
    elif tail in (2, 3, 4) and hundred not in (12, 13, 14):
        form = "особи"
    else:
        form = "осіб"
    return f"{n} {form}"


def aggregate(declarations: Iterable[Declaration], category: str,
              rules: AggregationRules | None = None) -> Aggregate:
    """Зводить волевиявлення однієї категорії у знеособлену картину.

    Якщо група не проходить пороги — повертається порожній агрегат із
    поясненням причини. Саме порожній, а не «приблизний»: показати частину
    чисел для групи з трьох осіб означало б видати цих трьох.
    """
    rules = rules or AggregationRules()
    items = [d for d in declarations if d.category == category]

    if not items:
        return Aggregate(category, date.today(), {}, False, "немає волевиявлень")

    horizon = max(d.horizon for d in items)
    unique_clients = {d.client_id for d in items}
    total_units = sum(d.units for d in items)

    if len(unique_clients) < rules.min_clients:
        return Aggregate(category, horizon, {}, False,
                         f"у групі {_people(len(unique_clients))}, "
                         f"поріг знеособлення — {_people(rules.min_clients)}")

    per_client: dict[str, int] = {}
    for d in items:
        per_client[d.client_id] = per_client.get(d.client_id, 0) + d.units
    top_share = max(per_client.values()) / total_units
    if top_share > rules.max_single_share:
        return Aggregate(category, horizon, {}, False,
                         f"один учасник дає {top_share:.0%} обсягу — група знеособлена "
                         f"лише формально (поріг {rules.max_single_share:.0%})")

    if total_units < rules.min_units:
        return Aggregate(category, horizon, {}, False,
                         f"сукупний обсяг {total_units} менший за поріг "
                         f"{rules.min_units}, який визначив «Сільпо»")

    by_level: dict[Level, LevelTotal] = {}
    for level in Level:
        subset = [d for d in items if d.level is level]
        if not subset:
            continue
        ceilings = [d.max_price for d in subset if d.max_price is not None]
        by_level[level] = LevelTotal(
            level=level,
            units=sum(d.units for d in subset),
            clients=len({d.client_id for d in subset}),
            businesses=len({d.client_id for d in subset if d.business}),
            price_ceiling=min(ceilings) if ceilings else None,
        )

    return Aggregate(category, horizon, by_level, True, None)


def negotiation_brief(agg: Aggregate) -> str:
    """Текст звернення до «Сільпо» — §19 концепту.

    Тон заданий уточненням Люміаль: це ЗАПРОШЕННЯ до співпраці, а не набір
    умов замість «Сільпо». Тому текст називає стан попиту й питає про умови,
    а не диктує їх.
    """
    if not agg.disclosable:
        return (f"Категорія «{agg.category}»: дані не розкриваються. "
                f"Причина: {agg.withheld_reason}.")

    lines = [f"Категорія «{agg.category}», горизонт до {agg.horizon:%d.%m.%Y}.", ""]
    for level in Level:
        entry = agg.by_level.get(level)
        if not entry:
            continue
        line = f"  {entry.title}: {entry.units} од. від {entry.clients} клієнтів"
        if entry.businesses:
            line += f" (з них {entry.businesses} — малий бізнес)"
        if entry.price_ceiling is not None:
            line += f", за ціни не вище {entry.price_ceiling:.2f} грн"
        lines.append(line)

    intent = agg.by_level.get(Level.INTENT)
    lines += ["", "Ці чотири величини мають різну юридичну вагу і не підсумовуються."]
    if intent:
        lines.append(
            f"Підтверджений намір на {intent.units} од. означає готовність взяти "
            f"визначені зобов'язання за умови ціни не вище "
            f"{intent.price_ceiling:.2f} грн." if intent.price_ceiling is not None
            else f"Підтверджений намір на {intent.units} од. є умовним.")
    lines.append("Які умови «Сільпо» може запропонувати цій групі споживачів?")
    return "\n".join(lines)


def raise_level(previous: Declaration, level: Level, *,
                max_price: float | None = None,
                program_id: str | None = None) -> Declaration:
    """Підвищення рівня — завжди явна дія клієнта, ніколи не висновок системи.

    Окрема функція існує саме для того, щоб підвищення не можна було зробити
    «між іншим», мутувавши запис: Declaration заморожений, а тут є перевірки.
    """
    if level <= previous.level:
        raise ConsentError(
            f"рівень можна лише підвищувати: «{previous.level.title}» → "
            f"«{level.title}» не є підвищенням")
    return Declaration(
        client_id=previous.client_id,
        category=previous.category,
        units=previous.units,
        level=level,
        horizon=previous.horizon,
        max_price=max_price if max_price is not None else previous.max_price,
        derived=False,  # заявив клієнт, тож запис більше не є виведеним
        program_id=program_id or previous.program_id,
        business=previous.business,
    )
