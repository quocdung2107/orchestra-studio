"""Deterministic QA for a rendered video (ADR-0032)."""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any

from orchestra_backend.media_gateway.audio import run_ffmpeg
from orchestra_backend.render.presets import Profile
from orchestra_backend.render.probe import probe_media
from orchestra_backend.render.timeline import Timeline


def _check(cid: str, ok: bool, detail: str, severity: str = "error") -> dict[str, Any]:
    return {"id": cid, "ok": ok, "detail": detail, "severity": severity}


def volume_stats(path: Path) -> tuple[float | None, float | None]:
    err = run_ffmpeg(["-i", str(path), "-af", "volumedetect", "-vn", "-f", "null", "-"])
    mean = re.search(r"mean_volume:\s*(-?[\d.]+|-inf) dB", err)
    peak = re.search(r"max_volume:\s*(-?[\d.]+|-inf) dB", err)

    def val(m: re.Match[str] | None) -> float | None:
        if not m:
            return None
        return -200.0 if m.group(1) == "-inf" else float(m.group(1))

    return val(mean), val(peak)


def run_qa(
    video: Path,
    tl: Timeline,
    profile: Profile,
    *,
    assets_license: list[dict[str, Any]],
    placeholders: list[str],
) -> dict[str, Any]:
    checks: list[dict[str, Any]] = []
    info = probe_media(video)
    if info is None:
        checks.append(_check("probe", False, "ffprobe không đọc được file"))
        return {"passed": False, "checks": checks, "probe": None}
    v, a = info.get("video") or {}, info.get("audio") or {}
    dur = info.get("duration_s") or 0.0
    checks.append(_check("video_codec", v.get("codec") == "h264", f"codec={v.get('codec')}"))
    checks.append(_check("pix_fmt", v.get("pix_fmt") == "yuv420p", f"pix_fmt={v.get('pix_fmt')}"))
    checks.append(
        _check(
            "resolution",
            (v.get("width"), v.get("height")) == (profile.width, profile.height),
            f"{v.get('width')}x{v.get('height')}, cần {profile.width}x{profile.height}",
        )
    )
    fps = v.get("fps") or 0
    checks.append(_check("fps", 24 <= fps <= 60, f"fps={fps:.2f}"))
    checks.append(_check("audio_codec", a.get("codec") == "aac", f"audio={a.get('codec')}"))
    checks.append(
        _check("audio_rate", a.get("sample_rate") == 48000, f"rate={a.get('sample_rate')}")
    )
    checks.append(
        _check(
            "duration_profile",
            profile.min_s <= dur <= profile.max_s,
            f"{dur:.1f}s, profile {profile.id} cần {profile.min_s:.0f}–{profile.max_s:.0f}s",
        )
    )
    checks.append(
        _check(
            "duration_timeline",
            abs(dur - tl.duration) <= 0.5,
            f"file {dur:.2f}s, timeline {tl.duration:.2f}s",
        )
    )
    mean, peak = volume_stats(video)
    checks.append(_check("not_silent", mean is not None and mean > -40, f"mean_volume={mean} dB"))
    checks.append(_check("no_clipping", peak is not None and peak < -0.1, f"max_volume={peak} dB"))

    long_lines, outside = [], []
    for sc in tl.scenes:
        for c in sc.cues:
            for line in c.text.split("\n"):
                if len(line) > profile.max_chars_per_line:
                    long_lines.append(line)
            if c.t0 < 0 or c.t1 > tl.duration + 0.05 or c.t1 <= c.t0:
                outside.append(f"{c.t0}-{c.t1}")
    checks.append(
        _check(
            "subtitle_line_length",
            not long_lines,
            f"{len(long_lines)} dòng > {profile.max_chars_per_line} ký tự",
        )
    )
    checks.append(_check("subtitle_timing", not outside, f"{len(outside)} cue ngoài thời lượng"))
    bad = [x["asset_id"] for x in assets_license if x.get("commercial") is not True]
    checks.append(_check("asset_license", not bad, f"{len(bad)} asset chưa rõ quyền thương mại"))
    if placeholders:
        checks.append(
            _check(
                "placeholders",
                False,
                f"Có dữ liệu giả lập ({', '.join(sorted(set(placeholders)))}); không dùng để đăng",
                severity="warning",
            )
        )
    passed = all(c["ok"] for c in checks if c["severity"] == "error")
    return {
        "passed": passed,
        "checks": checks,
        "probe": info,
        "loudness": {"mean_db": mean, "peak_db": peak},
    }
