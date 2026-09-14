"""«Пані Одарка» — надбудова над MCP «Сільпо».

`silpo_mcp` дає доступ до даних одного гостя. `odarka` — те, чого в MCP немає
за побудовою: сукупний попит, група, представництво, правова чистота.
"""
from .tier2 import (Aggregate, AggregationRules, ConsentError, Declaration,
                    Level, LevelTotal, aggregate, negotiation_brief, raise_level)

__all__ = ["Level", "Declaration", "AggregationRules", "LevelTotal",
           "Aggregate", "aggregate", "negotiation_brief", "raise_level",
           "ConsentError"]
