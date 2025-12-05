"""Logging, tracing, and lightweight metrics helpers for the agent."""
from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, Iterable, Optional

from .config import ObservabilitySettings

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

    def _emit(self, name: str, payload: Dict[str, Any]) -> None:
        self.logger.info("metric.%s", name, extra={"metric": payload})
        for sink in self.sinks:
            try:
                sink(name, payload)
            except Exception:
                self.logger.exception("Metric sink failed", extra={"metric_name": name})

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

    def emit_search_query(self, query: str, depth: str) -> None:
        self._emit("search_query", {"query": query, "depth": depth})

    def emit_source_selection(self, source: str, relevance: float) -> None:
        self._emit("source_selection", {"source": source, "relevance": relevance})
