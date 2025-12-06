"""Research agent prompt definitions and tool orchestration."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, List

from web_search_agent.models import SourceType
from web_search_agent.search_ranking import SearchResult as RankedResult
from web_search_agent.search_ranking import rank_search_results

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

    def research(self, query: str, depth: str = "standard", max_calls: int | None = None) -> Dict[str, List[SearchResult]]:
        """Run cached search and return ranked results grouped by preference."""

        cached = self.cache.get(query)
        if cached is not None:
            return cached

        raw_results = self.search_tool.search(query)
        if max_calls is not None:
            raw_results = raw_results[:max_calls]
        filtered = self._filter_by_preference(raw_results)
        ranked = self._rank(filtered)
        grouped = {
            "preferred": ranked,
            "all": raw_results,
        }
        self.cache.set(query, grouped)
        return grouped
    
    def research_with_response(self, query: str, depth: str = "standard", max_calls: int | None = None, model: Optional[str] = None) -> tuple[Dict[str, List[SearchResult]], Optional["WebSearchResponse"]]:
        """Run cached search and return both grouped results and WebSearchResponse.
        
        Returns:
            Tuple of (grouped_results, web_search_response)
        """
        from app.tools.web_search import WebSearchResponse, TokenUsage
        
        cached = self.cache.get(query)
        if cached is not None:
            # Return cached results with a minimal WebSearchResponse
            return cached, WebSearchResponse(
                results=cached.get("preferred", []),
                query=query,
                model=model,
                overall_confidence="medium",
                notes_for_downstream_agents=["Results from cache"],
            )

        # Use search_with_response to get structured response
        web_response = self.search_tool.search_with_response(query, model=model)
        raw_results = web_response.results
        
        if max_calls is not None:
            raw_results = raw_results[:max_calls]
            web_response.results = raw_results
        
        filtered = self._filter_by_preference(raw_results)
        ranked = self._rank(filtered)
        grouped = {
            "preferred": ranked,
            "all": raw_results,
        }
        self.cache.set(query, grouped)
        
        # Update response with ranked results
        web_response.results = ranked
        
        return grouped, web_response

    def _filter_by_preference(self, results: List[SearchResult]) -> List[SearchResult]:
        preference_rank = {label: index for index, label in enumerate(SOURCE_PREFERENCE_ORDER)}
        return sorted(
            results,
            key=lambda result: preference_rank.get(result.source_type, len(SOURCE_PREFERENCE_ORDER)),
        )

    @staticmethod
    def _rank(results: List[SearchResult]) -> List[SearchResult]:
        """Apply source-type weighting to order results."""

        def to_ranked(result: SearchResult) -> RankedResult:
            source_type = getattr(SourceType, result.source_type.upper(), SourceType.UNKNOWN)
            return RankedResult(
                title=result.title,
                url=result.url,
                snippet=result.snippet,
                source_type=source_type,
            )

        ranked = rank_search_results([to_ranked(res) for res in results])
        # Convert back to the lightweight SearchResult dataclass
        return [
            SearchResult(title=item.title, url=item.url, snippet=item.snippet, source_type=item.source_type.value)
            for item in ranked
        ]


def build_research_prompts() -> AgentPrompts:
    """Expose research system and developer messages."""

    return AgentPrompts(system=RESEARCH_SYSTEM_MESSAGE, developer=RESEARCH_DEVELOPER_MESSAGE)
