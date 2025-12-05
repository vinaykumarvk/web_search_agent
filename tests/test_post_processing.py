import math

from web_search_agent.post_processing import evaluate_report_sections, summarize_coverage_by_section


def test_evaluates_citation_and_template_scores():
    sections = {
        "Executive Summary": "Short setup. Claim with cite [1]. Another claim without cite.",
        "Deliverable": "Finding one [2]. Finding two [3].",
        "Assumptions": "",
    }
    required = ["Executive Summary", "Deliverable", "Assumptions"]

    evaluation = evaluate_report_sections(sections, required)

    # Executive Summary: 3 sentences, 1 citation => coverage 1/3
    # Deliverable: 2 sentences, 2 citations => coverage 1.0
    # Total claims = 5, covered = 3 => coverage score 0.6
    assert math.isclose(evaluation.citation_coverage_score, 0.6)
    assert math.isclose(evaluation.template_completeness_score, 2 / 3)
    assert evaluation.missing_sections == ["Assumptions"]

    coverage = summarize_coverage_by_section(evaluation.section_evaluations)
    assert math.isclose(coverage["Executive Summary"], 1 / 3)
    assert math.isclose(coverage["Deliverable"], 1.0)
