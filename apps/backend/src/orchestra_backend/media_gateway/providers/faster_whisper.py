"""faster-whisper (SYSTRAN, MIT) via Orchestra's sidecar, used for subtitle/voice QA."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import httpx2

from orchestra_backend.jobs.runner import JobError
from orchestra_backend.media_gateway.meta import HardwareReq, LicenseMeta, ProviderMeta, Transcript


class FasterWhisperAsr:
    meta = ProviderMeta(
        provider_id="faster_whisper",
        version="small-int8",
        kind="asr",
        label="faster-whisper small int8 (CPU)",
        hardware=HardwareReq(device="cpu", engine="faster_whisper", est_ram_mb=1500),
        license=LicenseMeta(
            code="MIT",
            weights="MIT (Whisper weights, OpenAI)",
            commercial=True,
            source_url="https://github.com/SYSTRAN/faster-whisper",
            checked_at="2026-11-06",
        ),
    )

    def __init__(self, transport: httpx2.BaseTransport | None = None, timeout_s: float = 1800):
        self.transport = transport
        self.timeout_s = timeout_s

    def transcribe(
        self, wav: Path, base_url: str | None, language: str = "vi", hint: str | None = None
    ) -> Transcript:
        assert base_url
        kw: dict[str, Any] = {"base_url": base_url, "timeout": self.timeout_s}
        if self.transport is not None:
            kw["transport"] = self.transport
        try:
            with httpx2.Client(**kw) as c:
                r = c.post(
                    f"/transcribe?language={language}",
                    content=wav.read_bytes(),
                    headers={"content-type": "audio/wav"},
                )
        except httpx2.HTTPError as exc:
            raise JobError("asr_unreachable", f"Không gọi được faster-whisper: {exc}") from exc
        if r.status_code >= 400:
            raise JobError("asr_failed", f"ASR lỗi ({r.status_code}): {r.text[:300]}")
        d = r.json()
        return Transcript(
            text=d.get("text", ""), words=d.get("words", []), language=d.get("language")
        )
