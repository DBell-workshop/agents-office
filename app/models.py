from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Literal, Optional
from uuid import uuid4

from pydantic import BaseModel, Field


TaskStatus = Literal["pending", "running", "succeeded", "failed"]


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def make_id(prefix: str) -> str:
    return f"{prefix}_{uuid4().hex[:10]}"


class CourseCreateRequest(BaseModel):
    product_id: str
    product_name: str
    objective: str
    required_points: list[str] = Field(default_factory=list)
    product_facts: dict[str, str] = Field(default_factory=dict)


class GenerateContentRequest(BaseModel):
    script_style: str = "natural"
    scene: str = "in_store"
    language: str = "zh-CN"


class TrainingAttemptCreateRequest(BaseModel):
    course_id: str
    user_id: str
    audio_url: Optional[str] = None
    mock_transcript: Optional[str] = None


class EvaluateAttemptRequest(BaseModel):
    rubric_version: str = "v1"


class ComparisonTarget(BaseModel):
    platform: str
    url: str


class ComparisonTaskCreateRequest(BaseModel):
    source_product_id: str
    source_product_name: str
    targets: list[ComparisonTarget]


class ComparisonRunRequest(BaseModel):
    template_version: str = "default_v1"


class TaskRecord(BaseModel):
    task_id: str
    trace_id: str
    task_type: str
    status: TaskStatus = "pending"
    created_at: str = Field(default_factory=now_iso)
    updated_at: str = Field(default_factory=now_iso)
    input: dict[str, Any] = Field(default_factory=dict)
    output: Optional[dict[str, Any]] = None
    error: Optional[str] = None


class CourseRecord(BaseModel):
    course_id: str
    created_at: str = Field(default_factory=now_iso)
    updated_at: str = Field(default_factory=now_iso)
    product_id: str
    product_name: str
    objective: str
    required_points: list[str] = Field(default_factory=list)
    product_facts: dict[str, str] = Field(default_factory=dict)
    content_version: int = 0
    latest_content: Optional[dict[str, Any]] = None


class TrainingAttemptRecord(BaseModel):
    attempt_id: str
    course_id: str
    user_id: str
    created_at: str = Field(default_factory=now_iso)
    audio_url: Optional[str] = None
    mock_transcript: Optional[str] = None


class ComparisonTaskRecord(BaseModel):
    comparison_task_id: str
    source_product_id: str
    source_product_name: str
    targets: list[dict[str, str]]
    created_at: str = Field(default_factory=now_iso)


class ApiEnvelope(BaseModel):
    trace_id: str
    request_id: str
    data: dict[str, Any]
    error: Optional[str] = None
