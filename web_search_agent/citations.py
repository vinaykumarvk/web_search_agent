from dataclasses import dataclass
from typing import Iterable, List


@dataclass
class Citation:
    """Represents a citation with minimal metadata."""

    title: str
    url: str
    snippet: str


def render_citations(citations: Iterable[Citation]) -> str:
    """Render citations as Markdown bullet list."""

    lines: List[str] = []
    for citation in citations:
        line = f"- [{citation.title}]({citation.url}) — {citation.snippet}"
        lines.append(line)
    return "\n".join(lines)


def has_complete_citations(rendered: str) -> bool:
    """Check that every bullet in the Sources section has a hyperlink."""

    return all("- [" in line and "](http" in line for line in rendered.splitlines() if line.startswith("- "))
