from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import ForeignKey, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from orchestra_backend.core.time import utcnow
from orchestra_backend.db.base import Base, IdMixin, TimestampMixin


class VoiceProfile(IdMixin, TimestampMixin, Base):
    """A channel voice. Changes create a new VoiceProfileVersion (ADR-0031)."""

    __tablename__ = "voice_profiles"

    company_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("companies.id"))
    name: Mapped[str] = mapped_column(String(200))
    current_version: Mapped[int] = mapped_column(default=1)
    is_default: Mapped[bool] = mapped_column(default=False)


class VoiceProfileVersion(IdMixin, Base):
    __tablename__ = "voice_profile_versions"
    __table_args__ = (UniqueConstraint("profile_id", "version"),)

    profile_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("voice_profiles.id"))
    version: Mapped[int]
    engine: Mapped[str] = mapped_column(String(50))  # tts provider id
    voice: Mapped[str] = mapped_column(String(200))
    dialect: Mapped[str] = mapped_column(String(10), default="south")
    speed: Mapped[float] = mapped_column(default=1.0)
    max_chars: Mapped[int] = mapped_column(default=180)
    params_json: Mapped[dict[str, Any]] = mapped_column(default=dict)
    lexicon_json: Mapped[dict[str, Any]] = mapped_column(default=dict)
    reference_asset_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("assets.id"), default=None
    )
    consent_note: Mapped[str] = mapped_column(String(1000), default="")
    created_at: Mapped[datetime] = mapped_column(default=utcnow)
