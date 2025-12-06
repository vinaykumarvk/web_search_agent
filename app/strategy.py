"""Strategy matrix for web search by profile and depth."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Literal, Mapping

Profile = Literal[
    "BRD_MODELING",
    "COMPANY_RESEARCH",
    "REQUIREMENT_ELABORATION",
    "MARKET_OR_TREND_QUERY",
    "DEFINITION_OR_SIMPLE_QUERY",
]

Depth = Literal["quick", "standard", "deep"]


@dataclass(frozen=True)
class Strategy:
    model: str
    effort: str
    max_searches: int
    tools: list[str]
    recency_bias: bool = False


# Defaults; can later be overridden via config/env if desired.
STRATEGY_MATRIX: Mapping[tuple[Profile, Depth], Strategy] = {
    ("DEFINITION_OR_SIMPLE_QUERY", "quick"): Strategy(
        model="gpt-5.1", effort="low", max_searches=2, tools=["web_search"], recency_bias=True
    ),
    ("DEFINITION_OR_SIMPLE_QUERY", "standard"): Strategy(
        model="gpt-5.1", effort="medium", max_searches=3, tools=["web_search"], recency_bias=True
    ),
    ("COMPANY_RESEARCH", "quick"): Strategy(
        model="gpt-5.1", effort="low", max_searches=2, tools=["web_search"], recency_bias=True
    ),
    ("COMPANY_RESEARCH", "standard"): Strategy(
        model="gpt-5.1", effort="high", max_searches=4, tools=["web_search"], recency_bias=True
    ),
    ("COMPANY_RESEARCH", "deep"): Strategy(
        model="o3-deep-research", effort="high", max_searches=8, tools=["web_search"], recency_bias=True
    ),
    ("BRD_MODELING", "quick"): Strategy(
        model="gpt-5.1", effort="medium", max_searches=2, tools=["web_search"], recency_bias=False
    ),
    ("BRD_MODELING", "standard"): Strategy(
        model="gpt-5.1", effort="high", max_searches=4, tools=["web_search"], recency_bias=False
    ),
    ("BRD_MODELING", "deep"): Strategy(
        model="o3-deep-research", effort="high", max_searches=8, tools=["web_search"], recency_bias=False
    ),
    ("REQUIREMENT_ELABORATION", "quick"): Strategy(
        model="gpt-5.1", effort="medium", max_searches=2, tools=["web_search"], recency_bias=False
    ),
    ("REQUIREMENT_ELABORATION", "standard"): Strategy(
        model="gpt-5.1", effort="high", max_searches=3, tools=["web_search"], recency_bias=False
    ),
    ("REQUIREMENT_ELABORATION", "deep"): Strategy(
        model="o3-deep-research", effort="high", max_searches=8, tools=["web_search"], recency_bias=False
    ),
    ("MARKET_OR_TREND_QUERY", "quick"): Strategy(
        model="gpt-5.1", effort="medium", max_searches=2, tools=["web_search"], recency_bias=True
    ),
    ("MARKET_OR_TREND_QUERY", "standard"): Strategy(
        model="gpt-5.1", effort="high", max_searches=4, tools=["web_search"], recency_bias=True
    ),
    ("MARKET_OR_TREND_QUERY", "deep"): Strategy(
        model="o3-deep-research", effort="high", max_searches=8, tools=["web_search"], recency_bias=True
    ),
}


def select_strategy(profile: Profile, depth: Depth) -> Strategy:
    """Return the strategy for a given profile and depth."""

    key = (profile, depth)
    if key not in STRATEGY_MATRIX:
        # Fallback to standard depth if specific combo missing.
        key = (profile, "standard")
    return STRATEGY_MATRIX[key]
