"""Core package for the web search agent."""

from .config import AppSettings, CacheSettings, ObservabilitySettings, load_settings
from .observability import configure_logging, configure_tracing, MetricsEmitter

__all__ = [
    "AppSettings",
    "CacheSettings",
    "ObservabilitySettings",
    "load_settings",
    "configure_logging",
    "configure_tracing",
    "MetricsEmitter",
]
"""Core package for multi-agent orchestrator."""

__all__ = [
    "NormalizedRequest",
    "RouterDecision",
    "ResearchPlan",
    "ResearchTask",
    "DepthPolicy",
    "RetryConfig",
    "Orchestrator",
]

from .orchestrator import (
    NormalizedRequest,
    RouterDecision,
    ResearchPlan,
    ResearchTask,
    DepthPolicy,
    RetryConfig,
    Orchestrator,
)
