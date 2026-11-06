from __future__ import annotations

import base64
import json
import wave

import httpx2
import pytest

from orchestra_backend.jobs.runner import JobError
from orchestra_backend.media_gateway import registry
from orchestra_backend.media_gateway.meta import ImageRequest, TtsRequest
from orchestra_backend.media_gateway.providers.fakes import write_png
from orchestra_backend.media_gateway.providers.openai_images import OpenAiImages
from orchestra_backend.media_gateway.providers.vieneu import VieneuTts
from orchestra_backend.media_gateway.providers.zerotts import ZeroTts


def test_vieneu_requests_pcm_and_writes_48k_wav(tmp_path):
    seen = {}

    def handle(req: httpx2.Request) -> httpx2.Response:
        seen["path"] = req.url.path
        seen["body"] = json.loads(req.content)
        return httpx2.Response(
            200, content=b"\x01\x00" * 48000, headers={"x-vieneu-ignored": "speed"}
        )

    p = VieneuTts(transport=httpx2.MockTransport(handle))
    res = p.synthesize(
        TtsRequest(text="Xin chào", voice="Thùy Dung", params={"temperature": 0.7}),
        "http://127.0.0.1:8000",
        tmp_path / "o.wav",
    )
    assert seen["path"] == "/v1/audio/speech"
    assert seen["body"]["response_format"] == "pcm" and seen["body"]["voice"] == "Thùy Dung"
    assert seen["body"]["temperature"] == 0.7
    with wave.open(str(res.wav_path)) as w:
        assert w.getframerate() == 48000 and w.getnframes() == 48000
    assert res.warnings


@pytest.mark.parametrize(
    ("code", "err", "retry"),
    [(429, "tts_busy", True), (400, "tts_rejected", False), (503, "tts_rejected", True)],
)
def test_vieneu_errors(tmp_path, code, err, retry):
    p = VieneuTts(transport=httpx2.MockTransport(lambda r: httpx2.Response(code, text="no")))
    with pytest.raises(JobError) as e:
        p.synthesize(TtsRequest(text="x", voice="v"), "http://127.0.0.1:8000", tmp_path / "o.wav")
    assert e.value.code == err and e.value.retryable is retry


def test_zerotts_sidecar_contract(tmp_path):
    def handle(req):
        if req.url.path == "/voices":
            return httpx2.Response(200, json={"data": [{"id": "maichi", "gender": "nữ"}]})
        body = json.loads(req.content)
        assert body == {"text": "Chào", "voice": "maichi", "cfg_scale": 1.5}
        return httpx2.Response(
            200, content=b"RIFFxxxxWAVE", headers={"x-engine-version": "zerotts@0.3"}
        )

    p = ZeroTts(transport=httpx2.MockTransport(handle))
    assert p.voices("http://127.0.0.1:8011")[0]["id"] == "maichi"
    r = p.synthesize(
        TtsRequest(text="Chào", voice="maichi", params={"cfg_scale": 1.5, "speed": 2}),
        "http://127.0.0.1:8011",
        tmp_path / "z.wav",
    )
    assert r.engine_version == "zerotts@0.3"


def test_cloud_images_b64_and_url(tmp_path):
    png = tmp_path / "p.png"
    write_png(png, 8, 8, (1, 2, 3), (4, 5, 6))
    raw = png.read_bytes()

    def handle(req):
        if req.url.path.endswith("/images/generations"):
            body = json.loads(req.content)
            assert req.headers["authorization"] == "Bearer k-123"
            if body["prompt"] == "b64":
                return httpx2.Response(
                    200, json={"data": [{"b64_json": base64.b64encode(raw).decode()}]}
                )
            return httpx2.Response(200, json={"data": [{"url": "https://cdn.test/x.png"}]})
        return httpx2.Response(200, content=raw)

    p = OpenAiImages(
        base_url="https://img.test/v1",
        model="m1",
        api_key="k-123",
        commercial_confirmed=True,
        transport=httpx2.MockTransport(handle),
    )
    for prompt in ("b64", "url"):
        out = tmp_path / f"{prompt}.bin"
        p.generate(ImageRequest(prompt=prompt, width=10, height=10), out)
        assert out.read_bytes() == raw


def test_license_policy_blocks_unconfirmed_cloud_and_non_commercial():
    cfg = registry.CloudImageSettings(base_url="https://img.test/v1", model="m1")
    with pytest.raises(registry.LicenseBlocked):
        registry.cloud_image_provider(cfg, "k")
    cfg.commercial_use_confirmed = True
    assert registry.cloud_image_provider(cfg, "k").meta.license.commercial is True
    meta = registry.TTS_PROVIDERS["vieneu"].meta.model_copy(deep=True)
    meta.license.commercial = False
    with pytest.raises(registry.LicenseBlocked):
        registry.check_license(meta)


def test_cloud_base_url_must_be_https():
    with pytest.raises(ValueError):
        registry.CloudImageSettings(base_url="http://evil.example/v1", model="m")


def test_providers_endpoint_lists_license(client):
    r = client.get("/api/v1/media/providers")
    ids = {p["provider_id"]: p for p in r.json()}
    assert ids["vieneu"]["license"]["code"] == "Apache-2.0" and ids["vieneu"]["allowed"]
    assert ids["zerotts"]["license"]["code"] == "MIT"
