from web_search_agent.models import CitationMetadata, SourceType


def test_citation_metadata_bibliography_rendering():
    citation = CitationMetadata(
        citation_id="1",
        title="Annual Report",
        url="https://example.com/report.pdf",
        source_type=SourceType.OFFICIAL,
        publisher="Example Corp",
        published_at="2024-02-15",
        accessed_at="2024-03-01",
        annotation="Primary source for revenue figures.",
    )

    label = citation.bibliography_label()
    assert "[1] Annual Report" in label
    assert "Example Corp" in label

    entry = citation.to_bibliography_entry()
    assert entry["source_type"] == "official"
    assert entry["publisher"] == "Example Corp"
    assert entry["accessed_at"] == "2024-03-01"
