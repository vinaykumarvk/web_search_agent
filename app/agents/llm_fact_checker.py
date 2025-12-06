"""LLM-based fact checker using GPT-5.1 for contradiction and citation analysis."""
from __future__ import annotations

import json
import logging
import os
from typing import Any, Dict, List, Optional

try:
    from openai import OpenAI  # type: ignore
except Exception:  # pragma: no cover - optional dependency
    OpenAI = None  # type: ignore

from app.observability import MetricsEmitter
from app.utils.semantic_citation import SemanticCitationValidator
from app.utils.reasoning_verbosity import build_reasoning_verbosity_params
from app.schemas import QualityReport
from web_search_agent.post_processing import evaluate_report_sections, summarize_coverage_by_section

logger = logging.getLogger(__name__)

DEFAULT_FACT_CHECK_MODEL = "gpt-5.1"


class LLMFactCheckerAgent:
    """GPT-5.1-powered fact checker for contradiction detection and citation validation."""

    def __init__(
        self,
        model: Optional[str] = None,
        api_key: Optional[str] = None,
        metrics_emitter: Optional[Any] = None,
        strict_mode: bool = False,
    ) -> None:
        self.model = model or os.environ.get("OPENAI_FACT_CHECK_MODEL", DEFAULT_FACT_CHECK_MODEL)
        self.api_key = api_key or os.environ.get("OPENAI_API_KEY")
        self.metrics = metrics_emitter or MetricsEmitter()
        self.strict_mode = strict_mode
        self.citation_validator = SemanticCitationValidator(
            model=self.model,
            api_key=self.api_key,
            strict_mode=strict_mode,
        )
        if OpenAI is None:
            logger.warning("OpenAI package not available; LLM fact checker will not function")
            self.client = None
        else:
            self.client = OpenAI(api_key=self.api_key) if self.api_key else None

    def check(self, written_output: Dict[str, Any], effort: str = "high", depth: str = "standard") -> QualityReport:
        """Perform LLM-based fact checking on the written output.
        
        Analyzes:
        - Logical contradictions
        - Citation quality and coverage
        - Uncited numerical claims
        - Missing sections
        
        If written_output already contains a QualityReport, returns it directly.
        """
        # Check if quality report already exists (from template writer evaluation)
        quality = written_output.get("quality")
        if isinstance(quality, QualityReport):
            return quality
        
        # Handle duck-typed quality objects
        if quality and all(hasattr(quality, attr) for attr in ("citation_coverage_score", "template_completeness_score")):
            return QualityReport(
                citation_coverage_score=getattr(quality, "citation_coverage_score", 0.0),
                template_completeness_score=getattr(quality, "template_completeness_score", 0.0),
                missing_sections=getattr(quality, "missing_sections", []) or [],
                section_coverage=getattr(quality, "section_coverage", {}) or {},
                uncited_numbers=getattr(quality, "uncited_numbers", False),
                contradictions=getattr(quality, "contradictions", False),
            )
        
        envelope = written_output.get("envelope")
        if not envelope:
            return QualityReport(
                citation_coverage_score=0.0,
                template_completeness_score=0.0,
                missing_sections=["Executive Summary", "Deliverable"],
                section_coverage={},
                uncited_numbers=True,
                contradictions=True,
            )

        if not self.client:
            raise RuntimeError("OpenAI client not available for fact checker")

        # Extract document content
        document_text = self._extract_document_text(envelope)
        citations = getattr(envelope, "citations", []) or []
        
        # Build analysis prompt
        system_prompt = (
            "You are an expert fact-checker and quality analyst. Analyze documents for:\n"
            "1. Logical contradictions (statements that conflict with each other)\n"
            "2. Citation quality (are claims properly cited?)\n"
            "3. Uncited numerical claims (numbers without citations)\n"
            "4. Missing or incomplete sections\n\n"
            "Return a JSON object with your analysis."
        )
        
        user_prompt = self._build_analysis_prompt(document_text, citations, written_output)

        try:
            response = self.client.responses.create(
                model=self.model,
                input=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt},
                ],
                max_output_tokens=2000,
                temperature=0.2,
            )
            
            # Extract and emit token usage metrics
            if self.metrics and hasattr(response, "usage"):
                usage = response.usage
                self.metrics.emit_token_usage(
                    stage="fact_checker",
                    prompt_tokens=getattr(usage, "prompt_tokens", 0),
                    completion_tokens=getattr(usage, "completion_tokens", 0),
                    model=self.model,
                )
            
            analysis_text = getattr(response, "output_text", "") or "{}"
            analysis = json.loads(analysis_text)
            
            return self._parse_analysis(analysis, envelope, written_output)
            
        except Exception as exc:
            logger.exception("LLM fact checking failed: %s", exc)
            if self.metrics:
                self.metrics.emit_fact_checker_unavailable()
            raise

    def _extract_document_text(self, envelope: Any) -> str:
        """Extract full document text from envelope."""
        parts = []
        if hasattr(envelope, "executive_summary"):
            parts.append(f"Executive Summary:\n{envelope.executive_summary}\n")
        if hasattr(envelope, "deliverable"):
            parts.append(f"Deliverable:\n{envelope.deliverable}\n")
        if hasattr(envelope, "assumptions_and_gaps"):
            parts.append(f"Assumptions & Gaps:\n{envelope.assumptions_and_gaps}\n")
        if hasattr(envelope, "open_questions"):
            questions = getattr(envelope, "open_questions", []) or []
            if questions:
                parts.append(f"Open Questions:\n" + "\n".join(f"- {q}" for q in questions) + "\n")
        return "\n".join(parts)

    def _build_analysis_prompt(self, document_text: str, citations: List[Any], written_output: Dict[str, Any]) -> str:
        """Build prompt for LLM fact checking."""
        citation_info = []
        for i, citation in enumerate(citations, 1):
            title = getattr(citation, "source", "") or citation.get("title", "") if isinstance(citation, dict) else ""
            url = getattr(citation, "url", "") or citation.get("url", "") if isinstance(citation, dict) else ""
            citation_info.append(f"[S{i}] {title} - {url}")
        
        prompt = f"""Analyze the following document for quality issues:

## Document Content
{document_text}

## Citations Available
{chr(10).join(citation_info) if citation_info else "No citations provided"}

## Analysis Required
Please analyze and return a JSON object with the following structure:
{{
    "contradictions": {{
        "found": true/false,
        "examples": ["list of contradictory statements if any"]
    }},
    "citation_coverage": {{
        "score": 0.0-1.0,
        "uncited_claims": ["list of claims without citations"],
        "uncited_numbers": true/false,
        "examples": ["examples of uncited numbers if any"]
    }},
    "section_completeness": {{
        "score": 0.0-1.0,
        "missing_sections": ["list of missing sections"],
        "incomplete_sections": ["list of incomplete sections"]
    }},
    "overall_quality": "high/medium/low"
}}

Focus on:
1. Finding logical contradictions (e.g., "X is true" vs "X is false")
2. Identifying claims without citations (especially numerical claims)
3. Checking if all required sections are present and complete
"""
        return prompt

    def _parse_analysis(self, analysis: Dict[str, Any], envelope: Any, written_output: Dict[str, Any]) -> QualityReport:
        """Parse LLM analysis into QualityReport."""
        contradictions = analysis.get("contradictions", {})
        citation_coverage = analysis.get("citation_coverage", {})
        section_completeness = analysis.get("section_completeness", {})
        
        citation_score = citation_coverage.get("score", 0.5)
        completeness_score = section_completeness.get("score", 0.5)
        
        uncited_numbers = citation_coverage.get("uncited_numbers", False)
        has_contradictions = contradictions.get("found", False)
        missing_sections = section_completeness.get("missing_sections", [])
        
        # Build section coverage from analysis
        section_coverage = {}
        if hasattr(envelope, "executive_summary") and envelope.executive_summary:
            section_coverage["Executive Summary"] = 1.0
        if hasattr(envelope, "deliverable") and envelope.deliverable:
            section_coverage["Deliverable"] = 1.0
        
        # Perform semantic citation validation
        semantic_validation = {}
        try:
            semantic_validation = self.citation_validator.validate_citations(
                document_text=document_text,
                citations=citations,
                effort=effort,
            )
        except Exception as exc:
            logger.warning("Semantic citation validation failed: %s", exc)
        
        return QualityReport(
            citation_coverage_score=citation_score,
            template_completeness_score=completeness_score,
            missing_sections=missing_sections,
            section_coverage=section_coverage,
            uncited_numbers=uncited_numbers,
            contradictions=has_contradictions,
            semantic_citation_score=semantic_validation.get("overall_semantic_score"),
            broken_urls=semantic_validation.get("broken_urls", []),
            low_relevance_citations=semantic_validation.get("low_relevance_citations", []),
            citation_relevance_map=semantic_validation.get("semantic_scores"),
        )

    def _basic_check(self, written_output: Dict[str, Any]) -> QualityReport:
        """Fallback basic fact checking when LLM is unavailable."""
        # Use existing basic evaluation logic
        from web_search_agent.post_processing import evaluate_report_sections
        
        envelope = written_output.get("envelope")
        if not envelope:
            return QualityReport(
                citation_coverage_score=0.0,
                template_completeness_score=0.0,
                missing_sections=["Executive Summary", "Deliverable"],
                section_coverage={},
                uncited_numbers=True,
                contradictions=True,
            )
        
        sections = {
            "Executive Summary": getattr(envelope, "executive_summary", ""),
            "Deliverable": getattr(envelope, "deliverable", ""),
            "Assumptions & Gaps": getattr(envelope, "assumptions_and_gaps", ""),
            "Open Questions": "\n".join(getattr(envelope, "open_questions", []) or []),
        }
        evaluation = evaluate_report_sections(sections, required_sections=list(sections.keys()))
        
        from web_search_agent.post_processing import summarize_coverage_by_section
        return QualityReport(
            citation_coverage_score=evaluation.citation_coverage_score,
            template_completeness_score=evaluation.template_completeness_score,
            missing_sections=evaluation.missing_sections,
            section_coverage=summarize_coverage_by_section(evaluation.section_evaluations),
            uncited_numbers=evaluation.has_uncited_numbers,
            contradictions=evaluation.has_contradictions,
        )
