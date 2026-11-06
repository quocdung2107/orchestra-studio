"""Fake providers that create real files, for tests and offline runs (ADR-0030)."""

from __future__ import annotations

import array
import hashlib
import math
import struct
import wave
import zlib
from pathlib import Path
from typing import Any

from orchestra_backend.media_gateway.audio import RATE
from orchestra_backend.media_gateway.meta import (
    HardwareReq,
    ImageRequest,
    ImageResult,
    LicenseMeta,
    ProviderMeta,
    Transcript,
    TtsRequest,
    TtsResult,
)

_FAKE_LICENSE = LicenseMeta(
    code="internal",
    weights="none",
    commercial=True,
    output_rights="test only",
    checked_at="2026-11-06",
)
CHARS_PER_SECOND = 15.0


class FakeTts:
    meta = ProviderMeta(
        provider_id="fake_tts",
        version="1",
        kind="tts",
        label="Giọng giả (âm tone, để thử pipeline)",
        capabilities={"voice_clone": False, "speed": False, "langs": ["vi"]},
        hardware=HardwareReq(device="none"),
        license=_FAKE_LICENSE,
        fake=True,
    )

    def voices(self, base_url: str | None) -> list[dict[str, Any]]:
        return [{"id": "fake_nu_nam", "name": "Giả lập nữ miền Nam", "gender": "nữ"}]

    def synthesize(self, req: TtsRequest, base_url: str | None, out: Path) -> TtsResult:
        seconds = max(0.6, len(req.text) / CHARS_PER_SECOND)
        h = int(hashlib.sha256(req.voice.encode()).hexdigest()[:4], 16)
        freq = 180 + h % 120
        n = int(seconds * RATE)
        samples = array.array(
            "h",
            (
                int(
                    6000
                    * math.sin(2 * math.pi * freq * i / RATE)
                    * (0.6 + 0.4 * math.sin(i / 2400))
                )
                for i in range(n)
            ),
        )
        with wave.open(str(out), "wb") as w:
            w.setnchannels(1)
            w.setsampwidth(2)
            w.setframerate(RATE)
            w.writeframes(samples.tobytes())
        return TtsResult(wav_path=out, engine_version="fake_tts@1")


def write_png(
    path: Path, width: int, height: int, top: tuple[int, int, int], bottom: tuple[int, int, int]
) -> Path:
    """Vertical-gradient PNG written with zlib only."""
    rows = []
    for y in range(height):
        t = y / max(1, height - 1)
        px = bytes(int(a + (b - a) * t) for a, b in zip(top, bottom, strict=True))
        rows.append(b"\x00" + px * width)
    raw = zlib.compress(b"".join(rows), 6)

    def chunk(tag: bytes, data: bytes) -> bytes:
        return (
            struct.pack(">I", len(data))
            + tag
            + data
            + struct.pack(">I", zlib.crc32(tag + data) & 0xFFFFFFFF)
        )

    ihdr = struct.pack(">IIBBBBB", width, height, 8, 2, 0, 0, 0)
    path.write_bytes(
        b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", ihdr) + chunk(b"IDAT", raw) + chunk(b"IEND", b"")
    )
    return path


class FakeImage:
    meta = ProviderMeta(
        provider_id="fake_image",
        version="1",
        kind="image",
        label="Ảnh giữ chỗ (gradient)",
        capabilities={"max_batch": 1, "supports_seed": True},
        hardware=HardwareReq(device="none"),
        license=_FAKE_LICENSE,
        fake=True,
    )

    def generate(self, req: ImageRequest, out: Path) -> ImageResult:
        d = hashlib.sha256(f"{req.prompt}|{req.seed}".encode()).digest()
        top = (d[0] // 2 + 40, d[1] // 2 + 40, d[2] // 2 + 60)
        bottom = (d[3] // 3, d[4] // 3, d[5] // 3 + 30)
        write_png(out, req.width, req.height, top, bottom)
        return ImageResult(path=out, model="fake_image@1", cost_usd=0.0)


class FakeAsr:
    meta = ProviderMeta(
        provider_id="fake_asr",
        version="1",
        kind="asr",
        label="ASR giả (trả lại văn bản gợi ý)",
        hardware=HardwareReq(device="none"),
        license=_FAKE_LICENSE,
        fake=True,
    )

    def transcribe(
        self, wav: Path, base_url: str | None, language: str = "vi", hint: str | None = None
    ) -> Transcript:
        return Transcript(text=hint or "", language=language)
