from web_search_agent.templates import render_envelope, render_template


def test_render_template_injects_context(fake_citations):
    deliverable = render_template(
        "brd",
        {"problem": "Slow sign-up", "goals": "Increase conversion"},
    )
    assert "Problem Statement" in deliverable
    assert "Slow sign-up" in deliverable
    assert "Goals" in deliverable


def test_render_envelope_maintains_structure(fake_citations):
    deliverable = render_template("custom", {"notes": "Custom response"})
    envelope = render_envelope(
        title="Test",
        summary="Summary section",
        deliverable=deliverable,
        sources=fake_citations,
        assumptions=["Assumption 1"],
        open_questions=["Question 1"],
        next_steps=["Step 1"],
    )

    assert envelope.startswith("# Test")
    for section in ["Metadata", "Executive Summary", "Deliverable", "Sources", "Assumptions", "Open Questions", "Next Steps"]:
        assert f"## {section}" in envelope
    assert "[Source One](http://example.com/1)" in envelope
