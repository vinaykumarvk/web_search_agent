"""Structured schemas for web search request/response."""
from __future__ import annotations

from typing import List, Optional

from pydantic import BaseModel, Field


class TaskContext(BaseModel):
    bank_profile: Optional[dict] = None
    requirement_snippet: Optional[str] = None
    user_goal: Optional[str] = None


class WebSearchRequest(BaseModel):
    query: str
    task_context: Optional[TaskContext] = None
    depth: str = "standard"
    profile: Optional[str] = None


class Finding(BaseModel):
    id: str
    title: str
    type: str = "web"
    relevance: str = "medium"
    source_url: str
    source_name: Optional[str] = None
    snippet: Optional[str] = None
    key_points: List[str] = Field(default_factory=list)


class Evidence(BaseModel):
    id: str
    claim: str
    excerpt: str
    source_id: str
    source_url: str
    confidence: str = "medium"


class WebSearchResponse(BaseModel):
    profile: str
    depth: str
    summary: str
    findings: List[Finding]
    overall_confidence: Optional[str] = None
    notes_for_downstream_agents: List[str] = Field(default_factory=list)
    source_map: Optional[dict[str, str]] = None
