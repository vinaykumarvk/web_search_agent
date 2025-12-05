from dataclasses import dataclass
from enum import Enum
from typing import Optional


class SourceType(str, Enum):
    """Enumerates the preferred types of sources for research."""

    OFFICIAL = "official"
    REPORTING = "reporting"
    COMMUNITY = "community"
    UNKNOWN = "unknown"


@dataclass
class CitationMetadata:
    """Describes a citation in a way that can be rendered in a bibliography."""

    citation_id: str
    title: str
    url: str
    source_type: SourceType = SourceType.UNKNOWN
    publisher: Optional[str] = None
    published_at: Optional[str] = None
    accessed_at: Optional[str] = None
    annotation: Optional[str] = None

    def bibliography_label(self) -> str:
        """Return a human-readable label for inclusion in a bibliography."""

        publisher = f" ({self.publisher})" if self.publisher else ""
        return f"[{self.citation_id}] {self.title}{publisher}"

    def to_bibliography_entry(self) -> dict:
        """Serialize the citation metadata for structured bibliography rendering."""

        return {
            "id": self.citation_id,
            "title": self.title,
            "url": self.url,
            "publisher": self.publisher,
            "published_at": self.published_at,
            "accessed_at": self.accessed_at,
            "source_type": self.source_type.value,
            "annotation": self.annotation,
        }
