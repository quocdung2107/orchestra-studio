"""VieNeu-TTS v3 Turbo via its OpenAI-compatible server (pnnbao97/VieNeu-TTS apps/openai_speech.py).

Verified against the repo on 2026-11-06: POST /v1/audio/speech (response_format pcm|wav,
s16le 48 kHz mono), GET /v1/voices, GET /health. `speed` is accepted but ignored by the server,
so the TTS service applies speed itself. No seed parameter.
"""

from __future__ import annotations

import wave
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

SAMPLING_KEYS = ("temperature", "top_k", "top_p", "repetition_penalty", "max_chars")


class VieneuTts:
    meta = ProviderMeta(
        provider_id="vieneu",
        version="v3-turbo",
        kind="tts",
        label="VieNeu-TTS v3 Turbo (local)",
        capabilities={"voice_clone": True, "speed": False, "langs": ["vi", "en"], "max_chars": 256},
        # CPU ONNX fp32 on Dung's laptop (CUDA 12.7 driver < 12.8 needed by its GPU path).
        hardware=HardwareReq(device="cpu", engine="vieneu", est_ram_mb=2500),
        license=LicenseMeta(
            code="Apache-2.0",
            weights="Apache-2.0 (pnnbao-ump/VieNeu-TTS-v3-Turbo model card)",
            commercial=True,
            output_rights="Không giới hạn theo license; server mặc định chèn watermark",
            source_url="https://github.com/pnnbao97/VieNeu-TTS",
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
            r = c.get("/v1/voices")
            r.raise_for_status()
            return list(r.json().get("data", []))

    def synthesize(self, req: TtsRequest, base_url: str | None, out: Path) -> TtsResult:
        assert base_url
        body: dict[str, Any] = {
            "model": "vieneu-v3-turbo",
            "input": req.text,
            "voice": req.voice,
            "response_format": "pcm",
            "sample_rate": 48000,
        }
        body.update({k: req.params[k] for k in SAMPLING_KEYS if k in req.params})
        try:
            with self._client(base_url) as c:
                r = c.post("/v1/audio/speech", json=body)
        except httpx2.TimeoutException as exc:
            raise JobError("tts_timeout", f"VieNeu không trả kết quả: {exc}") from exc
        except httpx2.HTTPError as exc:
            raise JobError("tts_unreachable", f"Không gọi được VieNeu: {exc}") from exc
        if r.status_code == 429:
            raise JobError("tts_busy", "VieNeu đang bận (429)")
        if r.status_code >= 400:
            msg = r.text[:500]
            raise JobError(
                "tts_rejected",
                f"VieNeu từ chối ({r.status_code}): {msg}",
                retryable=r.status_code >= 500,
            )
        pcm = r.content
        if len(pcm) < 4800:
            raise JobError("tts_empty", "VieNeu trả về audio rỗng")
        with wave.open(str(out), "wb") as w:
            w.setnchannels(1)
            w.setsampwidth(2)
            w.setframerate(48000)
            w.writeframes(pcm[: len(pcm) - len(pcm) % 2])
        warnings = []
        if r.headers.get("x-vieneu-ignored"):
            warnings.append(f"VieNeu bỏ qua: {r.headers['x-vieneu-ignored']}")
        return TtsResult(wav_path=out, engine_version="vieneu-v3-turbo", warnings=warnings)
