from __future__ import annotations

import asyncio
from typing import Optional

from .models import ResearchStatus, ResearchTask
from .repositories import TaskRepository


async def _render_response(task: ResearchTask) -> str:
    """Placeholder for the deep research renderer.

    A real implementation would orchestrate Agents SDK calls and template
    rendering. Here we simply echo the query in a structured block so the
    retrieval endpoint has something to return when the worker finishes.
    """

    return (
        "# Research Summary\n"
        f"## Query\n{task.query}\n\n"
        "## Findings\nDeep research pipeline not yet connected; this is a placeholder response."
    )


async def process_research_task(task_id: str, repository: TaskRepository) -> Optional[ResearchTask]:
    """Simulate background deep research, updating the task repository.

    The worker advances the task through ``in_progress`` to ``completed``
    (or ``failed`` if an exception occurs) and persists intermediate state via
    the repository. This function can be reused by an async worker loop or a
    task queue consumer.
    """

    task = await repository.get_task(task_id)
    if not task:
        return None

    await repository.set_status(task_id, ResearchStatus.IN_PROGRESS)

    try:
        await asyncio.sleep(0.1)
        rendered = await _render_response(task)
        await repository.set_status(task_id, ResearchStatus.COMPLETED, final_response=rendered)
    except Exception as exc:  # pragma: no cover - placeholder for actual error handling
        await repository.set_status(task_id, ResearchStatus.FAILED, error=str(exc))

    return await repository.get_task(task_id)
