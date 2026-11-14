"""Target video length: validation and fitting a script to it.

The length of a video is driven by its narration, so a target is met by choosing how much of
the script to keep: whole scenes first, then whole sentences of the last scene. Estimates use a
rough Vietnamese reading speed; the render step enforces the target again with real TTS lengths.
"""

from __future__ import annotations

import re

from orchestra_backend.core.errors import DomainValidationError
from orchestra_backend.render.presets import PROFILES

MIN_TARGET_S = 5.0
# Machine settings, set once at startup from Settings (configure()).
DEFAULT_S = 15.0
MAX_S = 120.0
# Vietnamese narration speed, estimates only. Measured 2026-11-15 with VieNeu "Thùy Dung":
# ~19 chars/s after silence trim; 18 keeps a small margin.
CHARS_PER_SECOND = 18.0
SCENE_OVERHEAD_S = 0.6  # lead-in/gaps/pause per scene, estimate only

_SENTENCE = re.compile(r"(?<=[.!?…])\s+")


def configure(default_s: float, max_s: float) -> None:
    global DEFAULT_S, MAX_S
    MAX_S = float(max_s)
    DEFAULT_S = float(min(default_s, max_s))


def tolerance(target_s: float) -> float:
    """How far over the target a finished video may run."""
    return max(2.0, 0.15 * target_s)


def limits(profile: str) -> tuple[float, float]:
    """(min, max) target allowed for a profile, capped by the machine setting."""
    return MIN_TARGET_S, min(PROFILES[profile].max_s, MAX_S)


def validate_target(target_s: float, profile: str) -> float:
    lo, hi = limits(profile)
    if not lo <= target_s <= hi:
        raise DomainValidationError(
            f"Độ dài video phải trong khoảng {lo:.0f}–{hi:.0f} giây (đang là {target_s:g})",
            code="video_duration_out_of_range",
            details={"min_s": lo, "max_s": hi},
        )
    return float(target_s)


def estimate_s(text: str) -> float:
    return len(text) / CHARS_PER_SECOND + SCENE_OVERHEAD_S


def fit_narrations(narrations: list[str], target_s: float) -> tuple[list[str], int]:
    """Keep scenes (and sentences of the last kept scene) that fit in target_s.

    A piece that runs past the target is still kept when it lands closer to the target than
    stopping would, within the tolerance (the render re-checks with real voice lengths).
    Returns (kept narrations, number of scenes dropped). Always keeps at least one sentence.
    """
    hard = target_s + tolerance(target_s)

    def worth(used: float, need: float) -> bool:
        after = used + need
        return after <= hard and abs(target_s - after) < abs(target_s - used)

    used = 0.0
    kept: list[str] = []
    for i, text in enumerate(narrations):
        est = estimate_s(text)
        if used + est <= target_s or worth(used, est):
            kept.append(text)
            used += est
            continue
        sentences = [x for x in _SENTENCE.split(text.strip()) if x]
        part: list[str] = []
        cur = used + SCENE_OVERHEAD_S
        for sen in sentences:
            need = len(sen) / CHARS_PER_SECOND
            if (part or kept) and not (cur + need <= target_s or worth(cur, need)):
                break
            part.append(sen)
            cur += need
        if part:
            kept.append(" ".join(part))
        return kept, len(narrations) - i - (1 if part else 0)
    return kept, 0
