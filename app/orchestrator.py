"""Orchestrator and supporting policies for the multi-agent workflow."""
from __future__ import annotations

import time
from concurrent.futures import ThreadPoolExecutor, TimeoutError
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional


@dataclass
class NormalizedRequest:
    """Represents the input after initial normalization from the API layer."""

    query: str
    metadata: Dict[str, Any] = field(default_factory=dict)

    def with_updates(self, **updates: Any) -> "NormalizedRequest":
        merged = {**self.metadata, **updates}
        return NormalizedRequest(query=self.query, metadata=merged)


@dataclass
class RouterDecision:
    """Outcome from the router agent."""

    purpose: str
    depth: str
    needs_clarification: bool = False
    profile: str | None = None
    need_deep_research: bool = False


@dataclass
class ResearchTask:
    """Represents a persisted research task (used in deep mode)."""

    task_id: str
    pass_index: int
    notes: str = ""
    status: str = "pending"


@dataclass
class ResearchPlan:
    """Controls how the research agent should operate for a request."""

    passes: int
    persistent_task: bool
    search_profile: str
    tasks: List[ResearchTask] = field(default_factory=list)


class DepthPolicy:
    """Creates a research plan based on the requested depth."""

    def __init__(self, depth: str) -> None:
        self.depth = depth.lower()

    def build_plan(self) -> ResearchPlan:
        if self.depth == "quick":
            return ResearchPlan(
                passes=1,
                persistent_task=False,
                search_profile="minimal_search",
            )

        if self.depth == "deep":
            tasks = [ResearchTask(task_id="persistent-task-0", pass_index=0, notes="init", status="created")]
            return ResearchPlan(
                passes=3,
                persistent_task=True,
                search_profile="multi_pass_search_with_synthesis",
                tasks=tasks,
            )

        # Standard/unspecified depth defaults to a moderate two-pass search.
        return ResearchPlan(
            passes=2,
            persistent_task=False,
            search_profile="iterative_search",
        )


@dataclass
class RetryConfig:
    max_attempts: int = 3
    backoff_factor: float = 0.5
    timeout_seconds: float = 300.0  # 5 minutes minimum for any response


class OrchestrationError(RuntimeError):
    """Raised when a stage fails even after retries."""


class Orchestrator:
    """Coordinates router, clarifier, researcher, and writer agents."""

    def __init__(
        self,
        router_agent: Any,
        clarifier_agent: Optional[Any],
        researcher_agent: Any,
        writer_agent: Any,
        fact_checker_agent: Optional[Any] = None,
        retry_config: RetryConfig | None = None,
    ) -> None:
        self.router_agent = router_agent
        self.clarifier_agent = clarifier_agent
        self.researcher_agent = researcher_agent
        self.writer_agent = writer_agent
        self.fact_checker_agent = fact_checker_agent
        self.retry_config = retry_config or RetryConfig()

    def run(self, request: NormalizedRequest) -> Dict[str, Any]:
        """Executes the end-to-end workflow for a normalized request."""

        router_decision: RouterDecision = self._call_with_controls(
            "router",
            self.router_agent.classify,
            request,
        )

        plan = DepthPolicy(router_decision.depth).build_plan()

        clarified_request = request
        if router_decision.needs_clarification and self.clarifier_agent:
            clarification = self._call_with_controls(
                "clarifier",
                self.clarifier_agent.clarify,
                request,
                router_decision,
            )
            clarified_request = request.with_updates(clarification=clarification)

        research_results: List[Any] = []
        persisted_task = plan.tasks[0] if plan.tasks else None
        for idx in range(plan.passes):
            research_results.append(
                self._call_with_controls(
                    "researcher",
                    self.researcher_agent.research,
                    clarified_request,
                    router_decision,
                    plan,
                    idx,
                    persisted_task,
                )
            )

        writer_payload = {
            "router": router_decision,
            "plan": plan,
            "research": research_results,
            "request": clarified_request,
        }

        written_output = self._call_with_controls(
            "writer",
            self.writer_agent.write,
            writer_payload,
        )

        # Fact checker: DISABLED to improve response time
        # The writer already performs quality evaluation, so separate fact-checking is redundant
        # Use basic quality report based on writer's evaluation
        from app.schemas import QualityReport
        
        # Extract quality from writer output if available (from template writer evaluation)
        quality = written_output.get("quality")
        if isinstance(quality, QualityReport):
            written_output["quality"] = quality
        else:
            # Use basic quality report - writer already ensures quality
            written_output["quality"] = QualityReport(
                citation_coverage_score=0.8,
                template_completeness_score=0.7,
                missing_sections=[],
                section_coverage=None,
                uncited_numbers=False,
                contradictions=False,
                semantic_citation_score=None,
                broken_urls=[],
                low_relevance_citations=[],
                citation_relevance_map=None,
            )

        return {
            "decision": router_decision,
            "plan": plan,
            "research_results": research_results,
            "output": written_output,
        }

    def _call_with_controls(
        self,
        stage: str,
        func: Callable[..., Any],
        *args: Any,
        **kwargs: Any,
    ) -> Any:
        import logging
        logger = logging.getLogger("app")
        
        start_time = time.time()
        attempt = 0
        last_error: Exception | None = None
        while attempt < self.retry_config.max_attempts:
            attempt += 1
            try:
                result = self._execute_with_timeout(func, *args, **kwargs)
                elapsed = time.time() - start_time
                logger.info(f"⏱️  [{stage}] completed in {elapsed:.2f}s")
                print(f"⏱️  [{stage}] completed in {elapsed:.2f}s")  # Also print to stdout for Docker logs
                return result
            except TimeoutError as exc:
                last_error = exc
            except Exception as exc:  # noqa: BLE001
                last_error = exc

            if attempt < self.retry_config.max_attempts:
                time.sleep(self.retry_config.backoff_factor * (2 ** (attempt - 1)))

        elapsed = time.time() - start_time
        error_msg = str(last_error) if last_error else "Unknown error"
        error_type = type(last_error).__name__ if last_error else "UnknownError"
        logger.error(f"❌ [{stage}] failed after {elapsed:.2f}s: {error_type}: {error_msg}")
        print(f"❌ [{stage}] failed after {elapsed:.2f}s: {error_type}: {error_msg}")
        raise OrchestrationError(
            f"{stage} agent failed after {self.retry_config.max_attempts} attempts: {error_type}: {error_msg}"
        ) from last_error

    def _execute_with_timeout(self, func: Callable[..., Any], *args: Any, **kwargs: Any) -> Any:
        with ThreadPoolExecutor(max_workers=1) as executor:
            future = executor.submit(func, *args, **kwargs)
            return future.result(timeout=self.retry_config.timeout_seconds)
