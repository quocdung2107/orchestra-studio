"""ZeroTTS through Orchestra's sidecar (media_gateway/sidecars/zerotts_server.py).

ZeroTTS (zeroweight-ai, MIT code + weights) ships a Python API only; the sidecar runs in its own
venv and exposes GET /health, GET /voices, POST /synthesize -> audio/wav.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import httpx2

from orchestra_backend.jobs.runner import JobError
from orchestra_backend.media_gateway.meta import (
    HardwareReq,
    LicenseMeta,
    ProviderMeta,
    TtsRequest,
    TtsResult,
)

PARAM_KEYS = (
    "cfg_scale",
    "audio_temperature",
    "audio_topk",
    "audio_topp",
    "audio_repetition_penalty",
    "seed",
)


class ZeroTts:
    meta = ProviderMeta(
        provider_id="zerotts",
        version="0.x",
        kind="tts",
        label="ZeroTTS (local, CPU)",
        capabilities={"voice_clone": False, "speed": False, "langs": ["vi", "en"], "seed": True},
        hardware=HardwareReq(device="cpu", engine="zerotts", est_ram_mb=2000),
        license=LicenseMeta(
            code="MIT",
            weights="MIT (codec decoder Apache-2.0)",
            commercial=True,
            output_rights="Không giới hạn theo license",
            source_url="https://github.com/zeroweight-ai/ZeroTTS",
            checked_at="2026-11-06",
        ),
    )

    def __init__(self, transport: httpx2.BaseTransport | None = None, timeout_s: float = 600):
        self.transport = transport
        self.timeout_s = timeout_s

    def _client(self, base_url: str) -> httpx2.Client:
        kw: dict[str, Any] = {"base_url": base_url, "timeout": self.timeout_s}
        if self.transport is not None:
            kw["transport"] = self.transport
        return httpx2.Client(**kw)

    def voices(self, base_url: str | None) -> list[dict[str, Any]]:
        assert base_url
        with self._client(base_url) as c:
            r = c.get("/voices")
            r.raise_for_status()
            return list(r.json().get("data", []))

    def synthesize(self, req: TtsRequest, base_url: str | None, out: Path) -> TtsResult:
        assert base_url
        body = {
            "text": req.text,
            "voice": req.voice,
            **{k: req.params[k] for k in PARAM_KEYS if k in req.params},
        }
        try:
            with self._client(base_url) as c:
                r = c.post("/synthesize", json=body)
        except httpx2.HTTPError as exc:
            raise JobError("tts_unreachable", f"Không gọi được ZeroTTS sidecar: {exc}") from exc
        if r.status_code >= 400:
            raise JobError(
                "tts_rejected",
                f"ZeroTTS lỗi ({r.status_code}): {r.text[:500]}",
                retryable=r.status_code >= 500,
            )
        out.write_bytes(r.content)
        return TtsResult(wav_path=out, engine_version=r.headers.get("x-engine-version", "zerotts"))
