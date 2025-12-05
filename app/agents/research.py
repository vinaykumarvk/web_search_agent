"""Research agent prompt definitions and tool orchestration."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, List

from app.tools.web_search import SearchResult, WebSearchTool
from app.utils.cache import TTLCache


SOURCE_PREFERENCE_ORDER = [
    "primary",
    "regulator",
    "filing",
    "official",
    "analyst",
    "news",
    "community",
    "unknown",
]


@dataclass(frozen=True)
class AgentPrompts:
    """Container for system and developer messages."""

    system: str
    developer: str


RESEARCH_SYSTEM_MESSAGE = (
    "You are the research specialist. Perform multi-step web investigation, "
    "favoring authoritative sources. Always return citations for key claims and "
    "annotate uncertainty. Depth controls effort: quick=minimal searching; "
    "standard=balanced; deep=exhaustive with cross-verification." 
)

RESEARCH_DEVELOPER_MESSAGE = (
    "Use the web_search tool for evidence gathering. Cache repeated queries. "
    "Rank sources by preference (official/regulator/filing > analyst/news > "
    "community). Provide metadata suitable for bibliography construction and keep "
    "a running list of search queries issued. If the query lacks clarity, hand back "
    "to the clarifier agent instead of guessing."
)


class ResearchAgent:
    """Executes research workflows with caching and source filtering."""

    def __init__(self, search_tool: WebSearchTool, cache: TTLCache | None = None) -> None:
        self.search_tool = search_tool
        self.cache = cache or TTLCache()
        self.prompts = AgentPrompts(
            system=RESEARCH_SYSTEM_MESSAGE,
            developer=RESEARCH_DEVELOPER_MESSAGE,
        )

    def research(self, query: str, depth: str = "standard") -> Dict[str, List[SearchResult]]:
        """Run cached search and return ranked results grouped by preference."""

        cached = self.cache.get(query)
        if cached is not None:
            return cached

        raw_results = self.search_tool.search(query)
        filtered = self._filter_by_preference(raw_results)
        grouped = {
            "preferred": filtered,
            "all": raw_results,
        }
        self.cache.set(query, grouped)
        return grouped

    def _filter_by_preference(self, results: List[SearchResult]) -> List[SearchResult]:
        preference_rank = {label: index for index, label in enumerate(SOURCE_PREFERENCE_ORDER)}
        return sorted(
            results,
            key=lambda result: preference_rank.get(result.source_type, len(SOURCE_PREFERENCE_ORDER)),
        )


def build_research_prompts() -> AgentPrompts:
    """Expose research system and developer messages."""

    return AgentPrompts(system=RESEARCH_SYSTEM_MESSAGE, developer=RESEARCH_DEVELOPER_MESSAGE)
