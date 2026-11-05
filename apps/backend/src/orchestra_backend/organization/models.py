from __future__ import annotations

import uuid

from sqlalchemy import ForeignKey, Index, String
from sqlalchemy.orm import Mapped, mapped_column

from orchestra_backend.db.base import Base, IdMixin, TimestampMixin


class Department(IdMixin, TimestampMixin, Base):
    __tablename__ = "departments"
    __table_args__ = (Index("ix_departments_company_parent", "company_id", "parent_department_id"),)

    company_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("companies.id"))
    parent_department_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("departments.id"), default=None
    )
    name: Mapped[str] = mapped_column(String(200))
    description: Mapped[str] = mapped_column(String(2000), default="")
    status: Mapped[str] = mapped_column(String(20), default="active")  # active | archived
    # ADR-0013: None = inherit the parent's / company's ceiling.
    max_tool_level: Mapped[int | None] = mapped_column(default=None)


class OrgLayout(Base):
    """UI-only node positions for the Org Builder (ADR-0011). Not business state; no events."""

    __tablename__ = "org_layouts"

    company_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("companies.id"), primary_key=True)
    node_key: Mapped[str] = mapped_column(String(80), primary_key=True)
    x: Mapped[float]
    y: Mapped[float]
