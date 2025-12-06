from __future__ import annotations

from pathlib import Path
from typing import Mapping


class MissingSectionError(ValueError):
    """Raised when a required section is absent or empty."""


# Template directory - use app/templates in production, fallback to templates/ for compatibility
# In Docker, __file__ will be /app/app/templates/render.py, so parents[2] = /app
_TEMPLATE_BASE = Path(__file__).resolve().parents[2]
if (_TEMPLATE_BASE / "app" / "templates").exists():
    TEMPLATE_DIR = _TEMPLATE_BASE / "app" / "templates"
elif (_TEMPLATE_BASE / "templates").exists():
    TEMPLATE_DIR = _TEMPLATE_BASE / "templates"
else:
    # Fallback to app/templates relative to current file
    TEMPLATE_DIR = Path(__file__).resolve().parent
BASE_TEMPLATE_NAME = "base_envelope.md"

PURPOSE_TO_TEMPLATE = {
    "brd": "brd.md",
    "company_research": "company_research.md",
    "req_elaboration": "req_elaboration.md",
    "market_query": "market_query.md",
    "custom": "custom.md",
}

MANDATORY_BASE_FIELDS = [
    "title",
    "purpose",
    "depth",
    "audience",
    "region_timeframe",
    "executive_summary",
    "sources",
    "assumptions_gaps",
    "open_questions",
    "next_steps",
    "deliverable",
]

MANDATORY_DELIVERABLE_FIELDS = {
    "brd": [
        "problem_statement",
        "goals",
        "target_users",
        "scope",
        "requirements",
        "success_metrics",
        "risks_mitigations",
        "timeline",
    ],
    "company_research": [
        "overview",
        "products_services",
        "market_position",
        "financials",
        "go_to_market",
        "risks",
        "source_highlights",
    ],
    "req_elaboration": [
        "epics",
        "user_stories",
        "acceptance_criteria",
        "dependencies",
        "open_questions",
    ],
    "market_query": [
        "question",
        "insights",
        "data_points",
        "confidence",
        "source_summary",
    ],
    "custom": [
        "notes",
    ],
}


def _validate_required_fields(label: str, data: Mapping[str, str], required_keys: list[str]) -> None:
    missing = [key for key in required_keys if not str(data.get(key, "")).strip()]
    if missing:
        raise MissingSectionError(f"{label} is missing required sections: {', '.join(missing)}")


def _load_template(name: str, template_dir: Path = TEMPLATE_DIR) -> str:
    template_path = template_dir / name
    if not template_path.exists():
        raise FileNotFoundError(f"Template {name} not found in {template_dir}")
    return template_path.read_text(encoding="utf-8")


def render_deliverable(
    purpose: str,
    deliverable_fields: Mapping[str, str],
    *,
    template_dir: Path = TEMPLATE_DIR,
) -> str:
    """Render the body for a given purpose-specific template."""

    template_name = PURPOSE_TO_TEMPLATE.get(purpose)
    if not template_name:
        raise ValueError(f"Unknown purpose '{purpose}'. Expected one of: {', '.join(PURPOSE_TO_TEMPLATE)}")

    _validate_required_fields(
        f"Deliverable for {purpose}", deliverable_fields, MANDATORY_DELIVERABLE_FIELDS[purpose]
    )

    template_content = _load_template(template_name, template_dir)
    return template_content.format_map(deliverable_fields)


def render_document(
    purpose: str,
    base_fields: Mapping[str, str],
    deliverable_fields: Mapping[str, str],
    *,
    template_dir: Path = TEMPLATE_DIR,
) -> str:
    """Render the full document by injecting deliverable content into the envelope."""

    deliverable_content = render_deliverable(purpose, deliverable_fields, template_dir=template_dir)

    merged_fields = dict(base_fields)
    merged_fields.setdefault("purpose", purpose)
    merged_fields.setdefault("region_timeframe", "n/a")
    merged_fields.setdefault("open_questions", "(none provided)")
    merged_fields["deliverable"] = deliverable_content
    merged_fields["deliverable_body"] = deliverable_content  # Also set deliverable_body for template compatibility

    _validate_required_fields("Base envelope", merged_fields, MANDATORY_BASE_FIELDS)

    base_template = _load_template(BASE_TEMPLATE_NAME, template_dir)
    return base_template.format_map(merged_fields)
