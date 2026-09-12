"""Тести другого ярусу.

Кожен тест відповідає вимозі концепту, а не примсі реалізації — тому в назвах
саме вимоги: рівні не змішуються, система не вирішує за клієнта, група не
видає учасника.

    python test_tier2.py
"""
from __future__ import annotations

import sys
import unittest
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from odarka import (Aggregate, AggregationRules, ConsentError, Declaration,
                    Level, aggregate, negotiation_brief, raise_level)

HORIZON = date(2026, 12, 1)


def decl(client: str, units: int, level: Level = Level.INTEREST, **kw) -> Declaration:
    if level is Level.INTENT:
        kw.setdefault("max_price", 18.0)
    if level is Level.COMMITMENT:
        kw.setdefault("program_id", "prog-1")
    return Declaration(client_id=client, category="картопля", units=units,
                       level=level, horizon=HORIZON, **kw)


def group(n: int, units: int = 100, level: Level = Level.INTEREST) -> list[Declaration]:
    return [decl(f"c{i}", units, level) for i in range(n)]


class TestLevelsDoNotMix(unittest.TestCase):
    """§17: «Ці рівні не можна змішувати.»"""

    def test_each_level_is_counted_separately(self):
        items = (group(3, 100, Level.FORECAST)
                 + group(3, 50, Level.INTEREST)
                 + [decl(f"i{i}", 20, Level.INTENT) for i in range(3)])
        agg = aggregate(items, "картопля", AggregationRules(min_clients=5))
        self.assertTrue(agg.disclosable, agg.withheld_reason)
        self.assertEqual(agg.total(Level.FORECAST), 300)
        self.assertEqual(agg.total(Level.INTEREST), 150)
        self.assertEqual(agg.total(Level.INTENT), 60)
        self.assertEqual(agg.total(Level.COMMITMENT), 0)

    def test_aggregate_has_no_single_total(self):
        # Найважливіше тут — відсутність: числа «весь попит» не існує.
        self.assertFalse(hasattr(Aggregate, "total_units"))
        agg = aggregate(group(6), "картопля")
        self.assertNotIn("total_units", vars(agg))

    def test_brief_states_that_levels_do_not_add_up(self):
        items = group(5, 100, Level.INTEREST) + [decl(f"i{i}", 40, Level.INTENT)
                                                 for i in range(3)]
        text = negotiation_brief(aggregate(items, "картопля"))
        self.assertIn("не підсумовуються", text)
        self.assertIn("заявлений інтерес", text)
        self.assertIn("підтверджений намір", text)


class TestSystemDoesNotDecideForClient(unittest.TestCase):
    """§18: Одарка аналізує, але не створює зобов'язання сама."""

    def test_derived_record_can_only_be_a_forecast(self):
        Declaration("c1", "картопля", 10, Level.FORECAST, HORIZON, derived=True)
        for level in (Level.INTEREST, Level.INTENT, Level.COMMITMENT):
            with self.assertRaises(ConsentError):
                Declaration("c1", "картопля", 10, level, HORIZON,
                            derived=True, max_price=18.0, program_id="p")

    def test_intent_requires_a_price_condition(self):
        with self.assertRaises(ConsentError):
            Declaration("c1", "картопля", 10, Level.INTENT, HORIZON)

    def test_commitment_requires_a_program(self):
        with self.assertRaises(ConsentError):
            Declaration("c1", "картопля", 10, Level.COMMITMENT, HORIZON)

    def test_raising_level_clears_derived_flag(self):
        forecast = Declaration("c1", "картопля", 10, Level.FORECAST, HORIZON,
                               derived=True)
        intent = raise_level(forecast, Level.INTENT, max_price=17.5)
        self.assertIs(intent.level, Level.INTENT)
        self.assertFalse(intent.derived)
        self.assertEqual(intent.max_price, 17.5)

    def test_level_cannot_be_lowered_silently(self):
        intent = decl("c1", 10, Level.INTENT)
        with self.assertRaises(ConsentError):
            raise_level(intent, Level.INTEREST)
        with self.assertRaises(ConsentError):
            raise_level(intent, Level.INTENT)

    def test_declaration_is_immutable(self):
        d = decl("c1", 10)
        with self.assertRaises(Exception):
            d.units = 999  # type: ignore[misc]


class TestGroupDoesNotExposeAnyone(unittest.TestCase):
    """§23: агрегований попит не повинен дозволяти впізнати клієнта."""

    def test_small_group_discloses_nothing(self):
        agg = aggregate(group(3), "картопля", AggregationRules(min_clients=5))
        self.assertFalse(agg.disclosable)
        self.assertEqual(agg.by_level, {})
        self.assertIn("поріг знеособлення", agg.withheld_reason)

    def test_dominant_participant_blocks_disclosure(self):
        # Кав'ярня з 8000 од. серед п'ятьох — формально група, фактично одна особа.
        items = group(4, 100) + [decl("cafe", 8000, business=True)]
        agg = aggregate(items, "картопля", AggregationRules(min_clients=5))
        self.assertFalse(agg.disclosable)
        self.assertIn("знеособлена", agg.withheld_reason)

    def test_withheld_brief_shows_reason_and_no_numbers(self):
        agg = aggregate(group(2), "картопля")
        text = negotiation_brief(agg)
        self.assertIn("не розкриваються", text)
        self.assertNotIn("100", text)

    def test_volume_threshold_set_by_silpo(self):
        agg = aggregate(group(6, 10), "картопля",
                        AggregationRules(min_clients=5, min_units=1000))
        self.assertFalse(agg.disclosable)
        self.assertIn("«Сільпо»", agg.withheld_reason)

    def test_rules_reject_degenerate_group(self):
        with self.assertRaises(ValueError):
            AggregationRules(min_clients=1)


class TestBusinessAndBrief(unittest.TestCase):
    """§4 уточнень: до групи приєднується малий бізнес."""

    def test_businesses_are_counted_visibly(self):
        items = group(5, 100) + [decl("cafe1", 150, business=True),
                                 decl("cafe2", 150, business=True)]
        agg = aggregate(items, "картопля")
        self.assertTrue(agg.disclosable, agg.withheld_reason)
        self.assertEqual(agg.by_level[Level.INTEREST].businesses, 2)
        self.assertIn("малий бізнес", negotiation_brief(agg))

    def test_price_ceiling_is_the_strictest_of_participants(self):
        items = group(5, 100) + [
            decl("i1", 40, Level.INTENT, max_price=20.0),
            decl("i2", 40, Level.INTENT, max_price=16.5),
            decl("i3", 40, Level.INTENT, max_price=18.0),
        ]
        agg = aggregate(items, "картопля")
        self.assertEqual(agg.by_level[Level.INTENT].price_ceiling, 16.5)
        self.assertIn("16.50", negotiation_brief(agg))

    def test_brief_invites_rather_than_dictates(self):
        # Тон заданий уточненням Люміаль: запрошення, а не умови замість «Сільпо».
        text = negotiation_brief(aggregate(group(6), "картопля"))
        self.assertIn("Які умови «Сільпо» може запропонувати", text)
        self.assertNotIn("повинен", text)

    def test_other_categories_are_not_pulled_in(self):
        items = group(6) + [Declaration("x1", "яблука", 500, Level.INTEREST,
                                        HORIZON)]
        agg = aggregate(items, "картопля")
        self.assertEqual(agg.total(Level.INTEREST), 600)

    def test_empty_input_is_handled(self):
        agg = aggregate([], "картопля")
        self.assertFalse(agg.disclosable)
        self.assertIn("немає волевиявлень", agg.withheld_reason)


if __name__ == "__main__":
    unittest.main(verbosity=2)
