import sys
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from app.templates import render  # noqa: E402


def test_render_document_injects_deliverable_content():
    base_fields = {
        "title": "Test BRD",
        "depth": "deep",
        "audience": "exec",
        "region_timeframe": "global",
        "executive_summary": "Summary text",
        "sources": "- Source A",
        "assumptions_gaps": "None",
        "next_steps": "Do more",
    }

    deliverable_fields = {
        "problem_statement": "Problem",
        "goals": "Goals",
        "target_users": "Users",
        "scope": "Scope",
        "requirements": "Requirements",
        "success_metrics": "KPIs",
        "risks_mitigations": "Risks",
        "timeline": "Timeline",
    }

    document = render.render_document("brd", base_fields, deliverable_fields)

    assert "## Deliverable" in document
    assert "## BRD Outline" in document
    assert "Problem Statement" in document
    assert "Summary text" in document


def test_missing_deliverable_section_raises_error():
    base_fields = {
        "title": "Test BRD",
        "depth": "deep",
        "audience": "exec",
        "region_timeframe": "global",
        "executive_summary": "Summary text",
        "sources": "- Source A",
        "assumptions_gaps": "None",
        "next_steps": "Do more",
    }

    deliverable_fields = {
        "problem_statement": "Problem",
        "goals": "Goals",
        "target_users": "Users",
        # missing scope
        "requirements": "Requirements",
        "success_metrics": "KPIs",
        "risks_mitigations": "Risks",
        "timeline": "Timeline",
    }

    with pytest.raises(render.MissingSectionError):
        render.render_document("brd", base_fields, deliverable_fields)


def test_missing_base_section_raises_error():
    base_fields = {
        "title": "Test BRD",
        "depth": "deep",
        "audience": "exec",
        "region_timeframe": "global",
        # missing executive_summary
        "sources": "- Source A",
        "assumptions_gaps": "None",
        "next_steps": "Do more",
    }

    deliverable_fields = {
        "problem_statement": "Problem",
        "goals": "Goals",
        "target_users": "Users",
        "scope": "Scope",
        "requirements": "Requirements",
        "success_metrics": "KPIs",
        "risks_mitigations": "Risks",
        "timeline": "Timeline",
    }

    with pytest.raises(render.MissingSectionError):
        render.render_document("brd", base_fields, deliverable_fields)
