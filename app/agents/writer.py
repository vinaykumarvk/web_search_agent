"""Writer agent prompt definitions and template assembly."""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from string import Template
from typing import Dict


@dataclass(frozen=True)
class AgentPrompts:
    """Container for system and developer messages."""

    system: str
    developer: str


WRITER_SYSTEM_MESSAGE = (
    "You are the writer. Merge the base envelope with the selected template body to "
    "produce a complete response. Preserve section headings, include citations next "
    "to claims, and keep formatting clean."
)

WRITER_DEVELOPER_MESSAGE = (
    "Always render using templates/base_envelope.md as the outer shell. Insert the "
    "chosen template body into the Deliverable section. Respect citation markers "
    "provided by the research agent and do not discard unknowns—surface them under "
    "Assumptions & Gaps."
)


class WriterAgent:
    """Combines templates into a final deliverable."""

    def __init__(self, templates_dir: str = "app/templates") -> None:
        self.templates_dir = Path(templates_dir)
        self.prompts = AgentPrompts(system=WRITER_SYSTEM_MESSAGE, developer=WRITER_DEVELOPER_MESSAGE)

    def render(self, template_name: str, context: Dict[str, str]) -> str:
        """Render the base envelope with the chosen template body."""

        base_envelope = self._load_template("base_envelope.md")
        body_template = self._load_template(f"{template_name}.md")

        body = Template(body_template).safe_substitute(**context)
        merged_context = {**context, "deliverable_body": body}
        return Template(base_envelope).safe_substitute(**merged_context)

    def _load_template(self, filename: str) -> str:
        path = self.templates_dir / filename
        return path.read_text(encoding="utf-8")


def build_writer_prompts() -> AgentPrompts:
    """Expose writer system and developer messages."""

    return AgentPrompts(system=WRITER_SYSTEM_MESSAGE, developer=WRITER_DEVELOPER_MESSAGE)
