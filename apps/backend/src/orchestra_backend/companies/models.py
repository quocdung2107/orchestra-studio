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
