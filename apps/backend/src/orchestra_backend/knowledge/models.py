from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import ForeignKey, Index, String
from sqlalchemy.orm import Mapped, mapped_column

from orchestra_backend.db.base import Base, IdMixin, TimestampMixin

KNOWLEDGE_KINDS = ("note", "document", "summary", "lesson")
SOURCE_TYPES = ("manual", "artifact", "task_summary", "lesson")
MAX_CONTENT = 100_000


class KnowledgeItem(IdMixin, TimestampMixin, Base):
    """Knowledge with provenance (ADR-0019). Search index: knowledge_fts (FTS5) when available."""

    __tablename__ = "knowledge_items"
    __table_args__ = (Index("ix_knowledge_company_status", "company_id", "status", "updated_at"),)

    company_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("companies.id"))
    title: Mapped[str] = mapped_column(String(300))
    content: Mapped[str] = mapped_column(String(MAX_CONTENT))
    kind: Mapped[str] = mapped_column(String(20))
    source_type: Mapped[str] = mapped_column(String(20))
    source_id: Mapped[str | None] = mapped_column(String(100), default=None)
    created_by: Mapped[str] = mapped_column(String(100), default="user")
    version: Mapped[int] = mapped_column(default=1)
    status: Mapped[str] = mapped_column(String(20), default="active")
    metadata_json: Mapped[dict[str, Any]] = mapped_column(default=dict)


class Lesson(IdMixin, TimestampMixin, Base):
    """Proposed learning; becomes knowledge only after human approval (ADR-0020)."""

    __tablename__ = "lessons"
    __table_args__ = (Index("ix_lessons_company_status", "company_id", "review_status"),)

    company_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("companies.id"))
    title: Mapped[str] = mapped_column(String(300))
    lesson: Mapped[str] = mapped_column(String(4000))
    source_task_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("tasks.id"), default=None)
    source_run_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("agent_runs.id"), default=None
    )
    proposed_by: Mapped[str] = mapped_column(String(100))
    review_status: Mapped[str] = mapped_column(String(20), default="proposed")
    review_note: Mapped[str | None] = mapped_column(String(2000), default=None)
    reviewed_at: Mapped[datetime | None] = mapped_column(default=None)
    knowledge_item_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("knowledge_items.id"), default=None
    )


class RoleChangeProposal(IdMixin, TimestampMixin, Base):
    """Agent or user proposes an org change; only a human applies it (ADR-0020)."""

    __tablename__ = "role_change_proposals"
    __table_args__ = (Index("ix_role_proposals_company_status", "company_id", "status"),)

    company_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("companies.id"))
    agent_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("agents.id"))
    changes_json: Mapped[dict[str, Any]] = mapped_column(default=dict)
    rationale: Mapped[str] = mapped_column(String(2000), default="")
    proposed_by: Mapped[str] = mapped_column(String(100))
    source_run_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("agent_runs.id"), default=None
    )
    status: Mapped[str] = mapped_column(String(20), default="proposed")
    review_note: Mapped[str | None] = mapped_column(String(2000), default=None)
    reviewed_at: Mapped[datetime | None] = mapped_column(default=None)
