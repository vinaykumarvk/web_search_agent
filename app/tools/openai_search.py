"""OpenAI Responses API-backed web search transport."""
from __future__ import annotations

import json
import logging
import os
from typing import Dict, List, Optional

try:
    from openai import OpenAI  # type: ignore
except Exception:  # pragma: no cover - optional dependency
    OpenAI = None  # type: ignore

from app.observability import MetricsEmitter

logger = logging.getLogger(__name__)

DEFAULT_SEARCH_MODEL = "gpt-5.1"


def _extract_text_output(response: object) -> str:
    """Best-effort extraction of text from Responses API output."""

    text = getattr(response, "output_text", None)
    if text:
        return text

    output = getattr(response, "output", None)
    if not output:
        return ""

    chunks: List[str] = []
    try:
        for item in output:
            for content in getattr(item, "content", []):
                if getattr(content, "type", None) == "output_text":
                    chunks.append(getattr(content, "text", "") or getattr(content, "value", ""))
                elif getattr(content, "type", None) == "text":
                    chunks.append(getattr(content, "text", ""))
    except Exception:  # pragma: no cover - structure may vary
        return ""
    return "\n".join(chunk for chunk in chunks if chunk)


def openai_web_search_transport(query: str, *, max_results: int = 5, model: Optional[str] = None) -> List[Dict[str, str]]:
    """Run a web search via the OpenAI Responses API and return normalized results."""

    if OpenAI is None:
        raise RuntimeError("openai package not installed; cannot use OpenAI search transport")

    client = OpenAI(api_key=os.environ.get("OPENAI_API_KEY"))
    model_name = model or os.environ.get("OPENAI_SEARCH_MODEL", DEFAULT_SEARCH_MODEL)
    schema = {
        "name": "web_results",
        "schema": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "title": {"type": "string"},
                    "url": {"type": "string"},
                    "snippet": {"type": "string"},
                    "source_type": {"type": "string"},
                },
                "required": ["title", "url", "snippet"],
                "additionalProperties": False,
            },
        },
        "strict": True,
    }

    prompt = (
        f"Use web search to find up to {max_results} high-quality sources for: '{query}'. "
        "Return a JSON array of objects matching the provided schema with title, url, snippet, and optional source_type. "
        "Prefer official/regulator/filing sources, then analyst/news, then community."
    )

    response = client.responses.create(
        model=model_name,
        input=prompt,
        tools=[{"type": "web_search"}],
    )

    text_output = _extract_text_output(response)
    if not text_output:
        logger.warning("OpenAI search returned no output text; returning empty results")
        MetricsEmitter().emit_search_empty_results(query)
        return []

    try:
        parsed = json.loads(text_output)
    except json.JSONDecodeError:
        logger.warning("Failed to decode OpenAI search output as JSON")
        return []

    results: List[Dict[str, str]] = []
    usage = getattr(response, "usage", None)
    if usage:
        prompt_tokens = getattr(usage, "prompt_tokens", 0)
        completion_tokens = getattr(usage, "completion_tokens", 0)
        MetricsEmitter().emit_token_usage(
            stage="web_search",
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
            model=model_name,
        )
    for item in parsed if isinstance(parsed, list) else []:
        if not isinstance(item, dict):
            continue
        results.append(
            {
                "title": str(item.get("title", "")),
                "url": str(item.get("url", "")),
                "snippet": str(item.get("snippet", "")),
                "source_type": str(item.get("source_type", "unknown")),
            }
        )
    return results
