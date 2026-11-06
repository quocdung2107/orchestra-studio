"""Production profiles and export presets as data (ADR-0032)."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Profile:
    id: str
    preset: str
    width: int
    height: int
    fps: int
    min_s: float
    max_s: float
    max_chars_per_line: int
    font_size: int
    margin_v: int
    max_scene_s: float


PROFILES: dict[str, Profile] = {
    "short": Profile("short", "fb_reel_1080x1920_h264", 1080, 1920, 30, 30, 90, 24, 78, 420, 6),
    "long": Profile("long", "fb_video_1920x1080_h264", 1920, 1080, 30, 180, 600, 42, 56, 70, 15),
}
