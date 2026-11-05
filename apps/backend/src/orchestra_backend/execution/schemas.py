from __future__ import annotations

import uuid
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict

TaskStatus = Literal["pending", "in_progress", "completed", "failed"]
RunStatus = Literal["queued", "running", "completed", "failed"]


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
    created_at: datetime
    updated_at: datetime
    completed_at: datetime | None


class RunOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    company_id: uuid.UUID
    agent_id: uuid.UUID
    agent_version_id: uuid.UUID
    task_id: uuid.UUID | None
    runtime_id: str
    status: RunStatus
    created_at: datetime
    started_at: datetime | None
    finished_at: datetime | None
    result_summary: str | None
    error_code: str | None
    error_summary: str | None


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
