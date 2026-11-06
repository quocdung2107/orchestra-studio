"""ffprobe wrapper. Returns None when ffprobe is missing or fails."""

from __future__ import annotations

import json
import shutil
import subprocess
from functools import lru_cache
from pathlib import Path
from typing import Any

_FFPROBE = ["ffprobe"]


def configure(ffprobe: str) -> None:
    _FFPROBE[0] = ffprobe
    available.cache_clear()


@lru_cache(maxsize=1)
def available() -> bool:
    return shutil.which(_FFPROBE[0]) is not None or Path(_FFPROBE[0]).is_file()


def probe_json(path: Path, timeout: float = 60) -> dict[str, Any] | None:
    if not available():
        return None
    try:
        res = subprocess.run(  # noqa: S603 - fixed argument list, no shell
            [
                _FFPROBE[0],
                "-v",
                "error",
                "-print_format",
                "json",
                "-show_format",
                "-show_streams",
                str(path),
            ],
            capture_output=True,
            timeout=timeout,
            check=False,
        )
    except (OSError, subprocess.TimeoutExpired):
        return None
    if res.returncode != 0:
        return None
    try:
        return json.loads(res.stdout.decode("utf-8", "replace"))
    except json.JSONDecodeError:
        return None


def _fps(rate: str | None) -> float | None:
    if not rate or rate == "0/0":
        return None
    num, _, den = rate.partition("/")
    try:
        return float(num) / float(den or 1)
    except (ValueError, ZeroDivisionError):
        return None


def probe_media(path: Path) -> dict[str, Any] | None:
    data = probe_json(path)
    if data is None:
        return None
    fmt = data.get("format", {})
    out: dict[str, Any] = {
        "format": fmt.get("format_name"),
        "duration_s": float(fmt["duration"]) if fmt.get("duration") else None,
        "bit_rate": int(fmt["bit_rate"]) if fmt.get("bit_rate") else None,
        "video": None,
        "audio": None,
        "width": None,
        "height": None,
    }
    for st in data.get("streams", []):
        if st.get("codec_type") == "video" and out["video"] is None:
            out["video"] = {
                "codec": st.get("codec_name"),
                "width": st.get("width"),
                "height": st.get("height"),
                "fps": _fps(st.get("avg_frame_rate") or st.get("r_frame_rate")),
                "pix_fmt": st.get("pix_fmt"),
                "profile": st.get("profile"),
            }
            out["width"], out["height"] = st.get("width"), st.get("height")
        elif st.get("codec_type") == "audio" and out["audio"] is None:
            out["audio"] = {
                "codec": st.get("codec_name"),
                "sample_rate": int(st["sample_rate"]) if st.get("sample_rate") else None,
                "channels": st.get("channels"),
            }
    return out
