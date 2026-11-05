from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import ForeignKey, Index, String
from sqlalchemy.orm import Mapped, mapped_column

from orchestra_backend.core.time import utcnow
from orchestra_backend.db.base import Base, IdMixin

APPROVAL_STATUSES = ("pending", "approved", "rejected", "expired", "cancelled")


class Approval(IdMixin, Base):
    """Human decision bound to an exact action payload by checksum (ADR-0018, SECURITY §8)."""

    __tablename__ = "approvals"
    __table_args__ = (Index("ix_approvals_company_status", "company_id", "status", "created_at"),)

    company_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("companies.id"))
    run_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("agent_runs.id"), default=None)
    task_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("tasks.id"), default=None)
    requested_by_agent_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("agents.id"), default=None
    )
    tool_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("tools.id"), default=None)
    action_type: Mapped[str] = mapped_column(String(120))
    request_json: Mapped[dict[str, Any]] = mapped_column(default=dict)
    checksum: Mapped[str] = mapped_column(String(100))
    required_level: Mapped[int] = mapped_column(default=3)
    status: Mapped[str] = mapped_column(String(20), default="pending")
    decided_by: Mapped[str | None] = mapped_column(String(100), default=None)
    decision_note: Mapped[str | None] = mapped_column(String(2000), default=None)
    decided_at: Mapped[datetime | None] = mapped_column(default=None)
    execution_status: Mapped[str | None] = mapped_column(String(20), default=None)
    result_json: Mapped[dict[str, Any] | None] = mapped_column(default=None)
    executed_at: Mapped[datetime | None] = mapped_column(default=None)
    created_at: Mapped[datetime] = mapped_column(default=utcnow)
