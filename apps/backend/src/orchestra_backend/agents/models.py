from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import ForeignKey, Index, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from orchestra_backend.core.time import utcnow
from orchestra_backend.db.base import Base, IdMixin, TimestampMixin


class Agent(IdMixin, TimestampMixin, Base):
    """Agent identity/configuration. Not a running process (ARCHITECTURE §8)."""

    __tablename__ = "agents"
    __table_args__ = (Index("ix_agents_company_status", "company_id", "status"),)

    company_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("companies.id"))
    reports_to_agent_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("agents.id"), default=None
    )
    name: Mapped[str] = mapped_column(String(200))
    role: Mapped[str] = mapped_column(String(100))
    description: Mapped[str] = mapped_column(String(2000), default="")
    status: Mapped[str] = mapped_column(String(20), default="draft")
    # Points at agent_versions.id; no FK to avoid a circular constraint (enforced in service).
    current_version_id: Mapped[uuid.UUID | None] = mapped_column(default=None)


class AgentVersion(IdMixin, Base):
    __tablename__ = "agent_versions"
    __table_args__ = (UniqueConstraint("agent_id", "version_number", name="uq_agent_versions"),)

    agent_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("agents.id"))
    version_number: Mapped[int]
    definition_json: Mapped[dict[str, Any]]
    runtime_preference_json: Mapped[dict[str, Any]]
    created_by: Mapped[str] = mapped_column(String(100), default="user")
    created_at: Mapped[datetime] = mapped_column(default=utcnow)
