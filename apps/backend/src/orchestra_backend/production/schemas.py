from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field


class SceneIn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    narration: str = Field(min_length=1, max_length=4000)
    visual_prompt: str = Field(default="", max_length=2000)
    motion: Literal["auto", "kenburns_in", "kenburns_out", "pan_left", "pan_right", "static"] = (
        "auto"
    )


class ScriptIn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    title: str = Field(min_length=1, max_length=300)
    profile: Literal["short", "long"] = "short"
    scenes: list[SceneIn] = Field(min_length=1, max_length=200)
    notes: str = Field(default="", max_length=4000)


class ProjectCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    script: ScriptIn
    voice_profile_id: uuid.UUID | None = None


class ImageSourceIn(BaseModel):
    source: Literal["manual", "cloud"]


class SceneUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    narration: str | None = Field(default=None, min_length=1, max_length=4000)
    visual_prompt: str | None = Field(default=None, max_length=2000)
    motion: (
        Literal["auto", "kenburns_in", "kenburns_out", "pan_left", "pan_right", "static"] | None
    ) = None
    pause_after_s: float | None = Field(default=None, ge=0, le=5)


class SceneImageIn(BaseModel):
    asset_id: uuid.UUID


class ImagesRequest(BaseModel):
    mode: Literal["cloud", "placeholder"]
    scene_ids: list[uuid.UUID] | None = None
    replace: bool = False


class ProduceIn(BaseModel):
    allow_placeholders: bool = False


class MusicIn(BaseModel):
    asset_id: uuid.UUID | None
    gain_db: float = Field(default=-18, ge=-40, le=0)


class VoiceProfileChoice(BaseModel):
    voice_profile_id: uuid.UUID


class SegmentOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    index: int
    text: str
    normalized_text: str
    status: str
    generation: int
    asset_id: uuid.UUID | None
    duration_s: float | None
    error: str | None


class SceneOut(BaseModel):
    id: uuid.UUID
    index: int
    narration: str
    visual_prompt: str
    motion: str
    pause_after_s: float
    image_asset_id: uuid.UUID | None
    image_is_placeholder: bool
    segments: list[SegmentOut]


class RenderOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    version: int
    status: str
    asset_id: uuid.UUID | None
    voice_asset_id: uuid.UUID | None
    subtitle_asset_id: uuid.UUID | None
    qa_json: dict[str, Any] | None
    qa_passed: bool | None
    encoder: str
    ffmpeg_version: str
    render_seconds: float | None
    error: str | None
    created_at: datetime


class JobOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    kind: str
    status: str
    attempts: int
    max_attempts: int
    progress: float
    progress_note: str
    error_code: str | None
    error: str | None
    payload_json: dict[str, Any]
    created_at: datetime
    finished_at: datetime | None


class ProjectSummary(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    company_id: uuid.UUID
    title: str
    profile: str
    status: str
    image_source: str | None
    created_at: datetime
    updated_at: datetime


class ProjectOut(ProjectSummary):
    image_source_confirmed_at: datetime | None
    voice_profile_id: uuid.UUID
    voice_profile_name: str
    music_asset_id: uuid.UUID | None
    music_gain_db: float
    last_error: str | None
    estimated_duration_s: float
    profile_limits: dict[str, float]
    scenes: list[SceneOut]
    latest_render: RenderOut | None
    renders: list[RenderOut]
    jobs: list[JobOut]


class SampleScript(BaseModel):
    id: str
    script: ScriptIn
