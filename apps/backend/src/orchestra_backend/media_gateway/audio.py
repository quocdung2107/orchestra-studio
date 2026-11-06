"""WAV helpers: convert to the house format (48 kHz mono s16), concat, silence (ADR-0031)."""

from __future__ import annotations

import subprocess
import wave
from pathlib import Path

from orchestra_backend.core.errors import AppError

RATE = 48_000


class FfmpegMissing(AppError):
    status_code = 503
    code = "ffmpeg_missing"


_FFMPEG = ["ffmpeg"]


def configure(ffmpeg: str) -> None:
    _FFMPEG[0] = ffmpeg


def ffmpeg_exe() -> str:
    return _FFMPEG[0]


def run_ffmpeg(args: list[str], *, cwd: Path | None = None, timeout: float = 600) -> str:
    try:
        res = subprocess.run(  # noqa: S603 - argument list, no shell
            [_FFMPEG[0], "-hide_banner", "-nostdin", "-y", *args],
            cwd=cwd,
            capture_output=True,
            timeout=timeout,
            check=False,
        )
    except FileNotFoundError as exc:
        raise FfmpegMissing(
            "Không tìm thấy FFmpeg. Cài: `winget install Gyan.FFmpeg` rồi mở lại app, "
            "hoặc đặt ORCHESTRA_FFMPEG."
        ) from exc
    err = res.stderr.decode("utf-8", "replace")
    if res.returncode != 0:
        raise AppError(f"FFmpeg lỗi (mã {res.returncode}): {err[-1500:]}", code="ffmpeg_failed")
    return err


def is_house_format(path: Path) -> bool:
    try:
        with wave.open(str(path), "rb") as w:
            return w.getframerate() == RATE and w.getnchannels() == 1 and w.getsampwidth() == 2
    except (wave.Error, EOFError, OSError):
        return False


def to_house_wav(src: Path, dst: Path, *, speed: float = 1.0, trim_silence: bool = True) -> Path:
    if speed == 1.0 and not trim_silence and is_house_format(src):
        if src != dst:
            dst.write_bytes(src.read_bytes())
        return dst
    filters: list[str] = []
    if trim_silence:
        # Trim leading/trailing silence so pauses are controlled by the timeline, not the model.
        filters.append(
            "silenceremove=start_periods=1:start_threshold=-50dB:start_silence=0.05,"
            "areverse,silenceremove=start_periods=1:start_threshold=-50dB:start_silence=0.1,"
            "areverse"
        )
    if speed != 1.0:
        filters.append(f"atempo={max(0.5, min(2.0, speed)):.3f}")
    args = ["-i", str(src)]
    if filters:
        args += ["-af", ",".join(filters)]
    args += ["-ar", str(RATE), "-ac", "1", "-c:a", "pcm_s16le", str(dst)]
    run_ffmpeg(args)
    return dst


def duration(path: Path) -> float:
    with wave.open(str(path), "rb") as w:
        return w.getnframes() / float(w.getframerate())


def write_silence(dst: Path, seconds: float) -> Path:
    with wave.open(str(dst), "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(RATE)
        w.writeframes(b"\x00\x00" * int(round(seconds * RATE)))
    return dst


def concat_house(parts: list[tuple[Path | None, float]], dst: Path) -> float:
    """Concatenate house-format WAVs; a `None` path means silence of the given seconds."""
    total = 0
    with wave.open(str(dst), "wb") as out:
        out.setnchannels(1)
        out.setsampwidth(2)
        out.setframerate(RATE)
        for path, seconds in parts:
            if path is None:
                n = int(round(seconds * RATE))
                out.writeframes(b"\x00\x00" * n)
                total += n
                continue
            with wave.open(str(path), "rb") as w:
                if (w.getframerate(), w.getnchannels(), w.getsampwidth()) != (RATE, 1, 2):
                    raise AppError(f"Not house format: {path.name}", code="bad_wav")
                frames = w.readframes(w.getnframes())
                out.writeframes(frames)
                total += w.getnframes()
    return total / RATE
