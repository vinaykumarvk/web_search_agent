from app.runtime import ResearcherAdapter
from app.tools.deep_research import MockDeepResearchClient
from app.tools.web_search import WebSearchTool


class NoopSearchTool(WebSearchTool):
    def __init__(self):
        super().__init__(transport=lambda q: [])


def test_deep_research_strategy_uses_deep_client():
    deep_client = MockDeepResearchClient()
    adapter = ResearcherAdapter(search_tool=NoopSearchTool(), deep_client=deep_client)
    dummy_request = type("Req", (), {"query": "deep topic", "metadata": {}})()
    dummy_decision = type("Dec", (), {"depth": "deep", "profile": "COMPANY_RESEARCH"})()
    dummy_plan = type("Plan", (), {"search_profile": "multi_pass_search_with_synthesis"})()

    result = adapter.research(dummy_request, dummy_decision, dummy_plan, pass_index=0, _persisted_task=None)

    assert deep_client.calls == ["deep topic"]
    assert result["results"]["preferred"]
    assert result["model"] == "o3-deep-research"
