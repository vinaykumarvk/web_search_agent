from __future__ import annotations

from fastapi import BackgroundTasks, Depends, FastAPI, HTTPException

from .models import ResearchTask, ResearchTaskCreate
from .repositories import RepositoryProvider, TaskRepository
from .worker import process_research_task

app = FastAPI(title="Web Research Agent")
_repository_provider = RepositoryProvider()


def get_repository() -> TaskRepository:
    return _repository_provider.get_repository()


@app.post("/research", response_model=ResearchTask, status_code=202)
async def create_research_task(
    payload: ResearchTaskCreate,
    background_tasks: BackgroundTasks,
    repository: TaskRepository = Depends(get_repository),
) -> ResearchTask:
    task = await repository.create_task(payload)
    background_tasks.add_task(process_research_task, task.id, repository)
    return task


@app.get("/research/{task_id}", response_model=ResearchTask)
async def get_research_task(task_id: str, repository: TaskRepository = Depends(get_repository)) -> ResearchTask:
    task = await repository.get_task(task_id)
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
    return task
