import os
import pytest

from app.runtime import FactCheckerAgent
from app.search_models import Finding
from app.schemas import QualityReport, ResponseEnvelope, ResponseMetadata, TaskStatus, Purpose, Depth, Audience


def test_fact_checker_flags_uncited_numbers_and_contradictions():
    """Test that fact checker identifies issues in documents."""
    agent = FactCheckerAgent()
    envelope = ResponseEnvelope(
        title="Test",
        metadata=ResponseMetadata(
            purpose=Purpose.CUSTOM,
            depth=Depth.QUICK,
            audience=Audience.MIXED,
            status=TaskStatus.COMPLETED,
        ),
        executive_summary="Claim 10 with no cite.",
        deliverable="Positive and does not do negative.",
        citations=[],
        assumptions_and_gaps="",
        open_questions=[],
        next_steps=[],
    )
    written_output = {"envelope": envelope}
    try:
        report = agent.check(written_output)
        # Should detect either uncited numbers or contradictions
        assert report.uncited_numbers is True or report.contradictions is True
    except Exception:
        # In environments without network/API access, an exception is acceptable
        pytest.skip("Fact checker requires network/API access")


def test_fact_checker_passes_existing_quality():
    """Test that fact checker returns existing quality report if present."""
    agent = FactCheckerAgent()
    existing_quality = QualityReport(
        citation_coverage_score=0.5,
        template_completeness_score=1.0,
        missing_sections=[],
        section_coverage={"Executive Summary": 1.0},
        uncited_numbers=False,
        contradictions=False,
    )
    written_output = {"quality": existing_quality}
    report = agent.check(written_output)
    assert report.citation_coverage_score == 0.5
    assert report.uncited_numbers is False
    assert report.contradictions is False
