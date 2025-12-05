from web_search_agent.models import SourceType
from web_search_agent.search_ranking import SearchResult, rank_search_results


def test_source_preference_order_and_filtering():
    results = [
        SearchResult(
            title="Regulator filing",
            url="https://gov.example/filing",
            snippet="Primary disclosure",
            source_type=SourceType.OFFICIAL,
            base_score=0.6,
        ),
        SearchResult(
            title="News coverage",
            url="https://news.example/story",
            snippet="Reporting",
            source_type=SourceType.REPORTING,
            base_score=0.9,
        ),
        SearchResult(
            title="Community forum",
            url="https://forum.example/post",
            snippet="Anecdote",
            source_type=SourceType.COMMUNITY,
            base_score=0.95,
        ),
    ]

    ranked = rank_search_results(results, disallowed_types=[SourceType.COMMUNITY])
    assert [result.title for result in ranked] == ["News coverage", "Regulator filing"]

    assert ranked[0].weighted_score() > ranked[1].weighted_score()
    assert all(result.source_type is not SourceType.COMMUNITY for result in ranked)
