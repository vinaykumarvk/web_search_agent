"""LLM-based router agent using GPT-5.1-mini for fast, intelligent intent classification."""
from __future__ import annotations

import json
import logging
import os
from typing import Any, Optional

try:
    from openai import OpenAI  # type: ignore
except Exception:  # pragma: no cover - optional dependency
    OpenAI = None  # type: ignore

from app.agents.router import ROUTER_SYSTEM_MESSAGE, ROUTER_DEVELOPER_MESSAGE, SUPPORTED_PURPOSES
from app.config import load_settings
from app.exceptions import RouterError
from app.orchestrator import RouterDecision

logger = logging.getLogger(__name__)
settings = load_settings()

# Use GPT-5-mini (faster and cheaper than GPT-5.1, perfect for classification)
# GPT-5-mini offers ~2x faster latency and 83% lower cost vs full GPT-5
# When GPT-5.1-mini becomes available, set OPENAI_ROUTER_MODEL=gpt-5.1-mini
# Fallback order: gpt-5-mini -> gpt-4o-mini (if GPT-5-mini unavailable)
DEFAULT_ROUTER_MODEL = "gpt-5-mini"


class LLMRouterAgent:
    """GPT-5.1-mini-powered router agent for intelligent intent classification."""

    def __init__(
        self,
        model: Optional[str] = None,
        api_key: Optional[str] = None,
        metrics_emitter: Optional[Any] = None,
    ) -> None:
        self.model = model or os.environ.get("OPENAI_ROUTER_MODEL", DEFAULT_ROUTER_MODEL)
        self.api_key = api_key or os.environ.get("OPENAI_API_KEY")
        self.metrics = metrics_emitter
        if OpenAI is None:
            logger.warning("OpenAI package not available; LLM router will not function")
            self.client = None
        else:
            self.client = OpenAI(api_key=self.api_key) if self.api_key else None

    def classify(self, request: Any) -> RouterDecision:
        """
        Classify user query into purpose, depth, and routing decisions using GPT-5.1-mini.
        
        Args:
            request: NormalizedRequest with query and metadata
            
        Returns:
            RouterDecision with purpose, depth, needs_clarification, etc.
            
        Raises:
            RouterError: If router fails and strict mode is enabled
        """
        if not self.client:
            if settings.strict_mode:
                raise RouterError("OpenAI client not available for router - strict mode enabled")
            logger.warning("OpenAI client not available; falling back to heuristic routing")
            return self._fallback_classify(request)

        query = request.query
        controls = getattr(request, "metadata", {}).get("controls", {}) if hasattr(request, "metadata") else {}
        
        # Extract hints from controls if present
        purpose_hint = None
        depth_hint = None
        if controls:
            purpose_hint = getattr(controls, "purpose", None)
            if purpose_hint and hasattr(purpose_hint, "value"):
                purpose_hint = purpose_hint.value
            depth_hint = getattr(controls, "depth", None)
            if depth_hint and hasattr(depth_hint, "value"):
                depth_hint = depth_hint.value

        # Build JSON schema for structured output
        # Note: Using json_object format instead of json_schema for gpt-4o-mini compatibility
        # When GPT-5.1-mini is available, can switch to json_schema format

        # Build prompt
        user_prompt = f"Classify the following user query:\n\nQuery: {query}\n"
        if purpose_hint:
            user_prompt += f"User-specified purpose hint: {purpose_hint}\n"
        if depth_hint:
            user_prompt += f"User-specified depth hint: {depth_hint}\n"
        user_prompt += (
            "\nAnalyze the query and determine:\n"
            "1. Purpose: Which template best fits this query?\n"
            "2. Depth: How thorough should the research be?\n"
            "3. Needs clarification: Is the query ambiguous or missing critical details?\n"
            "4. Need web: Does this query require web search?\n"
            "\nReturn your classification as structured JSON."
        )

        try:
            # GPT-5-mini uses max_completion_tokens instead of max_tokens
            # GPT-5-mini only supports default temperature (1), not custom values
            use_max_completion_tokens = "gpt-5" in self.model.lower()
            is_gpt5_mini = "gpt-5-mini" in self.model.lower()
            
            request_kwargs = {
                "model": self.model,
                "messages": [
                    {"role": "system", "content": ROUTER_SYSTEM_MESSAGE},
                    {"role": "user", "content": f"{ROUTER_DEVELOPER_MESSAGE}\n\n{user_prompt}\n\nReturn your response as valid JSON with these fields: purpose (one of {SUPPORTED_PURPOSES}), depth (quick/standard/deep), needs_clarification (boolean), need_web (boolean)."},
                ],
                "response_format": {"type": "json_object"},
            }
            
            # GPT-5-mini doesn't support custom temperature, only default (1)
            if not is_gpt5_mini:
                request_kwargs["temperature"] = 0.1  # Low temperature for consistent classification
            
            if use_max_completion_tokens:
                request_kwargs["max_completion_tokens"] = 200
            else:
                request_kwargs["max_tokens"] = 200
            
            response = self.client.chat.completions.create(**request_kwargs)

            # Emit token usage metrics
            if self.metrics and hasattr(response, "usage"):
                usage = response.usage
                self.metrics.emit_token_usage(
                    stage="router_classification",
                    prompt_tokens=getattr(usage, "prompt_tokens", 0),
                    completion_tokens=getattr(usage, "completion_tokens", 0),
                    model=self.model,
                )

            content = response.choices[0].message.content
            if not content:
                if settings.strict_mode:
                    raise RouterError("LLM router returned empty content - strict mode enabled")
                logger.warning("LLM router returned empty content; falling back to heuristic")
                return self._fallback_classify(request)

            parsed = json.loads(content)
            
            purpose = parsed.get("purpose", "custom")
            depth = parsed.get("depth", "standard")
            
            # Use existing profile router logic for consistency
            from app.agents.profile_router import classify_web_profile
            
            profile_decision = classify_web_profile(
                query,
                purpose_hint=purpose,
                depth_hint=depth,
            )
            
            return RouterDecision(
                purpose=purpose,
                depth=depth,
                needs_clarification=parsed.get("needs_clarification", False),
                profile=profile_decision.profile,
                need_deep_research=profile_decision.need_deep_research,
            )

        except json.JSONDecodeError as exc:
            if settings.strict_mode:
                raise RouterError(f"Failed to parse LLM router response as JSON: {exc}") from exc
            logger.warning("Failed to parse LLM router response as JSON: %s", exc)
            return self._fallback_classify(request)
        except Exception as exc:  # noqa: BLE001
            if settings.strict_mode:
                raise RouterError(f"LLM router classification failed: {exc}") from exc
            logger.exception("LLM router classification failed: %s", exc)
            return self._fallback_classify(request)


    def _fallback_classify(self, request: Any) -> RouterDecision:
        """Fallback to heuristic routing if LLM is unavailable."""
        from app.runtime import HeuristicRouter
        
        heuristic = HeuristicRouter()
        return heuristic.classify(request)

