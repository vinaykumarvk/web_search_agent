"""Custom exceptions for agent failures."""
from __future__ import annotations


class AgentError(RuntimeError):
    """Base exception for agent failures."""
    pass


class RouterError(AgentError):
    """Raised when router agent fails."""
    pass


class ClarifierError(AgentError):
    """Raised when clarifier agent fails."""
    pass


class WriterError(AgentError):
    """Raised when writer agent fails."""
    pass


class FactCheckerError(AgentError):
    """Raised when fact checker agent fails."""
    pass


class ResearchError(AgentError):
    """Raised when research agent fails."""
    pass


class DeepResearchError(AgentError):
    """Raised when deep research fails."""
    pass

