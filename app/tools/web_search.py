"""Web search tool abstraction with pluggable transport and metadata handling."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Callable, Dict, List, Optional

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


class WebSearchTool:
    """Web search interface that can be wired to any HTTP client."""

    def __init__(self, transport: Optional[SearchTransport] = None) -> None:
        self.transport = transport or self._noop_transport

    def search(self, query: str) -> List[SearchResult]:
        """Run a search query and normalize results.

        The default transport returns an empty list, making it safe to run in
        offline environments while still exercising caching and routing logic.
        """

        raw_results = self.transport(query)
        return [SearchResult.from_raw(raw) for raw in raw_results]

    @staticmethod
    def _noop_transport(_: str) -> List[Dict[str, str]]:
        return []
