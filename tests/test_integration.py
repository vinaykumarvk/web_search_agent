from web_search_agent.citations import has_complete_citations
from web_search_agent.fakes import FakeDeepResearchClient


def test_deep_research_flow(deep_research_client: FakeDeepResearchClient, sample_queries):
    create_response = deep_research_client.create_task(sample_queries["company"], depth_hint="deep")
    assert create_response["status"] == "queued"

    task_state = deep_research_client.retrieve_task(create_response["id"])
    assert task_state["status"] == "completed"

    envelope = task_state["response"]
    for section in ["Metadata", "Executive Summary", "Deliverable", "Sources", "Assumptions", "Open Questions", "Next Steps"]:
        assert f"## {section}" in envelope

    assert "Deep research on" in envelope
    assert has_complete_citations(envelope.split("## Assumptions", 1)[0].split("## Sources\n", 1)[1])
    for citation in task_state["citations"]:
        assert citation.title in envelope
        assert citation.url in envelope
