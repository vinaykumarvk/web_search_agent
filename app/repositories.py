from __future__ import annotations

import asyncio
import uuid
from datetime import datetime
from typing import Dict, Optional, Protocol

from .models import ResearchStatus, ResearchTask, ResearchTaskCreate


class TaskRepository(Protocol):
    async def create_task(self, payload: ResearchTaskCreate) -> ResearchTask:
        ...

    async def get_task(self, task_id: str) -> Optional[ResearchTask]:
        ...

    async def set_status(
        self,
        task_id: str,
        status: ResearchStatus,
        final_response: Optional[str] = None,
        error: Optional[str] = None,
    ) -> Optional[ResearchTask]:
        ...


class InMemoryTaskRepository:
    """Thread-safe in-memory repository for research tasks.

    Designed to be swapped out for DB or cache-backed implementations by
    reusing the ``TaskRepository`` protocol.
    """

    def __init__(self) -> None:
        self._tasks: Dict[str, ResearchTask] = {}
        self._lock = asyncio.Lock()

    async def create_task(self, payload: ResearchTaskCreate) -> ResearchTask:
        async with self._lock:
            now = datetime.utcnow()
            task = ResearchTask(
                id=str(uuid.uuid4()),
                query=payload.query,
                mode=payload.mode,
                status=ResearchStatus.QUEUED,
                created_at=now,
                updated_at=now,
            )
            self._tasks[task.id] = task
            return task

    async def get_task(self, task_id: str) -> Optional[ResearchTask]:
        async with self._lock:
            return self._tasks.get(task_id)

    async def set_status(
        self,
        task_id: str,
        status: ResearchStatus,
        final_response: Optional[str] = None,
        error: Optional[str] = None,
    ) -> Optional[ResearchTask]:
        async with self._lock:
            task = self._tasks.get(task_id)
            if not task:
                return None
            updated = task.copy(
                update={
                    "status": status,
                    "updated_at": datetime.utcnow(),
                    "final_response": final_response,
                    "error": error,
                }
            )
            self._tasks[task_id] = updated
            return updated


class RepositoryProvider:
    """Minimal provider that can return different repository backends.

    Today we only ship the in-memory repository but consumers can swap in a
    database-backed implementation without changing handlers.
    """

    def __init__(self, backend: str = "memory") -> None:
        if backend != "memory":
            raise ValueError(f"Unsupported backend: {backend}")
        self._repo: TaskRepository = InMemoryTaskRepository()

    def get_repository(self) -> TaskRepository:
        return self._repo
