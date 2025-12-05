import pytest

from web_search_agent.citations import Citation
from web_search_agent.fakes import FakeDeepResearchClient, FakeSearchProvider


@pytest.fixture()
def sample_queries():
    return {
        "brd": "Write a BRD for launching a new payments API",
        "company": "Research the company 'ExampleCorp' recent announcements",
        "market": "Market analysis for urban delivery startups",
    }


@pytest.fixture()
def fake_sources():
    return [
        {"title": "Source One", "url": "http://example.com/1", "snippet": "First result"},
        {"title": "Source Two", "url": "http://example.com/2", "snippet": "Second result"},
    ]


@pytest.fixture()
def fake_citations(fake_sources):
    return [Citation(**source) for source in fake_sources]


@pytest.fixture()
def deep_research_client(fake_sources):
    provider = FakeSearchProvider(fake_sources)
    return FakeDeepResearchClient(provider)
