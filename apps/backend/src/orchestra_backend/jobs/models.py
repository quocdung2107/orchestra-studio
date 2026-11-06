from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import ForeignKey, Index, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from orchestra_backend.core.time import utcnow
from orchestra_backend.db.base import Base, IdMixin, TimestampMixin

JOB_STATUSES = ("queued", "running", "succeeded", "failed", "cancelled")
JOB_TERMINAL = {"succeeded", "failed", "cancelled"}


class Job(IdMixin, TimestampMixin, Base):
    """Durable background job (ADR-0029). Survives restarts via leases."""

    __tablename__ = "jobs"
    __table_args__ = (
        UniqueConstraint("company_id", "idempotency_key"),
        Index("ix_jobs_status_next_run", "status", "next_run_at"),
        Index("ix_jobs_subject", "subject_id"),
    )

    company_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("companies.id"))
    kind: Mapped[str] = mapped_column(String(50))
    # Entity the job works on (e.g. a video project), for listing and cancellation.
    subject_id: Mapped[uuid.UUID | None] = mapped_column(default=None)
    payload_json: Mapped[dict[str, Any]] = mapped_column(default=dict)
    status: Mapped[str] = mapped_column(String(20), default="queued")
    priority: Mapped[int] = mapped_column(default=0)
    attempts: Mapped[int] = mapped_column(default=0)
    max_attempts: Mapped[int] = mapped_column(default=2)
    deferrals: Mapped[int] = mapped_column(default=0)
    next_run_at: Mapped[datetime] = mapped_column(default=utcnow)
    lease_until: Mapped[datetime | None] = mapped_column(default=None)
    idempotency_key: Mapped[str | None] = mapped_column(String(200), default=None)
    engine: Mapped[str | None] = mapped_column(String(50), default=None)
    cancel_requested: Mapped[bool] = mapped_column(default=False)
    progress: Mapped[float] = mapped_column(default=0.0)
    progress_note: Mapped[str] = mapped_column(String(300), default="")
    result_json: Mapped[dict[str, Any] | None] = mapped_column(default=None)
    error_code: Mapped[str | None] = mapped_column(String(100), default=None)
    error: Mapped[str | None] = mapped_column(String(2000), default=None)
    started_at: Mapped[datetime | None] = mapped_column(default=None)
    finished_at: Mapped[datetime | None] = mapped_column(default=None)
