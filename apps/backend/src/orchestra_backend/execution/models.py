from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import ForeignKey, Index, String
from sqlalchemy.orm import Mapped, mapped_column

from orchestra_backend.core.time import utcnow
from orchestra_backend.db.base import Base, IdMixin, TimestampMixin

TASK_STATUSES = ("pending", "in_progress", "completed", "failed")
RUN_STATUSES = ("queued", "running", "completed", "failed")
RUN_TERMINAL = {"completed", "failed"}


class Task(IdMixin, TimestampMixin, Base):
    """Minimal P0 task (ADR-0004): no dependencies, no parallelism."""

    __tablename__ = "tasks"
    __table_args__ = (
        Index("ix_tasks_company_status", "company_id", "status", "created_at"),
        Index("ix_tasks_assignee_status", "assigned_agent_id", "status"),
    )

    company_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("companies.id"))
    parent_task_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("tasks.id"), default=None)
    assigned_agent_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("agents.id"), default=None
    )
    created_by: Mapped[str] = mapped_column(String(100))
    title: Mapped[str] = mapped_column(String(300))
    description: Mapped[str] = mapped_column(String(4000), default="")
    required_role: Mapped[str | None] = mapped_column(String(100), default=None)
    status: Mapped[str] = mapped_column(String(20), default="pending")
    priority: Mapped[int] = mapped_column(default=0)
    completed_at: Mapped[datetime | None] = mapped_column(default=None)


class AgentRun(IdMixin, Base):
    """One execution attempt. Never overwritten by retries."""

    __tablename__ = "agent_runs"
    __table_args__ = (
        Index("ix_agent_runs_agent_created", "agent_id", "created_at"),
        Index("ix_agent_runs_task_created", "task_id", "created_at"),
        Index("ix_agent_runs_company_created", "company_id", "created_at"),
    )

    company_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("companies.id"))
    agent_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("agents.id"))
    agent_version_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("agent_versions.id"))
    task_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("tasks.id"), default=None)
    runtime_id: Mapped[str] = mapped_column(String(50))
    worker_id: Mapped[str | None] = mapped_column(String(100), default=None)
    status: Mapped[str] = mapped_column(String(20), default="queued")
    created_at: Mapped[datetime] = mapped_column(default=utcnow)
    started_at: Mapped[datetime | None] = mapped_column(default=None)
    finished_at: Mapped[datetime | None] = mapped_column(default=None)
    input_json: Mapped[dict[str, Any]] = mapped_column(default=dict)
    result_summary: Mapped[str | None] = mapped_column(String(4000), default=None)
    error_code: Mapped[str | None] = mapped_column(String(100), default=None)
    error_summary: Mapped[str | None] = mapped_column(String(2000), default=None)
    usage_json: Mapped[dict[str, Any] | None] = mapped_column(default=None)


class Artifact(IdMixin, Base):
    __tablename__ = "artifacts"
    __table_args__ = (Index("ix_artifacts_task_created", "task_id", "created_at"),)

    company_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("companies.id"))
    task_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("tasks.id"), default=None)
    run_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("agent_runs.id"), default=None)
    name: Mapped[str] = mapped_column(String(255))
    mime_type: Mapped[str] = mapped_column(String(100))
    size_bytes: Mapped[int]
    storage_uri: Mapped[str] = mapped_column(String(500))
    checksum: Mapped[str] = mapped_column(String(100))
    created_at: Mapped[datetime] = mapped_column(default=utcnow)
    access_policy_json: Mapped[dict[str, Any]] = mapped_column(default=dict)
