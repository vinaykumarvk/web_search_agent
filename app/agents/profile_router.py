"""Profile-aware web search router."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Optional


PROFILES = [
    "BRD_MODELING",
    "COMPANY_RESEARCH",
    "REQUIREMENT_ELABORATION",
    "MARKET_OR_TREND_QUERY",
    "DEFINITION_OR_SIMPLE_QUERY",
]


@dataclass(frozen=True)
class ProfileDecision:
    profile: str
    depth: str
    need_deep_research: bool


def classify_web_profile(
    query: str,
    purpose_hint: Optional[str] = None,
    depth_hint: Optional[str] = None,
) -> ProfileDecision:
    """Classify a query into a web-search profile and depth."""

    normalized = (query or "").lower()
    depth = (depth_hint or "standard").lower()

    def matches(*keywords: str) -> bool:
        return any(keyword in normalized for keyword in keywords)

    profile = "DEFINITION_OR_SIMPLE_QUERY"

    if purpose_hint:
        profile = _profile_from_purpose(purpose_hint)
    elif matches("brd", "business requirements", "functional spec", "requirements doc"):
        profile = "BRD_MODELING"
    elif matches("company", "business model", "valuation", "research the company", "fundamentals"):
        profile = "COMPANY_RESEARCH"
    elif matches("requirement", "user story", "acceptance criteria", "epic", "story"):
        profile = "REQUIREMENT_ELABORATION"
    elif matches("market", "trend", "industry", "guidelines", "analysis", "sizing"):
        profile = "MARKET_OR_TREND_QUERY"
    elif len(query.split()) <= 8:
        profile = "DEFINITION_OR_SIMPLE_QUERY"

    if matches("deep", "comprehensive", "detailed", "full report"):
        depth = "deep"
    elif matches("quick", "brief", "summary", "overview") or profile == "DEFINITION_OR_SIMPLE_QUERY":
        depth = "quick" if depth_hint is None else depth

    need_deep_research = depth == "deep" or matches("deep research", "background research")

    return ProfileDecision(profile=profile, depth=depth, need_deep_research=need_deep_research)


def _profile_from_purpose(purpose: str) -> str:
    purpose_normalized = purpose.lower()
    if purpose_normalized == "brd":
        return "BRD_MODELING"
    if purpose_normalized == "company_research":
        return "COMPANY_RESEARCH"
    if purpose_normalized == "req_elaboration":
        return "REQUIREMENT_ELABORATION"
    if purpose_normalized == "market_query":
        return "MARKET_OR_TREND_QUERY"
    return "DEFINITION_OR_SIMPLE_QUERY"
