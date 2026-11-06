"""Timeline -> deterministic FFmpeg argument list -> MP4 (ADR-0032)."""

from __future__ import annotations

import subprocess
import time
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path

from orchestra_backend.core.errors import AppError
from orchestra_backend.media_gateway.audio import FfmpegMissing, ffmpeg_exe
from orchestra_backend.render.timeline import Timeline, TimelineScene

ZOOM = 0.12


def _motion(sc: TimelineScene, frames: int) -> tuple[str, str, str]:
    n = max(1, frames - 1)
    center_x, center_y = "iw/2-(iw/zoom/2)", "ih/2-(ih/zoom/2)"
    m = sc.visual.motion
    if m == "kenburns_in":
        return f"1+{ZOOM}*on/{n}", center_x, center_y
    if m == "kenburns_out":
        return f"{1 + ZOOM}-{ZOOM}*on/{n}", center_x, center_y
    if m == "pan_left":
        return f"{1 + ZOOM / 2}", f"(iw-iw/zoom)*(1-on/{n})", center_y
    if m == "pan_right":
        return f"{1 + ZOOM / 2}", f"(iw-iw/zoom)*on/{n}", center_y
    return "1", center_x, center_y


@dataclass
class RenderInputs:
    images: dict[str, Path]  # asset_id -> file
    voice_wav: Path
    music: Path | None
    subtitles_ass: str | None  # file name relative to the work dir


def build_args(tl: Timeline, inp: RenderInputs, out_name: str, encoder: str) -> list[str]:
    w, h, fps = tl.canvas.w, tl.canvas.h, tl.canvas.fps
    args: list[str] = []
    for sc in tl.scenes:
        args += ["-i", str(inp.images[str(sc.visual.asset_id)])]
    voice_idx = len(tl.scenes)
    args += ["-i", str(inp.voice_wav)]
    music_idx = None
    if tl.music and inp.music:
        music_idx = voice_idx + 1
        args += ["-stream_loop", "-1", "-i", str(inp.music)]

    parts: list[str] = []
    labels: list[str] = []
    for i, sc in enumerate(tl.scenes):
        frames = max(1, round(sc.duration * fps))
        z, x, y = _motion(sc, frames)
        fade = min(sc.fade_s, sc.duration / 3)
        out_t = max(0.0, frames / fps - fade)
        parts.append(
            f"[{i}:v]scale={2 * w}:{2 * h}:force_original_aspect_ratio=increase,"
            f"crop={2 * w}:{2 * h},setsar=1,"
            f"zoompan=z='{z}':x='{x}':y='{y}':d={frames}:s={w}x{h}:fps={fps},"
            f"trim=end_frame={frames},setpts=PTS-STARTPTS,"
            f"fade=t=in:st=0:d={fade:.3f},fade=t=out:st={out_t:.3f}:d={fade:.3f},"
            f"format=yuv420p[v{i}]"
        )
        labels.append(f"[v{i}]")
    parts.append(f"{''.join(labels)}concat=n={len(labels)}:v=1:a=0[vcat]")
    if tl.burn_subtitles and inp.subtitles_ass:
        parts.append(f"[vcat]subtitles={inp.subtitles_ass}[vout]")
    else:
        parts.append("[vcat]null[vout]")

    parts.append(
        f"[{voice_idx}:a]aresample=48000,aformat=sample_fmts=fltp:channel_layouts=stereo[voice]"
    )
    lufs = tl.loudnorm_lufs
    if music_idx is not None and tl.music:
        parts.append("[voice]asplit=2[vo][sc]")
        parts.append(
            f"[{music_idx}:a]aresample=48000,aformat=sample_fmts=fltp:channel_layouts=stereo,"
            f"volume={tl.music.gain_db}dB[mu]"
        )
        if tl.music.duck:
            parts.append(
                "[mu][sc]sidechaincompress=threshold=0.03:ratio=8:attack=20:release=300[duck]"
            )
        else:
            parts.append("[mu]anull[duck];[sc]anullsink")
        parts.append("[vo][duck]amix=inputs=2:duration=first:normalize=0[mix]")
        parts.append(f"[mix]loudnorm=I={lufs}:TP=-1.5:LRA=11,aresample=48000[aout]")
    else:
        parts.append(f"[voice]loudnorm=I={lufs}:TP=-1.5:LRA=11,aresample=48000[aout]")

    if encoder == "h264_nvenc":
        venc = ["-c:v", "h264_nvenc", "-preset", "p5", "-cq", "21", "-b:v", "0"]
    else:
        venc = ["-c:v", "libx264", "-preset", "veryfast", "-crf", "20"]
    args += [
        "-filter_complex",
        ";".join(parts),
        "-map",
        "[vout]",
        "-map",
        "[aout]",
        *venc,
        "-profile:v",
        "high",
        "-pix_fmt",
        "yuv420p",
        "-r",
        str(fps),
        "-c:a",
        "aac",
        "-b:a",
        "192k",
        "-ar",
        "48000",
        "-ac",
        "2",
        "-t",
        f"{tl.duration:.3f}",
        "-movflags",
        "+faststart",
        "-progress",
        "pipe:1",
        "-nostats",
        out_name,
    ]
    return args


def ffmpeg_version() -> str:
    try:
        res = subprocess.run(  # noqa: S603 - fixed args
            [ffmpeg_exe(), "-version"], capture_output=True, timeout=10, check=False
        )
        return res.stdout.decode("utf-8", "replace").splitlines()[0][:200]
    except (OSError, IndexError, subprocess.TimeoutExpired):
        return ""


def run_render(
    args: list[str],
    *,
    cwd: Path,
    total_s: float,
    timeout_s: float,
    progress: Callable[[float], None] | None = None,
    cancelled: Callable[[], bool] | None = None,
) -> tuple[float, str]:
    """Run FFmpeg with -progress; return (seconds taken, stderr tail)."""
    log_path = cwd / "ffmpeg.log"
    started = time.monotonic()
    try:
        with log_path.open("wb") as log:
            proc = subprocess.Popen(  # noqa: S603 - argument list, no shell
                [ffmpeg_exe(), "-hide_banner", "-nostdin", "-y", *args],
                cwd=cwd,
                stdout=subprocess.PIPE,
                stderr=log,
                stdin=subprocess.DEVNULL,
            )
            assert proc.stdout is not None
            for raw in proc.stdout:
                line = raw.decode("utf-8", "replace").strip()
                if line.startswith("out_time_us=") and progress and total_s > 0:
                    try:
                        progress(min(0.99, int(line.split("=", 1)[1]) / 1e6 / total_s))
                    except ValueError:
                        pass
                if cancelled and cancelled():
                    proc.kill()
                    break
                if time.monotonic() - started > timeout_s:
                    proc.kill()
                    raise AppError("Render quá thời gian cho phép", code="render_timeout")
            code = proc.wait()
    except FileNotFoundError as exc:
        raise FfmpegMissing("Không tìm thấy FFmpeg (winget install Gyan.FFmpeg)") from exc
    tail = log_path.read_text(encoding="utf-8", errors="replace")[-3500:]
    if code != 0:
        raise AppError(f"FFmpeg lỗi (mã {code}): {tail[-1200:]}", code="ffmpeg_failed")
    return time.monotonic() - started, tail
