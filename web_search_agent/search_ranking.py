from dataclasses import dataclass
from typing import Iterable, List, Optional, Sequence

from .models import SourceType

SOURCE_WEIGHTS = {
    SourceType.OFFICIAL: 1.25,
    SourceType.REPORTING: 1.0,
    SourceType.COMMUNITY: 0.7,
    SourceType.UNKNOWN: 0.6,
}

PREFERENCE_BONUS = {
    SourceType.OFFICIAL: 0.15,
    SourceType.REPORTING: 0.05,
    SourceType.COMMUNITY: -0.05,
    SourceType.UNKNOWN: -0.1,
}


@dataclass
class SearchResult:
    title: str
    url: str
    snippet: str
    source_type: SourceType = SourceType.UNKNOWN
    base_score: float = 1.0

    def weighted_score(self) -> float:
        weight = SOURCE_WEIGHTS.get(self.source_type, SOURCE_WEIGHTS[SourceType.UNKNOWN])
        bonus = PREFERENCE_BONUS.get(self.source_type, 0)
        return (self.base_score * weight) + bonus


def rank_search_results(
    results: Iterable[SearchResult],
    disallowed_types: Optional[Sequence[SourceType]] = None,
) -> List[SearchResult]:
    """
    Rank search results by applying source-preference filtering and weighting.

    Args:
        results: iterable of SearchResult items.
        disallowed_types: source categories that should be removed entirely.

    Returns:
        List of SearchResult ordered by source preference and weighted score.
    """

    disallowed_set = set(disallowed_types or [])
    filtered_results = [
        result for result in results if result.source_type not in disallowed_set
    ]

    return sorted(filtered_results, key=lambda result: result.weighted_score(), reverse=True)
