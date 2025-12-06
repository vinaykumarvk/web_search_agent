from dataclasses import dataclass
import re
from typing import Dict, Iterable, List, Sequence


@dataclass
class SectionEvaluation:
    section_name: str
    claim_count: int
    citation_count: int
    coverage_ratio: float


@dataclass
class TemplateEvaluation:
    section_evaluations: List[SectionEvaluation]
    citation_coverage_score: float
    template_completeness_score: float
    missing_sections: List[str]
    has_uncited_numbers: bool = False
    has_contradictions: bool = False


def _estimate_claims(text: str) -> int:
    sentences = [segment.strip() for segment in re.split(r"[.!?]+", text) if segment.strip()]
    return len(sentences)


def _count_citations(text: str) -> int:
    bracketed = re.findall(r"\[[^\]]+\]", text)
    parenthetical = re.findall(r"\([^)]*?\)", text)
    return len(bracketed) + len(parenthetical)


def _has_numbers_without_citations(text: str) -> bool:
    """Detect numeric tokens lacking nearby citations."""

    sentences = [segment.strip() for segment in re.split(r"[.!?]+", text) if segment.strip()]
    for sentence in sentences:
        has_number = bool(re.search(r"\d", sentence))
        has_citation = bool(re.search(r"\[[^\]]+\]|\([^)]*?\)", sentence))
        if has_number and not has_citation:
            return True
    return False


def _has_simple_contradictions(text: str) -> bool:
    """Detect simple contradictory phrasing heuristically."""

    lowered = text.lower()
    contradictory_pairs = [
        ("not available", "available"),
        ("no evidence", "evidence"),
        ("does not", "does"),
    ]
    return any(a in lowered and b in lowered for a, b in contradictory_pairs)


def evaluate_report_sections(
    sections: Dict[str, str], required_sections: Sequence[str]
) -> TemplateEvaluation:
    """
    Evaluate a rendered report by checking template completeness and citation coverage.

    Args:
        sections: Mapping of section titles to their rendered text.
        required_sections: Names of sections that must be present and non-empty.

    Returns:
        TemplateEvaluation summarizing per-section coverage, overall citation coverage,
        and template completeness.
    """

    section_evaluations: List[SectionEvaluation] = []
    total_claims = 0
    total_cited_claims = 0

    for name, text in sections.items():
        claims = _estimate_claims(text)
        citations = _count_citations(text)
        covered_claims = min(citations, claims)
        coverage_ratio = (covered_claims / claims) if claims else 0.0
        total_claims += claims
        total_cited_claims += covered_claims
        section_evaluations.append(
            SectionEvaluation(
                section_name=name,
                claim_count=claims,
                citation_count=citations,
                coverage_ratio=coverage_ratio,
            )
        )

    citation_coverage_score = (total_cited_claims / total_claims) if total_claims else 0.0

    missing_sections = [
        section for section in required_sections if not sections.get(section, "").strip()
    ]
    template_completeness_score = (
        (len(required_sections) - len(missing_sections)) / len(required_sections)
        if required_sections
        else 1.0
    )

    evaluation = TemplateEvaluation(
        section_evaluations=section_evaluations,
        citation_coverage_score=citation_coverage_score,
        template_completeness_score=template_completeness_score,
        missing_sections=missing_sections,
    )

    evaluation.has_uncited_numbers = any(
        _has_numbers_without_citations(text) for text in sections.values()
    )
    evaluation.has_contradictions = any(
        _has_simple_contradictions(text) for text in sections.values()
    )

    return evaluation


def summarize_coverage_by_section(section_evaluations: Iterable[SectionEvaluation]) -> Dict[str, float]:
    """Convert a list of section evaluations into a lookup of coverage ratios."""

    return {evaluation.section_name: evaluation.coverage_ratio for evaluation in section_evaluations}
