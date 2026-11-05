from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import ForeignKey, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from orchestra_backend.core.time import utcnow
from orchestra_backend.db.base import Base, IdMixin, TimestampMixin


class Skill(IdMixin, TimestampMixin, Base):
    __tablename__ = "skills"
    __table_args__ = (UniqueConstraint("company_id", "name", name="uq_skills_company_name"),)

    company_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("companies.id"))
    name: Mapped[str] = mapped_column(String(200))
    description: Mapped[str] = mapped_column(String(2000), default="")
    status: Mapped[str] = mapped_column(String(20), default="active")
    latest_version_id: Mapped[uuid.UUID | None] = mapped_column(default=None)


class SkillVersion(IdMixin, Base):
    __tablename__ = "skill_versions"
    __table_args__ = (UniqueConstraint("skill_id", "version_number", name="uq_skill_versions"),)

    skill_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("skills.id"))
    version_number: Mapped[int]
    instructions: Mapped[str] = mapped_column(String(20000), default="")
    input_hints_json: Mapped[dict[str, Any]] = mapped_column(default=dict)
    created_by: Mapped[str] = mapped_column(String(100), default="user")
    created_at: Mapped[datetime] = mapped_column(default=utcnow)


class AgentSkill(Base):
    """Agent uses a skill pinned to one version (ADR-0012)."""

    __tablename__ = "agent_skills"

    agent_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("agents.id"), primary_key=True)
    skill_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("skills.id"), primary_key=True)
    skill_version_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("skill_versions.id"))
    attached_at: Mapped[datetime] = mapped_column(default=utcnow)


class Tool(IdMixin, TimestampMixin, Base):
    __tablename__ = "tools"
    __table_args__ = (UniqueConstraint("company_id", "key", name="uq_tools_company_key"),)

    company_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("companies.id"))
    key: Mapped[str] = mapped_column(String(100))
    name: Mapped[str] = mapped_column(String(200))
    description: Mapped[str] = mapped_column(String(2000), default="")
    version: Mapped[int] = mapped_column(default=1)
    input_schema_json: Mapped[dict[str, Any]] = mapped_column(default=dict)
    permission_level: Mapped[int]  # 0 Read, 1 Draft, 2 Execute, 3 External (SECURITY §4)
    policy_json: Mapped[dict[str, Any]] = mapped_column(default=dict)
    status: Mapped[str] = mapped_column(String(20), default="active")


class AgentTool(Base):
    __tablename__ = "agent_tools"

    agent_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("agents.id"), primary_key=True)
    tool_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("tools.id"), primary_key=True)
    configuration_json: Mapped[dict[str, Any]] = mapped_column(default=dict)
    granted_by: Mapped[str] = mapped_column(String(100), default="user")
    granted_at: Mapped[datetime] = mapped_column(default=utcnow)
