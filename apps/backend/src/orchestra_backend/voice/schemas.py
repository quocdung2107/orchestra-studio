from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field


class VoiceSettings(BaseModel):
    model_config = ConfigDict(extra="forbid")

    engine: Literal["vieneu", "zerotts", "fake_tts"]
    voice: str = Field(min_length=1, max_length=200)
    dialect: Literal["south", "north"] = "south"
    speed: float = Field(default=1.0, ge=0.5, le=2.0)
    max_chars: int = Field(default=180, ge=60, le=400)
    params: dict[str, float | int] = Field(default_factory=dict)
    lexicon: dict[str, str] = Field(default_factory=dict)
    reference_asset_id: uuid.UUID | None = None
    consent_note: str = Field(default="", max_length=1000)


class VoiceProfileCreate(VoiceSettings):
    name: str = Field(min_length=1, max_length=200)
    is_default: bool = False


class VoiceProfileVersionOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    version: int
    engine: str
    voice: str
    dialect: str
    speed: float
    max_chars: int
    params_json: dict[str, Any]
    lexicon_json: dict[str, Any]
    reference_asset_id: uuid.UUID | None
    consent_note: str
    created_at: datetime


class VoiceProfileOut(BaseModel):
    id: uuid.UUID
    company_id: uuid.UUID
    name: str
    is_default: bool
    current_version: int
    current: VoiceProfileVersionOut


class NormalizePreview(BaseModel):
    text: str = Field(min_length=1, max_length=20000)
    dialect: Literal["south", "north"] = "south"
    lexicon: dict[str, str] = Field(default_factory=dict)
    max_chars: int = Field(default=180, ge=60, le=400)


class NormalizePreviewOut(BaseModel):
    normalized: str
    segments: list[str]
