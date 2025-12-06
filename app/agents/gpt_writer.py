"""GPT-5.1 writer agent for structured reporting and deliverable generation."""
from __future__ import annotations

import json
import logging
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional

try:
    from openai import OpenAI  # type: ignore
except Exception:  # pragma: no cover - optional dependency
    OpenAI = None  # type: ignore

from app.config import load_settings
from app.exceptions import WriterError

logger = logging.getLogger(__name__)
settings = load_settings()

DEFAULT_WRITER_MODEL = "gpt-5.1"


@dataclass(frozen=True)
class WriterPrompts:
    """Container for writer system and developer messages."""

    system: str
    developer: str


def _build_writer_system_message(purpose: str) -> str:
    """Build system message for GPT-5.1 writer based on purpose."""
    base = (
        "You are an expert technical writer specializing in structured business and technical documents. "
        "Your role is to transform research findings into polished, executive-grade deliverables. "
        "You excel at formatting, clarity, structured writing, and following templates precisely."
    )
    
    purpose_specific = {
        "brd": (
            "For BRDs, you must include: Problem statement, Goals/Non-goals, Stakeholders/Personas, "
            "User journeys, Functional requirements (MoSCoW), Non-functional requirements, "
            "Data & analytics requirements, Dependencies/integrations, Risks & mitigations, "
            "Acceptance criteria outline, Rollout plan + success metrics."
        ),
        "company_research": (
            "For company research, include: Company overview, Products/services, Customers & positioning, "
            "Market sizing (with cited assumptions), Competitive landscape, Business model & unit economics, "
            "Financial snapshot, Strategy signals, Risks, and 'What to watch' indicators."
        ),
        "req_elaboration": (
            "For requirement elaboration, include: Restated requirement + intent, Ambiguities & clarifications, "
            "Decomposition (epics → stories), Acceptance criteria (Given/When/Then), Edge cases & failure modes, "
            "Test scenarios, and Telemetry/metrics."
        ),
        "market_query": (
            "For market queries, include: Definition, Why it matters (context), Examples, "
            "Common confusions, and Source list."
        ),
    }
    
    specific = purpose_specific.get(purpose.lower(), "Follow the template structure provided.")
    return f"{base}\n\n{specific}"


def _build_writer_developer_message(purpose: str, template_content: str) -> str:
    """Build developer message with template instructions."""
    return (
        f"You are writing a {purpose.upper()} document. Use the following template structure:\n\n"
        f"{template_content}\n\n"
        "Requirements:\n"
        "- Every key claim must cite a source using [S1], [S2], etc. format\n"
        "- Any numerical claim should have a citation or be labeled as 'estimate'\n"
        "- Use clean Markdown formatting with proper headings, tables, and lists\n"
        "- Maintain professional, consultant-grade language\n"
        "- Surface uncertainties and assumptions explicitly\n"
        "- Follow the template structure exactly, filling all required sections\n"
        "- Ensure narrative cohesion and logical flow"
    )


class GPT5WriterAgent:
    """GPT-5.1-powered writer agent for structured reporting."""

    def __init__(
        self,
        model: Optional[str] = None,
        templates_dir: str = "app/templates",
        api_key: Optional[str] = None,
        metrics: Optional[Any] = None,
    ) -> None:
        self.model = model or os.environ.get("OPENAI_WRITER_MODEL", DEFAULT_WRITER_MODEL)
        self.templates_dir = Path(templates_dir)
        self.api_key = api_key or os.environ.get("OPENAI_API_KEY")
        self.metrics = metrics
        if OpenAI is None:
            if settings.strict_mode:
                raise WriterError("OpenAI package not available for writer - strict mode enabled")
            logger.warning("OpenAI package not available; GPT writer will not function")
            self.client = None
        else:
            self.client = OpenAI(api_key=self.api_key) if self.api_key else None
            if not self.client and settings.strict_mode:
                raise WriterError("OpenAI API key not available for writer - strict mode enabled")

    def write_deliverable(
        self,
        purpose: str,
        research_findings: List[Dict[str, Any]],
        query: str,
        citations: List[Dict[str, str]],
        context: Optional[Dict[str, Any]] = None,
        effort: str = "medium",
        depth: str = "standard",
    ) -> Dict[str, Any]:
        """Generate structured deliverable using GPT-5.1 from research findings.
        
        Args:
            purpose: Document purpose (brd, company_research, req_elaboration, market_query, custom)
            research_findings: List of research results with findings/evidence
            query: Original user query
            citations: List of citation dicts with title, url, snippet
            context: Additional context (audience, region, timeframe, etc.)
        
        Returns:
            Dict with 'deliverable' (markdown), 'executive_summary', and other fields
        """
        if not self.client:
            raise WriterError("OpenAI client not available; cannot generate deliverable")

        # Load template for the purpose
        template_path = self.templates_dir / f"{purpose}.md"
        if template_path.exists():
            template_content = template_path.read_text(encoding="utf-8")
        else:
            template_content = f"# {purpose.upper()}\n\nGenerate content based on research findings."

        # Build research context string
        research_context = self._format_research_context(research_findings, citations)
        
        # Build prompt
        system_msg = _build_writer_system_message(purpose)
        developer_msg = _build_writer_developer_message(purpose, template_content)
        
        user_prompt = self._build_user_prompt(query, research_context, citations, context or {})

        try:
            # Use Responses API (newer generation API) for GPT-5.1
            # Responses API supports reasoning/verbosity parameters and better performance
            response = self.client.responses.create(
                model=self.model,
                input=[
                    {"role": "system", "content": system_msg},
                    {"role": "user", "content": f"{developer_msg}\n\n{user_prompt}"},
                ],
                max_output_tokens=4000,
                temperature=0.3,
            )

            if self.metrics and hasattr(response, "usage"):
                usage = response.usage
                self.metrics.emit_token_usage(
                    stage="writer_deliverable",
                    prompt_tokens=getattr(usage, "prompt_tokens", 0),
                    completion_tokens=getattr(usage, "completion_tokens", 0),
                    model=self.model,
                )

            deliverable_text = getattr(response, "output_text", "") or ""
            if not deliverable_text:
                raise WriterError("Writer returned empty output")

            executive_summary = self._extract_executive_summary(deliverable_text)
            if not executive_summary:
                executive_summary = self._generate_executive_summary(query, research_context)

            return {
                "deliverable": deliverable_text,
                "executive_summary": executive_summary,
            }
        except Exception as exc:
            logger.exception("GPT-5.1 writer failed: %s", exc)
            raise WriterError(f"Failed to generate deliverable: {exc}") from exc

    def _format_research_context(
        self, research_findings: List[Dict[str, Any]], citations: List[Dict[str, str]]
    ) -> str:
        """Format research findings into context string."""
        context_parts = ["## Research Findings\n"]
        
        # Add citations reference
        if citations:
            context_parts.append("### Sources\n")
            for i, citation in enumerate(citations, 1):
                context_parts.append(
                    f"[S{i}] {citation.get('title', 'Source')}\n"
                    f"URL: {citation.get('url', 'N/A')}\n"
                    f"Snippet: {citation.get('snippet', 'N/A')}\n\n"
                )
        
        # Add findings
        for idx, finding in enumerate(research_findings, 1):
            notes = finding.get("notes", [])
            if notes:
                context_parts.append(f"### Finding {idx}\n")
                for note in notes[:5]:  # Limit to top 5 notes per finding
                    context_parts.append(f"- {note}\n")
                context_parts.append("\n")
        
        return "\n".join(context_parts)

    def _build_user_prompt(
        self,
        query: str,
        research_context: str,
        citations: List[Dict[str, str]],
        context: Dict[str, Any],
    ) -> str:
        """Build user prompt for GPT-5.1."""
        audience = context.get("audience", "mixed")
        region = context.get("region")
        timeframe = context.get("timeframe")
        
        prompt_parts = [
            f"## Task\n",
            f"Generate a structured document for: {query}\n",
        ]
        
        if audience:
            prompt_parts.append(f"Target audience: {audience}\n")
        if region:
            prompt_parts.append(f"Region focus: {region}\n")
        if timeframe:
            prompt_parts.append(f"Timeframe: {timeframe}\n")
        
        # Add research notes from WebSearchResponse if available
        research_notes = context.get("research_notes", [])
        if research_notes:
            prompt_parts.append("\n## Research Notes\n")
            for note in research_notes[:10]:  # Limit to top 10 notes
                prompt_parts.append(f"- {note}\n")
        
        prompt_parts.append("\n## Research Context\n")
        prompt_parts.append(research_context)
        prompt_parts.append("\n## Instructions\n")
        prompt_parts.append(
            "Using the research findings above, generate a complete, well-structured document. "
            "Cite sources using [S1], [S2], etc. format. Ensure all sections are complete and "
            "professionally written. Surface any uncertainties or assumptions explicitly."
        )
        
        return "\n".join(prompt_parts)

    def _extract_executive_summary(self, deliverable_text: str) -> str:
        """Extract executive summary from deliverable if present."""
        # Look for ## Executive Summary or # Executive Summary
        lines = deliverable_text.split("\n")
        summary_lines = []
        in_summary = False
        
        for line in lines:
            if line.strip().lower().startswith(("# executive summary", "## executive summary")):
                in_summary = True
                continue
            if in_summary:
                if line.strip().startswith("#") and not line.strip().lower().startswith("## executive"):
                    break
                if line.strip():
                    summary_lines.append(line.strip())
        
        return "\n".join(summary_lines) if summary_lines else ""

    def _generate_executive_summary(self, query: str, research_context: str, effort: str = "medium", depth: str = "standard") -> str:
        """Generate executive summary using GPT-5.1 if not present in deliverable."""
        if not self.client:
            return f"Summary for: {query}"
        
        try:
            # Use Responses API (newer generation API) for GPT-5.1
            response = self.client.responses.create(
                model=self.model,
                input=[
                    {
                        "role": "system",
                        "content": "You are an expert at writing executive summaries. "
                        "Generate concise, bullet-point summaries (3-7 bullets) of key findings.",
                    },
                    {
                        "role": "user",
                        "content": f"Generate an executive summary for research query: {query}\n\n{research_context}",
                    },
                ],
                max_output_tokens=500,
                temperature=0.3,
            )
            
            # Extract and emit token usage metrics
            if self.metrics and hasattr(response, "usage"):
                usage = response.usage
                self.metrics.emit_token_usage(
                    stage="writer_summary",
                    prompt_tokens=getattr(usage, "prompt_tokens", 0),
                    completion_tokens=getattr(usage, "completion_tokens", 0),
                    model=self.model,
                )
            
            return getattr(response, "output_text", "") or f"Summary for: {query}"
        except Exception as exc:
            logger.warning("Failed to generate executive summary: %s", exc)
            return f"Summary for: {query}"
