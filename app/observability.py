"""Logging, tracing, and lightweight metrics helpers for the agent."""
from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, Iterable, Optional

from .config import ObservabilitySettings

try:
    from .utils.persistent_logging import PersistentLogger
except ImportError:
    PersistentLogger = None  # type: ignore

try:
    from openai import tracing  # type: ignore
except Exception:  # pragma: no cover - optional dependency
    tracing = None


MetricSink = Callable[[str, Dict[str, Any]], None]


def configure_logging(settings: ObservabilitySettings) -> None:
    """Configure structured logging according to the provided settings."""

    level = getattr(logging, settings.log_level.upper(), logging.INFO)
    logging.basicConfig(
        level=level,
        format="%(asctime)s %(levelname)s [%(name)s] %(message)s",
    )
    logging.getLogger(__name__).debug(
        "Logging configured", extra={"level": settings.log_level.upper()}
    )


def configure_tracing(settings: ObservabilitySettings) -> Optional[Any]:
    """Enable OpenAI Agents SDK tracing when available.

    Returns a tracer instance when tracing is enabled and supported, otherwise ``None``.
    """

    logger = logging.getLogger(__name__)
    if not settings.tracing_enabled:
        logger.info("Tracing disabled by configuration")
        return None

    if tracing is None:
        logger.warning("OpenAI tracing SDK not available; skipping tracing setup")
        return None

    tracer = None
    try:
        tracer = tracing.configure(
            sample_rate=settings.tracing_sample_rate,
            endpoint=settings.tracing_endpoint,
        )
        logger.info(
            "OpenAI tracing configured",
            extra={
                "sample_rate": settings.tracing_sample_rate,
                "endpoint": settings.tracing_endpoint,
            },
        )
    except Exception as exc:  # pragma: no cover - depends on external SDK
        logger.exception("Failed to configure tracing: %s", exc)
    return tracer


@dataclass
class MetricsEmitter:
    """Simple metrics helper that fans out to configured sinks."""

    sinks: Iterable[MetricSink] = field(default_factory=list)
    logger: logging.Logger = field(default_factory=lambda: logging.getLogger(__name__))
    persistent_logger: Optional[Any] = None
    
    def __post_init__(self):
        """Initialize persistent logger if available."""
        if PersistentLogger is not None and self.persistent_logger is None:
            try:
                self.persistent_logger = PersistentLogger()
            except Exception:
                self.persistent_logger = None  # Gracefully handle initialization failures

    def _emit(self, name: str, payload: Dict[str, Any]) -> None:
        self.logger.info("metric.%s", name, extra={"metric": payload})
        
        # Persist to database if available
        if self.persistent_logger:
            try:
                value = payload.get("value", 1.0)
                extra = {k: v for k, v in payload.items() if k != "value"}
                self.persistent_logger.log_metric(name, float(value), extra if extra else None)
            except Exception:
                pass  # Don't fail if persistence fails
        
        for sink in self.sinks:
            try:
                sink(name, payload)
            except Exception:
                self.logger.exception("Metric sink failed", extra={"metric_name": name})

    def emit_clarifier_unavailable(self) -> None:
        """Emit metric when clarifier is unavailable."""
        self.emit_metric("clarifier.unavailable", 1)

    def emit_fact_checker_unavailable(self) -> None:
        """Emit metric when fact checker is unavailable."""
        self.emit_metric("fact_checker.unavailable", 1)

    def emit_search_empty_results(self, query: str) -> None:
        """Emit metric when search returns empty results."""
        self.emit_metric("search.empty_results", 1, extra={"query": query[:100]})

    def emit_token_usage(
        self,
        stage: str,
        prompt_tokens: int,
        completion_tokens: int,
        model: Optional[str] = None,
    ) -> None:
        payload = {
            "stage": stage,
            "prompt_tokens": prompt_tokens,
            "completion_tokens": completion_tokens,
        }
        if model:
            payload["model"] = model
        self._emit("token_usage", payload)
        
        # Also persist token usage separately
        if self.persistent_logger:
            try:
                self.persistent_logger.log_token_usage(stage, prompt_tokens, completion_tokens, model)
            except Exception:
                pass  # Don't fail if persistence fails

    def emit_search_query(self, query: str, depth: str, results_count: int = 0) -> None:
        self._emit("search_query", {"query": query, "depth": depth, "results_count": results_count})
        
        # Also persist search query separately
        if self.persistent_logger:
            try:
                self.persistent_logger.log_search_query(query, depth, results_count)
            except Exception:
                pass  # Don't fail if persistence fails

    def emit_source_selection(self, source: str, relevance: float) -> None:
        self._emit("source_selection", {"source": source, "relevance": relevance})

    def emit_task_status(self, task_id: str, status: str) -> None:
        self._emit("task_status", {"task_id": task_id, "status": status})
        
        # Also persist task status separately
        if self.persistent_logger:
            try:
                self.persistent_logger.log_task_status(task_id, status)
            except Exception:
                pass  # Don't fail if persistence fails

    def emit_metric(self, name: str, value: float, extra: Optional[Dict[str, Any]] = None) -> None:
        """Emit a generic metric."""
        payload = {"value": value}
        if extra:
            payload.update(extra)
        self._emit(name, payload)
