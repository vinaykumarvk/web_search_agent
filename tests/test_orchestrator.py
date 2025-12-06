from __future__ import annotations

import time
import unittest

from app.orchestrator import (
    DepthPolicy,
    NormalizedRequest,
    OrchestrationError,
    Orchestrator,
    ResearchPlan,
    ResearchTask,
    RetryConfig,
    RouterDecision,
)


class StubRouter:
    def __init__(self, decision: RouterDecision) -> None:
        self.decision = decision
        self.call_count = 0

    def classify(self, _request: NormalizedRequest) -> RouterDecision:
        self.call_count += 1
        return self.decision


class StubClarifier:
    def __init__(self, clarification: dict) -> None:
        self.clarification = clarification
        self.call_count = 0

    def clarify(self, request: NormalizedRequest, _decision: RouterDecision) -> dict:
        self.call_count += 1
        return {**self.clarification, "original": request.query}


class StubResearcher:
    def __init__(self) -> None:
        self.calls = []

    def research(
        self,
        request: NormalizedRequest,
        decision: RouterDecision,
        plan: ResearchPlan,
        pass_index: int,
        persisted_task: ResearchTask | None,
    ) -> dict:
        record = {
            "query": request.query,
            "pass_index": pass_index,
            "depth": decision.depth,
            "persistent": persisted_task.task_id if persisted_task else None,
            "profile": plan.search_profile,
        }
        self.calls.append(record)
        return record


class StubWriter:
    def __init__(self) -> None:
        self.received_payload = None
        self.call_count = 0

    def write(self, payload: dict) -> dict:
        self.call_count += 1
        self.received_payload = payload
        return {"status": "ok", "summary": payload["router"].purpose}


class RetryAgent:
    def __init__(self, failures: int) -> None:
        self.failures_remaining = failures
        self.calls = 0

    def classify(self, _request: NormalizedRequest) -> RouterDecision:
        self.calls += 1
        if self.failures_remaining:
            self.failures_remaining -= 1
            raise RuntimeError("planned failure")
        return RouterDecision(purpose="test", depth="quick")


class TimeoutAgent:
    def __init__(self, sleep_seconds: float) -> None:
        self.sleep_seconds = sleep_seconds
        self.calls = 0

    def classify(self, _request: NormalizedRequest) -> RouterDecision:
        self.calls += 1
        time.sleep(self.sleep_seconds)
        return RouterDecision(purpose="slow", depth="quick")


class OrchestratorTests(unittest.TestCase):
    def test_depth_policy_plans(self) -> None:
        quick_plan = DepthPolicy("quick").build_plan()
        self.assertEqual(1, quick_plan.passes)
        self.assertFalse(quick_plan.persistent_task)
        self.assertEqual("minimal_search", quick_plan.search_profile)

        deep_plan = DepthPolicy("deep").build_plan()
        self.assertEqual(3, deep_plan.passes)
        self.assertTrue(deep_plan.persistent_task)
        self.assertEqual("multi_pass_search_with_synthesis", deep_plan.search_profile)
        self.assertTrue(deep_plan.tasks)

    def test_orchestrator_runs_all_agents(self) -> None:
        router = StubRouter(RouterDecision(purpose="company_research", depth="deep", needs_clarification=True))
        clarifier = StubClarifier({"region": "apac"})
        researcher = StubResearcher()
        writer = StubWriter()
        orchestrator = Orchestrator(router, clarifier, researcher, writer)

        request = NormalizedRequest(query="Research ACME")
        result = orchestrator.run(request)

        self.assertEqual(router.call_count, 1)
        self.assertEqual(clarifier.call_count, 1)
        self.assertEqual(writer.call_count, 1)
        self.assertEqual(len(result["research_results"]), 3)
        self.assertEqual(result["plan"].search_profile, "multi_pass_search_with_synthesis")
        self.assertEqual(result["decision"].purpose, "company_research")
        self.assertEqual(result["research_results"][0]["persistent"], "persistent-task-0")

    def test_retries_and_timeout(self) -> None:
        retry_router = RetryAgent(failures=1)
        researcher = StubResearcher()
        writer = StubWriter()
        retry_config = RetryConfig(max_attempts=2, backoff_factor=0.0, timeout_seconds=0.05)
        orchestrator = Orchestrator(retry_router, None, researcher, writer, retry_config=retry_config)
        request = NormalizedRequest(query="hello")

        result = orchestrator.run(request)
        self.assertEqual(retry_router.calls, 2)
        self.assertEqual(result["decision"].purpose, "test")

        timeout_router = TimeoutAgent(sleep_seconds=0.1)
        orchestrator_timeout = Orchestrator(timeout_router, None, researcher, writer, retry_config=retry_config)
        with self.assertRaises(OrchestrationError):
            orchestrator_timeout.run(request)
        self.assertGreaterEqual(timeout_router.calls, retry_config.max_attempts)


if __name__ == "__main__":
    unittest.main()
