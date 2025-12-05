from dataclasses import dataclass
from typing import Optional


@dataclass
class RouteDecision:
    """Represents a routing decision for an incoming user request."""

    purpose: str
    depth: str


PURPOSE_KEYWORDS = {
    "brd": "brd",
    "business requirements": "brd",
    "company": "company_research",
    "market": "market_query",
    "requirement": "req_elaboration",
}

DEPTH_KEYWORDS = {
    "quick": "quick",
    "fast": "quick",
    "deep": "deep",
    "thorough": "deep",
}


def route_request(
    user_text: str,
    purpose_hint: Optional[str] = None,
    depth_hint: Optional[str] = None,
) -> RouteDecision:
    """
    Very small heuristic router that maps user text to an explicit purpose/depth.

    The heuristics are intentionally simple to keep tests deterministic; they only
    rely on keyword matches or explicit hints provided by the caller.
    """

    normalized = user_text.lower()
    purpose = purpose_hint or "custom"
    depth = depth_hint or "standard"

    for keyword, mapped in PURPOSE_KEYWORDS.items():
        if keyword in normalized:
            purpose = mapped
            break

    for keyword, mapped in DEPTH_KEYWORDS.items():
        if keyword in normalized:
            depth = mapped
            break

    return RouteDecision(purpose=purpose, depth=depth)
