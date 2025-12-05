from __future__ import annotations

import itertools
from dataclasses import asdict
from typing import Dict, Iterable, List, Mapping

from .citations import Citation
from .router import route_request
from .templates import render_envelope, render_template


class FakeSearchProvider:
    """Deterministic search provider that returns fixed sources for tests."""

    def __init__(self, sources: Iterable[Mapping[str, str]]):
        self.sources = list(sources)

    def search(self, query: str) -> List[Mapping[str, str]]:
        return [dict(item, query=query) for item in self.sources]


class FakeDeepResearchClient:
    """Tiny in-memory stand-in for a deep research/Agents SDK workflow."""

    def __init__(self, search_provider: FakeSearchProvider):
        self.search_provider = search_provider
        self.tasks: Dict[str, Dict] = {}
        self._counter = itertools.count(1)

    def create_task(self, prompt: str, purpose_hint: str | None = None, depth_hint: str | None = None) -> Dict:
        decision = route_request(prompt, purpose_hint, depth_hint)
        task_id = f"task_{next(self._counter)}"
        self.tasks[task_id] = {
            "id": task_id,
            "prompt": prompt,
            "purpose": decision.purpose,
            "depth": decision.depth,
            "status": "queued",
        }
        return {"id": task_id, "status": "queued"}

    def retrieve_task(self, task_id: str) -> Dict:
        task = self.tasks[task_id]
        if task["status"] != "completed":
            sources = [
                Citation(title=item["title"], url=item["url"], snippet=item["snippet"])
                for item in self.search_provider.search(task["prompt"])
            ]
            deliverable = render_template(
                task["purpose"],
                {
                    "problem": task["prompt"],
                    "goals": "High level goals based on prompt.",
                    "overview": f"Summary for {task['prompt']}",
                    "moves": "Key announcements and launches.",
                    "user_story": f"As a user I want {task['prompt']}...",
                    "acceptance": "Clear success criteria.",
                    "summary": "Market snapshot for the request.",
                    "signals": "Competition summary.",
                    "notes": task["prompt"],
                },
            )
            summary = f"Deep research on '{task['prompt']}' using depth={task['depth']}"
            envelope = render_envelope(
                title="Deep Research",
                summary=summary,
                deliverable=deliverable,
                sources=sources,
                assumptions=["Limited to deterministic fixtures"],
                next_steps=["Review citations", "Request a refresh if needed"],
            )
            task.update({"status": "completed", "response": envelope, "citations": sources})
        return task


__all__ = ["FakeSearchProvider", "FakeDeepResearchClient"]
