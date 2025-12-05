"""Routing agent prompt definitions."""
from __future__ import annotations

from dataclasses import dataclass
from typing import List


@dataclass(frozen=True)
class AgentPrompts:
    """Container for system and developer messages."""

    system: str
    developer: str


ROUTER_SYSTEM_MESSAGE = (
    "You are the routing orchestrator. Classify the user's intent into supported "
    "templates (brd, company_research, req_elaboration, market_query, custom) and "
    "assign depth (quick, standard, deep). Respect user-specified purpose/depth when "
    "present. Keep responses terse and avoid performing research yourself."
)

ROUTER_DEVELOPER_MESSAGE = (
    "Return a structured classification only. Use clarifier agent when critical "
    "details are missing. Deep depth should be chosen only when the user explicitly "
    "requests exhaustive research or citations." 
)


def build_router_prompts() -> AgentPrompts:
    """Builds router system and developer messages."""

    return AgentPrompts(system=ROUTER_SYSTEM_MESSAGE, developer=ROUTER_DEVELOPER_MESSAGE)


SUPPORTED_PURPOSES: List[str] = [
    "brd",
    "company_research",
    "req_elaboration",
    "market_query",
    "custom",
]
