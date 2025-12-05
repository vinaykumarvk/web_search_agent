from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Optional

from pydantic import BaseModel, Field


class ResearchStatus(str, Enum):
    QUEUED = "queued"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    FAILED = "failed"


class ResearchTaskCreate(BaseModel):
    query: str = Field(..., description="User prompt to research")
    mode: str = Field("deep", description="Requested research depth")


class ResearchTask(BaseModel):
    id: str
    query: str
    mode: str
    status: ResearchStatus
    created_at: datetime
    updated_at: datetime
    final_response: Optional[str] = None
    error: Optional[str] = None

    class Config:
        use_enum_values = True
