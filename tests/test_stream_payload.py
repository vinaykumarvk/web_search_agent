import json

from app.main import app, _tasks
from app.schemas import ResearchTaskStatus, TaskStatus
from fastapi.testclient import TestClient


def test_stream_emits_findings_and_status():
    client = TestClient(app)
    task_id = "task_stream"
    _tasks[task_id] = ResearchTaskStatus(
        task_id=task_id,
        status=TaskStatus.COMPLETED,
        findings=[{"id": "F1", "title": "Finding"}],
        evidence=[{"id": "E1", "claim": "Claim"}],
    )

    with client.stream("GET", f"/v1/agent/tasks/{task_id}/stream") as response:
        events = []
        for line in response.iter_lines():
            if line:
                events.append(line if isinstance(line, str) else line.decode("utf-8"))
            if len(events) >= 3:
                break

    assert any("event: findings" in e for e in events)
    assert any("event: status" in e or "event: writing" in e for e in events)
