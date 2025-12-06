from dataclasses import dataclass
from typing import Iterable, List, Mapping


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


def render_bibliography(entries: Iterable[Mapping[str, str]]) -> str:
    """Render a bibliography block from structured citation metadata."""

    lines: List[str] = []
    for entry in entries:
        identifier = entry.get("id") or entry.get("citation_id") or ""
        title = entry.get("title", "")
        publisher = entry.get("publisher")
        url = entry.get("url", "")
        annotation = entry.get("annotation")
        suffix = f" ({publisher})" if publisher else ""
        note = f" — {annotation}" if annotation else ""
        lines.append(f"- [{identifier}] {title}{suffix} - {url}{note}")
    return "\n".join(lines)
