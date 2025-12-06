from app.runtime import ResearcherAdapter
from app.tools.web_search import WebSearchTool, SearchResult


class CountingSearchTool(WebSearchTool):
    def __init__(self):
        self.calls = []
        super().__init__(transport=self._transport)

    def _transport(self, query: str):
        self.calls.append(query)
        return [
            {
                "title": f"Title {query}",
                "url": f"https://example.com/{len(self.calls)}",
                "snippet": "Snippet",
                "source_type": "official",
            }
        ]


def test_researcher_adapter_uses_strategy_limits():
    tool = CountingSearchTool()
    adapter = ResearcherAdapter(search_tool=tool)
    dummy_request = type("Req", (), {"query": "test query", "metadata": {}})()
    dummy_decision = type("Dec", (), {"depth": "standard", "profile": "COMPANY_RESEARCH"})()
    dummy_plan = type("Plan", (), {"search_profile": "iterative_search"})()

    result = adapter.research(dummy_request, dummy_decision, dummy_plan, pass_index=0, _persisted_task=None)

    # Standard depth should generate up to 2 queries by helper, capped by strategy max_searches=4
    assert len(result["search_queries"]) == 2
    assert len(tool.calls) == 2
    assert len(result["results"]["preferred"]) <= 4


def test_researcher_adapter_uses_deep_results_from_metadata():
    deep_result = SearchResult(
        title="Deep Title",
        url="https://example.com/deep",
        snippet="Deep snippet",
        source_type="official",
    )
    adapter = ResearcherAdapter(search_tool=CountingSearchTool())
    dummy_request = type("Req", (), {"query": "test query", "metadata": {"deep_results": [deep_result]}})()
    dummy_decision = type("Dec", (), {"depth": "deep", "profile": "COMPANY_RESEARCH"})()
    dummy_plan = type("Plan", (), {"search_profile": "multi_pass_search_with_synthesis"})()

    result = adapter.research(dummy_request, dummy_decision, dummy_plan, pass_index=0, _persisted_task=None)
    assert result["results"]["preferred"] == [deep_result]
