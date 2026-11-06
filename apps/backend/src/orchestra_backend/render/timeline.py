"""Timeline JSON v1 (ADR-0032). Built deterministically from a project; stored with each render."""

from __future__ import annotations

import uuid
from typing import Literal

from pydantic import BaseModel, Field

Motion = Literal["kenburns_in", "kenburns_out", "pan_left", "pan_right", "static"]
MOTIONS: tuple[Motion, ...] = ("kenburns_in", "pan_right", "kenburns_out", "pan_left")

LEAD_IN_S = 0.3
SEGMENT_GAP_S = 0.25
FADE_S = 0.3


class Canvas(BaseModel):
    w: int
    h: int
    fps: int


class VoicePlacement(BaseModel):
    segment_id: uuid.UUID
    asset_id: uuid.UUID
    start: float
    duration: float


class Cue(BaseModel):
    t0: float
    t1: float
    text: str


class Visual(BaseModel):
    asset_id: uuid.UUID
    motion: Motion
    placeholder: bool = False


class TimelineScene(BaseModel):
    id: uuid.UUID
    index: int
    start: float
    duration: float
    visual: Visual
    fade_s: float = FADE_S
    voice: list[VoicePlacement]
    cues: list[Cue]


class Music(BaseModel):
    asset_id: uuid.UUID
    gain_db: float = -18
    duck: bool = True


class Timeline(BaseModel):
    version: Literal[1] = 1
    profile: str
    preset: str
    canvas: Canvas
    duration: float
    scenes: list[TimelineScene]
    music: Music | None = None
    loudnorm_lufs: float = -14
    subtitle_style: dict[str, int | str] = Field(default_factory=dict)
    burn_subtitles: bool = True


def split_lines(text: str, max_chars: int) -> list[str]:
    words, lines, cur = text.split(), [], ""
    for w in words:
        if cur and len(cur) + 1 + len(w) > max_chars:
            lines.append(cur)
            cur = w
        else:
            cur = f"{cur} {w}".strip()
    if cur:
        lines.append(cur)
    return lines


def cues_for_segment(text: str, start: float, duration: float, max_chars: int) -> list[Cue]:
    """Two-line cues; time inside a segment is split by character count (ADR-0032)."""
    lines = split_lines(text, max_chars)
    chunks = ["\n".join(lines[i : i + 2]) for i in range(0, len(lines), 2)]
    total = sum(len(c) for c in chunks) or 1
    t, out = start, []
    for c in chunks:
        d = duration * len(c) / total
        out.append(Cue(t0=round(t, 3), t1=round(t + d, 3), text=c))
        t += d
    return out
