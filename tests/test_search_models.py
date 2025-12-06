from app.search_models import Finding, WebSearchRequest, WebSearchResponse
from app.search_models import Evidence


def test_web_search_request_defaults():
    req = WebSearchRequest(query="Test query")
    assert req.depth == "standard"
    assert req.profile is None


def test_finding_and_response_shape():
    finding = Finding(
        id="F1",
        title="Source Title",
        source_url="https://example.com",
        snippet="Excerpt",
        key_points=["Point 1"],
    )
    evidence = Evidence(
        id="E1",
        claim="Point 1",
        excerpt="Excerpt",
        source_id="F1",
        source_url="https://example.com",
    )
    resp = WebSearchResponse(
        profile="COMPANY_RESEARCH",
        depth="standard",
        summary="Summary text",
        findings=[finding],
        overall_confidence="medium",
        notes_for_downstream_agents=["Note"],
        source_map={"F1": "https://example.com"},
    )
    assert resp.profile == "COMPANY_RESEARCH"
    assert resp.findings[0].id == "F1"
    assert resp.source_map["F1"] == "https://example.com"
    assert evidence.source_id == "F1"
