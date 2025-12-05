from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import List, Optional

from pydantic import BaseModel, Field


class Purpose(str, Enum):
    BRD = "brd"
    COMPANY_RESEARCH = "company_research"
    REQ_ELABORATION = "req_elaboration"
    MARKET_QUERY = "market_query"
    CUSTOM = "custom"


class Depth(str, Enum):
    QUICK = "quick"
    STANDARD = "standard"
    DEEP = "deep"


class Audience(str, Enum):
    EXEC = "exec"
    PRODUCT = "product"
    ENGINEERING = "engineering"
    MIXED = "mixed"


class TaskStatus(str, Enum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"


class ResearchControls(BaseModel):
    purpose: Purpose = Purpose.CUSTOM
    depth: Depth = Depth.QUICK
    audience: Audience = Audience.MIXED
    region: Optional[str] = None
    timeframe: Optional[str] = None
    output_format: str = "markdown"
    async_mode: bool = Field(
        False,
        description="Whether to run the research asynchronously and poll for results.",
    )


class ResearchRequest(BaseModel):
    query: str = Field(..., description="User research request or problem statement.")
    controls: ResearchControls = Field(
        default_factory=ResearchControls,
        description="Optional controls to influence the research strategy.",
    )


class Citation(BaseModel):
    source: str
    url: Optional[str] = None
    note: Optional[str] = None


class ResponseMetadata(BaseModel):
    purpose: Purpose
    depth: Depth
    audience: Audience
    region: Optional[str] = None
    timeframe: Optional[str] = None
    task_id: Optional[str] = None
    status: TaskStatus = TaskStatus.COMPLETED
    created_at: datetime = Field(default_factory=datetime.utcnow)


class ResponseEnvelope(BaseModel):
    title: str
    metadata: ResponseMetadata
    executive_summary: str
    deliverable: str
    citations: List[Citation]
    assumptions_and_gaps: str
    next_steps: List[str]


class ResearchResponse(BaseModel):
    envelope: ResponseEnvelope


class ResearchTaskCreated(BaseModel):
    task_id: str
    status: TaskStatus = TaskStatus.PENDING
    message: str = "Research task created. Poll the task endpoint for updates."


class ResearchTaskStatus(BaseModel):
    task_id: str
    status: TaskStatus
    envelope: Optional[ResponseEnvelope] = None
    error: Optional[str] = None
