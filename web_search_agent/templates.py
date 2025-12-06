from __future__ import annotations

from string import Template
from typing import Iterable, List, Mapping

from .citations import Citation, render_citations


TEMPLATES = {
    "brd": Template(
        """## Deliverable\n### Problem Statement\n$problem\n\n### Goals\n$goals\n"""
    ),
    "company_research": Template(
        """## Deliverable\n### Company Overview\n$overview\n\n### Recent Moves\n$moves\n"""
    ),
    "req_elaboration": Template(
        """## Deliverable\n### User Story\n$user_story\n\n### Acceptance Criteria\n$acceptance\n"""
    ),
    "market_query": Template(
        """## Deliverable\n### Market Summary\n$summary\n\n### Competitive Signals\n$signals\n"""
    ),
    "custom": Template(
        """## Deliverable\n### Notes\n$notes\n"""
    ),
}


BASE_ENVELOPE = Template(
    """# $title\n
## Metadata
- Purpose: $purpose
- Depth: $depth
- Audience: $audience
- Region/Timeframe: $region_timeframe

## Executive Summary
$summary

$deliverable

## Sources
$sources

## Assumptions & Gaps
$assumptions

## Open Questions
$open_questions

## Next Steps
$next_steps
"""
)


def render_template(purpose: str, context: Mapping[str, str]) -> str:
    """Render a template body based on purpose using the provided context."""

    template = TEMPLATES.get(purpose, TEMPLATES["custom"])
    return template.safe_substitute(context)


def render_envelope(
    title: str,
    summary: str,
    deliverable: str,
    sources: Iterable[Citation],
    *,
    purpose: str = "custom",
    depth: str = "standard",
    audience: str = "mixed",
    region_timeframe: str = "n/a",
    assumptions: Iterable[str] | None = None,
    open_questions: Iterable[str] | None = None,
    next_steps: Iterable[str] | None = None,
) -> str:
    """
    Render the full response envelope with consistent section ordering.

    The function keeps the formatting stable so tests can assert structure without
    talking to external services.
    """

    source_block = render_citations(list(sources)) or "- (no sources)"
    assumptions_block = "\n".join(f"- {item}" for item in (assumptions or ["(none provided)"]))
    open_questions_block = "\n".join(f"- {item}" for item in (open_questions or ["(none provided)"]))
    next_steps_block = "\n".join(f"- {item}" for item in (next_steps or ["(none provided)"]))

    return BASE_ENVELOPE.safe_substitute(
        title=title,
        purpose=purpose,
        depth=depth,
        audience=audience,
        region_timeframe=region_timeframe,
        summary=summary,
        deliverable=deliverable,
        sources=source_block,
        assumptions=assumptions_block,
        open_questions=open_questions_block,
        next_steps=next_steps_block,
    )
