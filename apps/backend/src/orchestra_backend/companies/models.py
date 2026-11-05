from __future__ import annotations

from typing import Any

from sqlalchemy import String
from sqlalchemy.orm import Mapped, mapped_column

from orchestra_backend.db.base import Base, IdMixin, TimestampMixin


class Company(IdMixin, TimestampMixin, Base):
    __tablename__ = "companies"

    name: Mapped[str] = mapped_column(String(200))
    description: Mapped[str] = mapped_column(String(2000), default="")
    status: Mapped[str] = mapped_column(String(20), default="active")  # active | archived
    settings_json: Mapped[dict[str, Any]] = mapped_column(default=dict)
    # ADR-0013: highest tool permission level (0-3) any agent in this company may hold.
    max_tool_level: Mapped[int] = mapped_column(default=1)
