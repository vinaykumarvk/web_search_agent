"""Minimal web search agent utilities for routing, templating, and citation handling."""

from .router import RouteDecision, route_request
from .templates import render_envelope, render_template
from .citations import Citation, render_citations, has_complete_citations
from .fakes import FakeSearchProvider, FakeDeepResearchClient

__all__ = [
    "RouteDecision",
    "route_request",
    "render_envelope",
    "render_template",
    "Citation",
    "render_citations",
    "has_complete_citations",
    "FakeSearchProvider",
    "FakeDeepResearchClient",
]
"""Utilities for evaluating research outputs and ranking search results."""
