from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import JSON, ForeignKey, Index, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from orchestra_backend.core.time import utcnow
from orchestra_backend.db.base import Base, IdMixin, TimestampMixin

PROJECT_STATUSES = ("draft", "producing", "ready", "qa_failed", "failed")


class VideoProject(IdMixin, TimestampMixin, Base):
    """One video produced from a script (ADR-0033)."""

    __tablename__ = "video_projects"
    __table_args__ = (Index("ix_video_projects_company_created", "company_id", "created_at"),)

    company_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("companies.id"))
    title: Mapped[str] = mapped_column(String(300))
    profile: Mapped[str] = mapped_column(String(20))  # short | long
    status: Mapped[str] = mapped_column(String(20), default="draft")
    image_source: Mapped[str | None] = mapped_column(String(20), default=None)  # manual | cloud
    image_source_confirmed_at: Mapped[datetime | None] = mapped_column(default=None)
    voice_profile_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("voice_profiles.id"))
    music_asset_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("assets.id"), default=None)
    music_gain_db: Mapped[float] = mapped_column(default=-18.0)
    latest_render_id: Mapped[uuid.UUID | None] = mapped_column(default=None)
    script_json: Mapped[dict[str, Any]] = mapped_column(default=dict)
    last_error: Mapped[str | None] = mapped_column(String(2000), default=None)


class VideoScene(IdMixin, TimestampMixin, Base):
    __tablename__ = "video_scenes"
    __table_args__ = (UniqueConstraint("project_id", "index"),)

    project_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("video_projects.id"))
    index: Mapped[int]
    narration: Mapped[str] = mapped_column(String(4000))
    visual_prompt: Mapped[str] = mapped_column(String(2000), default="")
    image_asset_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("assets.id"), default=None)
    motion: Mapped[str] = mapped_column(String(20), default="auto")
    pause_after_s: Mapped[float] = mapped_column(default=0.4)


class VoiceSegment(IdMixin, Base):
    """One TTS unit: also the subtitle and regeneration unit (ADR-0031)."""

    __tablename__ = "voice_segments"
    __table_args__ = (Index("ix_voice_segments_scene_index", "scene_id", "index"),)

    project_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("video_projects.id"))
    scene_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("video_scenes.id"))
    index: Mapped[int]
    text: Mapped[str] = mapped_column(String(2000))
    normalized_text: Mapped[str] = mapped_column(String(4000))
    profile_version_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("voice_profile_versions.id"))
    generation: Mapped[int] = mapped_column(default=1)
    status: Mapped[str] = mapped_column(String(20), default="pending")  # pending|ready|failed
    asset_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("assets.id"), default=None)
    duration_s: Mapped[float | None] = mapped_column(default=None)
    error: Mapped[str | None] = mapped_column(String(1000), default=None)
    created_at: Mapped[datetime] = mapped_column(default=utcnow)


class VideoRender(IdMixin, TimestampMixin, Base):
    __tablename__ = "video_renders"
    __table_args__ = (UniqueConstraint("project_id", "version"),)

    project_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("video_projects.id"))
    version: Mapped[int]
    # Hash of every input (segment audio, images, music, settings): same key = same video.
    content_key: Mapped[str] = mapped_column(String(64), default="")
    status: Mapped[str] = mapped_column(
        String(20), default="queued"
    )  # queued|running|succeeded|failed
    timeline_json: Mapped[dict[str, Any]] = mapped_column(default=dict)
    asset_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("assets.id"), default=None)
    voice_asset_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("assets.id"), default=None)
    subtitle_asset_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("assets.id"), default=None
    )
    qa_json: Mapped[dict[str, Any] | None] = mapped_column(default=None)
    qa_passed: Mapped[bool | None] = mapped_column(default=None)
    encoder: Mapped[str] = mapped_column(String(20), default="libx264")
    ffmpeg_args_json: Mapped[list[Any]] = mapped_column(JSON, default=list)
    ffmpeg_version: Mapped[str] = mapped_column(String(200), default="")
    render_seconds: Mapped[float | None] = mapped_column(default=None)
    log_tail: Mapped[str] = mapped_column(String(4000), default="")
    error: Mapped[str | None] = mapped_column(String(2000), default=None)
