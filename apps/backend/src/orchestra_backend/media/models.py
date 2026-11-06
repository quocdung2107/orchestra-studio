from __future__ import annotations

import uuid
from typing import Any

from sqlalchemy import ForeignKey, Index, String
from sqlalchemy.orm import Mapped, mapped_column

from orchestra_backend.db.base import Base, IdMixin, TimestampMixin

ASSET_KINDS = ("image", "voice", "music", "subtitle", "render", "reference_audio", "other")


class Asset(IdMixin, TimestampMixin, Base):
    """Binary media metadata; bytes live in the content-addressed store (ADR-0028)."""

    __tablename__ = "assets"
    __table_args__ = (
        Index("ix_assets_company_kind_created", "company_id", "kind", "created_at"),
        Index("ix_assets_sha256", "sha256"),
    )

    company_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("companies.id"))
    kind: Mapped[str] = mapped_column(String(30))
    label: Mapped[str] = mapped_column(String(300), default="")
    sha256: Mapped[str] = mapped_column(String(64))
    mime: Mapped[str] = mapped_column(String(100))
    bytes: Mapped[int]
    duration_s: Mapped[float | None] = mapped_column(default=None)
    width: Mapped[int | None] = mapped_column(default=None)
    height: Mapped[int | None] = mapped_column(default=None)
    source: Mapped[str] = mapped_column(String(20))  # upload | provider | render
    provider: Mapped[str | None] = mapped_column(String(100), default=None)
    model: Mapped[str | None] = mapped_column(String(200), default=None)
    params_json: Mapped[dict[str, Any]] = mapped_column(default=dict)
    license_json: Mapped[dict[str, Any]] = mapped_column(default=dict)
    parent_asset_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("assets.id"), default=None)
    retention: Mapped[str] = mapped_column(String(10), default="keep")  # temp | keep
