"""Web search tool abstraction with pluggable transport and metadata handling."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Callable, Dict, List, Optional
import logging

logger = logging.getLogger(__name__)

SearchTransport = Callable[[str], List[Dict[str, str]]]


@dataclass
class SearchResult:
    """Structured search result with normalized fields."""

    title: str
    url: str
    snippet: str
    source_type: str = "unknown"

    @classmethod
    def from_raw(cls, raw: Dict[str, str]) -> "SearchResult":
        return cls(
            title=raw.get("title", ""),
            url=raw.get("url", ""),
            snippet=raw.get("snippet", ""),
            source_type=raw.get("source_type", "unknown"),
        )


@dataclass
class TokenUsage:
    """Token usage metrics for API calls."""
    prompt_tokens: int = 0
    completion_tokens: int = 0
    total_tokens: int = 0


@dataclass
class WebSearchResponse:
    """Structured response from web search operations."""
    results: List[SearchResult]
    query: str
    model: Optional[str] = None
    timestamp: datetime = None
    token_usage: Optional[TokenUsage] = None
    notes_for_downstream_agents: List[str] = None
    overall_confidence: Optional[str] = None
    
    def __post_init__(self):
        if self.timestamp is None:
            self.timestamp = datetime.utcnow()
        if self.notes_for_downstream_agents is None:
            self.notes_for_downstream_agents = []
    
    def to_dict(self) -> Dict:
        """Convert to dictionary for serialization."""
        return {
            "results": [
                {
                    "title": r.title,
                    "url": r.url,
                    "snippet": r.snippet,
                    "source_type": r.source_type,
                }
                for r in self.results
            ],
            "query": self.query,
            "model": self.model,
            "timestamp": self.timestamp.isoformat() if self.timestamp else None,
            "token_usage": {
                "prompt_tokens": self.token_usage.prompt_tokens if self.token_usage else 0,
                "completion_tokens": self.token_usage.completion_tokens if self.token_usage else 0,
                "total_tokens": self.token_usage.total_tokens if self.token_usage else 0,
            } if self.token_usage else None,
            "notes_for_downstream_agents": self.notes_for_downstream_agents,
            "overall_confidence": self.overall_confidence,
        }


class WebSearchTool:
    """Web search interface that can be wired to any HTTP client."""

    def __init__(self, transport: Optional[SearchTransport] = None) -> None:
        self.transport = transport or self._noop_transport

    def search(self, query: str) -> List[SearchResult]:
        """Run a search query and normalize results.

        The default transport returns an empty list, making it safe to run in
        offline environments while still exercising caching and routing logic.
        """

        try:
            raw_results = self.transport(query)
        except Exception as exc:  # pragma: no cover - depends on external transport
            logger.exception("Search transport failed for query '%s': %s", query, exc)
            raw_results = []
        return [SearchResult.from_raw(raw) for raw in raw_results]
    
    def search_with_response(self, query: str, model: Optional[str] = None, token_usage: Optional[TokenUsage] = None) -> WebSearchResponse:
        """Run a search query and return structured WebSearchResponse."""
        results = self.search(query)
        
        # Calculate overall confidence based on result count and quality
        if len(results) == 0:
            confidence = "low"
        elif len(results) < 3:
            confidence = "medium"
        else:
            confidence = "high"
        
        # Generate notes for downstream agents
        notes = []
        if len(results) == 0:
            notes.append("No search results found. Consider refining the query or checking search parameters.")
        elif len(results) < 3:
            notes.append(f"Limited results ({len(results)}). Consider expanding search terms or checking alternative sources.")
        
        return WebSearchResponse(
            results=results,
            query=query,
            model=model,
            token_usage=token_usage,
            overall_confidence=confidence,
            notes_for_downstream_agents=notes,
        )

    @staticmethod
    def _noop_transport(_: str) -> List[Dict[str, str]]:
        return []
