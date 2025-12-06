"""Environment-driven configuration helpers for the web search agent."""
from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Mapping, MutableMapping, Optional

try:
    from dotenv import load_dotenv
except ImportError:
    load_dotenv = None  # type: ignore

DEFAULT_CACHE_TTL_SECONDS = 300
DEFAULT_ENV_FILE = Path(".env")


def _to_bool(value: Optional[str], *, default: bool = False) -> bool:
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


@dataclass
class ObservabilitySettings:
    """Tracing and logging toggles."""

    tracing_enabled: bool = False
    tracing_sample_rate: float = 1.0
    tracing_endpoint: Optional[str] = None
    log_level: str = "INFO"


@dataclass
class CacheSettings:
    """Cache defaults used across the agent."""

    ttl_seconds: int = DEFAULT_CACHE_TTL_SECONDS


@dataclass
class AppSettings:
    """Aggregated configuration for the application."""

    openai_api_key: Optional[str] = None
    search_api_key: Optional[str] = None
    cache: CacheSettings = field(default_factory=CacheSettings)
    observability: ObservabilitySettings = field(default_factory=ObservabilitySettings)
    strict_mode: bool = False  # If True, fail fast instead of using fallbacks


def load_settings(env: Mapping[str, str] | MutableMapping[str, str] | None = None, env_file: Optional[Path] = None) -> AppSettings:
    """Load settings from the provided environment mapping (defaults to ``os.environ``).
    
    Also loads from .env file if present and python-dotenv is available.
    Environment variables take precedence over .env file values.

    The loader is intentionally lightweight so it can be reused in CLIs, tests, or
    application entrypoints without pulling in a heavier configuration framework.
    """
    
    # Load .env file if available
    env_file_path = env_file or DEFAULT_ENV_FILE
    if load_dotenv is not None and env_file_path.exists():
        load_dotenv(env_file_path, override=False)  # Don't override existing env vars
    
    env = env if env is not None else os.environ
    cache_ttl = int(env.get("CACHE_TTL_SECONDS", DEFAULT_CACHE_TTL_SECONDS))

    observability = ObservabilitySettings(
        tracing_enabled=_to_bool(env.get("TRACING_ENABLED")),
        tracing_sample_rate=float(env.get("TRACING_SAMPLE_RATE", 1.0)),
        tracing_endpoint=env.get("TRACING_ENDPOINT"),
        log_level=env.get("LOG_LEVEL", "INFO"),
    )

    strict_mode = _to_bool(env.get("STRICT_MODE"), default=False)

    return AppSettings(
        openai_api_key=env.get("OPENAI_API_KEY"),
        search_api_key=env.get("SEARCH_API_KEY"),
        cache=CacheSettings(ttl_seconds=cache_ttl),
        observability=observability,
        strict_mode=strict_mode,
    )
