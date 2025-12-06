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
    QUEUED = "queued"
    PENDING = "pending"
    RUNNING = "running"
    WRITING = "writing"
    VALIDATING = "validating"
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


class QualityReport(BaseModel):
    citation_coverage_score: float
    template_completeness_score: float
    missing_sections: List[str] = Field(default_factory=list)
    section_coverage: Optional[dict[str, float]] = None
    uncited_numbers: bool = False
    contradictions: bool = False
    semantic_citation_score: Optional[float] = None
    broken_urls: List[str] = Field(default_factory=list)
    low_relevance_citations: List[str] = Field(default_factory=list)
    citation_relevance_map: Optional[dict[str, float]] = None


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
    open_questions: List[str] = Field(default_factory=list)
    next_steps: List[str]


class ResearchResponse(BaseModel):
    envelope: ResponseEnvelope
    quality: Optional[QualityReport] = None
    bibliography: Optional[str] = None
    source_map: Optional[dict[str, str]] = None
    notes: Optional[list[str]] = None
    findings: Optional[list[dict]] = None
    evidence: Optional[list[dict]] = None
    overall_confidence: Optional[str] = None


class ResearchTaskCreated(BaseModel):
    task_id: str
    status: TaskStatus = TaskStatus.QUEUED
    estimated_mode: str = "async"
    message: str = "Research task created. Poll the task endpoint for updates."


class ResearchTaskStatus(BaseModel):
    task_id: str
    status: TaskStatus
    envelope: Optional[ResponseEnvelope] = None
    quality: Optional[QualityReport] = None
    bibliography: Optional[str] = None
    source_map: Optional[dict[str, str]] = None
    notes: Optional[list[str]] = None
    findings: Optional[list[dict]] = None
    evidence: Optional[list[dict]] = None
    overall_confidence: Optional[str] = None
    error: Optional[str] = None
