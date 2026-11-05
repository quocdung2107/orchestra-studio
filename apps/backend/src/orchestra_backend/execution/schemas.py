from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

TaskStatus = Literal[
    "pending", "in_progress", "waiting_approval", "paused", "completed", "failed", "cancelled"
]
RunStatus = Literal[
    "queued",
    "running",
    "waiting_approval",
    "paused",
    "cancel_requested",
    "completed",
    "failed",
    "cancelled",
]


class TaskOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    company_id: uuid.UUID
    parent_task_id: uuid.UUID | None
    assigned_agent_id: uuid.UUID | None
    created_by: str
    title: str
    description: str
    required_role: str | None
    status: TaskStatus
    priority: int
    max_attempts: int
    context_json: dict[str, Any]
    created_at: datetime
    updated_at: datetime
    completed_at: datetime | None
    depends_on: list[uuid.UUID] = Field(default_factory=list)
    # Dependencies that failed or were cancelled: the task stays pending (ADR-0015).
    blocked_by: list[uuid.UUID] = Field(default_factory=list)


class TaskCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    title: str = Field(min_length=1, max_length=300)
    description: str = Field(default="", max_length=4000)
    assigned_agent_id: uuid.UUID | None = None
    required_role: str | None = Field(default=None, min_length=1, max_length=100)
    depends_on: list[uuid.UUID] = Field(default_factory=list, max_length=20)
    max_attempts: int = Field(default=1, ge=1, le=5)
    priority: int = Field(default=0, ge=-10, le=10)

    @model_validator(mode="after")
    def _assignee(self) -> TaskCreate:
        if self.assigned_agent_id is None and not self.required_role:
            raise ValueError("assigned_agent_id or required_role is required")
        return self


class DependencyIn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    depends_on_task_id: uuid.UUID


class RunOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    company_id: uuid.UUID
    agent_id: uuid.UUID
    agent_version_id: uuid.UUID
    task_id: uuid.UUID | None
    runtime_id: str
    attempt: int
    status: RunStatus
    created_at: datetime
    started_at: datetime | None
    finished_at: datetime | None
    result_summary: str | None
    error_code: str | None
    error_summary: str | None
    # Token/cost totals from model runtimes (ADR-0023); None for mock runs.
    usage_json: dict[str, Any] | None = None


class ArtifactOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    company_id: uuid.UUID
    task_id: uuid.UUID | None
    run_id: uuid.UUID | None
    name: str
    mime_type: str
    size_bytes: int
    checksum: str
    created_at: datetime


class RunDetail(RunOut):
    task: TaskOut | None
    agent_name: str
    agent_role: str
    artifacts: list[ArtifactOut]
