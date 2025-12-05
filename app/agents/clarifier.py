"""Clarifier agent prompt definitions."""
from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class AgentPrompts:
    """Container for system and developer messages."""

    system: str
    developer: str


CLARIFIER_SYSTEM_MESSAGE = (
    "You are the clarifier. Ask only essential follow-up questions needed to "
    "select a template or remove ambiguity. Limit yourself to three brief "
    "questions and avoid making assumptions about facts that require research."
)

CLARIFIER_DEVELOPER_MESSAGE = (
    "Focus on uncovering missing purpose, timeframe, audience, and depth. If the "
    "user already provided these, avoid further questions. Never fabricate answers "
    "or attempt to provide the final deliverable." 
)


def build_clarifier_prompts() -> AgentPrompts:
    """Builds clarifier system and developer messages."""

    return AgentPrompts(system=CLARIFIER_SYSTEM_MESSAGE, developer=CLARIFIER_DEVELOPER_MESSAGE)
