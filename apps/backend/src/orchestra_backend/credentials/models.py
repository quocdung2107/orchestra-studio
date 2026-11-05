from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column

from orchestra_backend.db.base import Base, IdMixin, TimestampMixin

PROVIDERS = ("anthropic", "openai")
STORES = ("keyring", "env", "memory")


class Credential(IdMixin, TimestampMixin, Base):
    """A *reference* to a secret. The secret itself never lives in the database (ADR-0021)."""

    __tablename__ = "credentials"

    provider: Mapped[str] = mapped_column(String(30))
    label: Mapped[str] = mapped_column(String(200))
    company_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("companies.id"), default=None)
    store: Mapped[str] = mapped_column(String(20))
    store_ref: Mapped[str] = mapped_column(String(200))
    status: Mapped[str] = mapped_column(String(20), default="active")
    rotated_at: Mapped[datetime | None] = mapped_column(default=None)
    revoked_at: Mapped[datetime | None] = mapped_column(default=None)
    last_verified_at: Mapped[datetime | None] = mapped_column(default=None)
    last_verify_ok: Mapped[bool | None] = mapped_column(default=None)
    last_verify_message: Mapped[str | None] = mapped_column(String(500), default=None)
