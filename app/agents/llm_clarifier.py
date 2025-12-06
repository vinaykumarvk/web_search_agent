"""LLM-based clarifier agent using GPT-5.1-mini for intelligent question generation."""
from __future__ import annotations

import json
import logging
import os
from typing import Any, Dict, Optional

try:
    from openai import OpenAI  # type: ignore
except Exception:  # pragma: no cover - optional dependency
    OpenAI = None  # type: ignore

from app.agents.clarifier import CLARIFIER_SYSTEM_MESSAGE, CLARIFIER_DEVELOPER_MESSAGE
from app.config import load_settings
from app.exceptions import ClarifierError
from app.orchestrator import RouterDecision
from app.observability import MetricsEmitter

logger = logging.getLogger(__name__)
settings = load_settings()

# Use GPT-5-mini (faster and cheaper than GPT-5.1, perfect for question generation)
# GPT-5-mini offers ~2x faster latency and 83% lower cost vs full GPT-5
# When GPT-5.1-mini becomes available, set OPENAI_CLARIFIER_MODEL=gpt-5.1-mini
# Fallback order: gpt-5-mini -> gpt-4o-mini (if GPT-5-mini unavailable)
DEFAULT_CLARIFIER_MODEL = "gpt-5-mini"


class LLMClarifierAgent:
    """GPT-5.1-mini-powered clarifier agent for asking targeted clarification questions."""

    def __init__(
        self,
        model: Optional[str] = None,
        api_key: Optional[str] = None,
        metrics_emitter: Optional[Any] = None,
    ) -> None:
        # Allow explicit model override via parameter or env var, otherwise use default
        self.model = model or os.environ.get("OPENAI_CLARIFIER_MODEL", DEFAULT_CLARIFIER_MODEL)
        self.api_key = api_key or os.environ.get("OPENAI_API_KEY")
        self.metrics = metrics_emitter
        if OpenAI is None:
            logger.warning("OpenAI package not available; LLM clarifier will not function")
            self.client = None
        else:
            self.client = OpenAI(api_key=self.api_key) if self.api_key else None

    def clarify(self, request: Any, decision: RouterDecision) -> Dict[str, str]:
        """
        Generate 2-3 targeted clarification questions when query is ambiguous.
        
        Args:
            request: NormalizedRequest with query and metadata
            decision: RouterDecision indicating what needs clarification
            
        Returns:
            Dictionary with clarification questions and updated query context
        """
        if not self.client:
            logger.warning("OpenAI client not available for clarifier; proceeding without clarification")
            if self.metrics:
                self.metrics.emit_clarifier_unavailable()
            return {"query": request.query, "clarification_skipped": True}

        query = request.query
        controls = getattr(request, "metadata", {}).get("controls", {}) if hasattr(request, "metadata") else {}

        # Note: Using json_object format instead of json_schema for gpt-4o-mini compatibility

        # Build prompt
        user_prompt = (
            f"The user query is ambiguous and needs clarification:\n\n"
            f"Query: {query}\n\n"
            f"Router Decision:\n"
            f"- Purpose: {decision.purpose}\n"
            f"- Depth: {decision.depth}\n"
            f"- Needs clarification: {decision.needs_clarification}\n\n"
        )

        # Add context about what might be missing
        missing_context = []
        if not controls or not getattr(controls, "audience", None):
            missing_context.append("audience (exec, product, engineering, mixed)")
        if not controls or not getattr(controls, "region", None):
            missing_context.append("region (APAC, Global, US, etc.)")
        if not controls or not getattr(controls, "timeframe", None):
            missing_context.append("timeframe (last 6 months, last year, all time, etc.)")
        if decision.purpose == "custom":
            missing_context.append("purpose/template type (BRD, company research, requirement elaboration, etc.)")

        if missing_context:
            user_prompt += (
                f"Potentially missing context: {', '.join(missing_context)}\n\n"
            )

        user_prompt += (
            "Generate 2-3 targeted questions to clarify the ambiguous aspects. "
            "Focus on:\n"
            "- Purpose/template type (if unclear)\n"
            "- Timeframe (if relevant)\n"
            "- Audience (if relevant)\n"
            "- Region (if relevant)\n"
            "- Depth (if unclear)\n\n"
            "Keep questions brief and avoid asking about facts that require research."
        )

        try:
            # GPT-5-mini uses max_completion_tokens instead of max_tokens
            # GPT-5-mini only supports default temperature (1), not custom values
            use_max_completion_tokens = "gpt-5" in self.model.lower()
            is_gpt5_mini = "gpt-5-mini" in self.model.lower()
            
            request_kwargs = {
                "model": self.model,
                "messages": [
                    {"role": "system", "content": CLARIFIER_SYSTEM_MESSAGE},
                    {"role": "user", "content": f"{CLARIFIER_DEVELOPER_MESSAGE}\n\n{user_prompt}\n\nReturn your response as valid JSON with these fields: questions (array of 1-3 strings), clarified_query (string)."},
                ],
                "response_format": {"type": "json_object"},
            }
            
            # GPT-5-mini doesn't support custom temperature, only default (1)
            if not is_gpt5_mini:
                request_kwargs["temperature"] = 0.3  # Slightly higher for question generation
            
            if use_max_completion_tokens:
                request_kwargs["max_completion_tokens"] = 300
            else:
                request_kwargs["max_tokens"] = 300
            
            response = self.client.chat.completions.create(**request_kwargs)

            # Emit token usage metrics
            if self.metrics and hasattr(response, "usage"):
                usage = response.usage
                self.metrics.emit_token_usage(
                    stage="clarifier_questions",
                    prompt_tokens=getattr(usage, "prompt_tokens", 0),
                    completion_tokens=getattr(usage, "completion_tokens", 0),
                    model=self.model,
                )

            content = response.choices[0].message.content
            if not content:
                logger.warning("LLM clarifier returned empty content; proceeding without clarification")
                if self.metrics:
                    self.metrics.emit_clarifier_unavailable()
                return {"query": request.query, "clarification_skipped": True}

            parsed = json.loads(content)
            questions = parsed.get("questions", [])
            clarified_query = parsed.get("clarified_query", query)

            # Return questions and updated query context
            result = {"query": clarified_query}
            if questions:
                result["clarification_questions"] = questions
                logger.info(
                    "Generated clarification questions",
                    extra={"questions": questions, "query": query},
                )

            return result

        except json.JSONDecodeError as exc:
            logger.warning("Failed to parse LLM clarifier response as JSON: %s; proceeding without clarification", exc)
            if self.metrics:
                self.metrics.emit_clarifier_unavailable()
            return {"query": request.query, "clarification_skipped": True}
        except Exception as exc:  # noqa: BLE001
            logger.exception("LLM clarifier failed: %s; proceeding without clarification", exc)
            if self.metrics:
                self.metrics.emit_clarifier_unavailable()
            return {"query": request.query, "clarification_skipped": True}

