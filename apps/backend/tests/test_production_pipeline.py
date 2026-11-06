"""End-to-end: sample script -> TTS segments -> render -> QA, offline with fake providers (L12)."""

from __future__ import annotations

import base64
import json
import shutil
from pathlib import Path

import httpx2
import pytest

from orchestra_backend.media_gateway.providers.fakes import write_png
from orchestra_backend.render.probe import probe_media
from tests.media_helpers import drain, png_bytes

pytestmark = pytest.mark.skipif(shutil.which("ffmpeg") is None, reason="needs ffmpeg")

REPO = Path(__file__).resolve().parents[3]


def _fake_voice(client, company_id):
    r = client.post(
        f"/api/v1/companies/{company_id}/voice-profiles",
        json={
            "name": "Giả lập nữ Nam",
            "engine": "fake_tts",
            "voice": "fake_nu_nam",
            "is_default": True,
        },
    )
    assert r.status_code == 201, r.text
    return r.json()


def _sample(client, name="short_bau_troi"):
    r = client.get("/api/v1/video-samples")
    return next(x["script"] for x in r.json() if x["id"] == name)


def _project(client, company_id, script):
    r = client.post(f"/api/v1/companies/{company_id}/video-projects", json={"script": script})
    assert r.status_code == 201, r.text
    return r.json()


def test_default_voice_is_southern_female_vieneu(client, company):
    r = client.get(f"/api/v1/companies/{company['id']}/voice-profiles")
    cur = r.json()[0]["current"]
    assert (cur["engine"], cur["voice"], cur["dialect"]) == ("vieneu", "Thùy Dung", "south")


def test_produce_requires_image_source_then_images(client, company):
    _fake_voice(client, company["id"])
    p = _project(client, company["id"], _sample(client))
    r = client.post(f"/api/v1/video-projects/{p['id']}/produce", json={})
    assert r.json()["error"]["code"] == "image_source_not_confirmed"
    client.post(f"/api/v1/video-projects/{p['id']}/image-source", json={"source": "manual"})
    r = client.post(f"/api/v1/video-projects/{p['id']}/produce", json={})
    assert r.json()["error"]["code"] == "scene_images_missing"
    r = client.post(f"/api/v1/video-projects/{p['id']}/images", json={"mode": "cloud"})
    assert r.json()["error"]["code"] == "image_source_not_cloud"


def test_short_video_end_to_end_and_regenerate_one_segment(client, company, container, tmp_path):
    cid = company["id"]
    _fake_voice(client, cid)
    p = _project(client, cid, _sample(client))
    assert p["scenes"][2]["segments"][0]["normalized_text"].startswith(
        "Khi đi qua bầu khí quyển dày khoảng một trăm ki lô mét"
    )
    client.post(f"/api/v1/video-projects/{p['id']}/image-source", json={"source": "manual"})
    # Scene 1 gets a real upload; the rest use placeholders.
    up = client.put(
        f"/api/v1/companies/{cid}/assets?kind=image", content=png_bytes(tmp_path, 640, 480)
    ).json()
    client.put(f"/api/v1/video-scenes/{p['scenes'][0]['id']}/image", json={"asset_id": up["id"]})
    r = client.post(f"/api/v1/video-projects/{p['id']}/produce", json={"allow_placeholders": True})
    assert r.status_code == 200, r.text
    drain(container, 300)

    out = client.get(f"/api/v1/video-projects/{p['id']}").json()
    assert out["status"] == "ready", (out["last_error"], out["latest_render"])
    render = out["latest_render"]
    checks = {c["id"]: c for c in render["qa_json"]["checks"]}
    assert all(c["ok"] for c in checks.values() if c["severity"] == "error"), checks
    assert checks["placeholders"]["ok"] is False  # warning: not for publishing
    assert render["qa_json"]["asr"]["status"] == "skipped"
    mp4 = client.get(f"/api/v1/assets/{render['asset_id']}/content")
    f = tmp_path / "out.mp4"
    f.write_bytes(mp4.content)
    info = probe_media(f)
    assert (info["width"], info["height"]) == (1080, 1920)
    assert info["audio"]["codec"] == "aac" and 30 <= info["duration_s"] <= 90
    assert "-->" in render["qa_json"]["srt"]

    # Regenerate one segment: only its asset changes, then a new render version.
    segs = [s for sc in out["scenes"] for s in sc["segments"]]
    target = segs[3]
    before = {s["id"]: s["asset_id"] for s in segs}
    client.post(f"/api/v1/voice-segments/{target['id']}/regenerate")
    drain(container, 300)
    out2 = client.get(f"/api/v1/video-projects/{p['id']}").json()
    after = {s["id"]: s["asset_id"] for sc in out2["scenes"] for s in sc["segments"]}
    changed = [k for k in before if before[k] != after[k]]
    assert changed == [target["id"]] or (
        changed == [] and after[target["id"]] == before[target["id"]]
    )
    assert out2["status"] == "ready" and out2["latest_render"]["version"] == 2
    gens = {s["id"]: s["generation"] for sc in out2["scenes"] for s in sc["segments"]}
    assert gens[target["id"]] == 2 and all(g == 1 for k, g in gens.items() if k != target["id"])


def test_pipeline_resumes_after_restart(client, company, container):
    cid = company["id"]
    _fake_voice(client, cid)
    script = {
        "title": "Ngắn",
        "profile": "short",
        "scenes": [
            {
                "narration": "Đây là câu thử số một, đủ dài để có giọng đọc rõ ràng. "
                * 4
            },
            {"narration": "Câu thử số hai cũng dài vừa phải để video vượt qua ba mươi giây. " * 4},
        ],
    }
    p = _project(client, cid, script)
    client.post(f"/api/v1/video-projects/{p['id']}/image-source", json={"source": "manual"})
    client.post(f"/api/v1/video-projects/{p['id']}/produce", json={"allow_placeholders": True})
    runner = container.extras["job_runner"]
    from orchestra_backend.jobs.models import Job

    with container.tx() as s:  # pretend the app died while TTS jobs were running
        for j in s.query(Job).filter(Job.subject_id == __import__("uuid").UUID(p["id"])):
            if j.kind == "tts.segment":
                j.status, j.attempts = "running", 1
    assert runner.recover() >= 1
    drain(container, 300)
    out = client.get(f"/api/v1/video-projects/{p['id']}").json()
    assert out["status"] == "ready", out["last_error"]


def test_cloud_images_and_asr_qa(client, company, container, tmp_path):
    cid = company["id"]
    _fake_voice(client, cid)
    png = tmp_path / "c.png"
    write_png(png, 512, 512, (10, 120, 200), (200, 120, 10))
    calls = []

    def handle(req):
        calls.append(json.loads(req.content)["prompt"])
        return httpx2.Response(
            200, json={"data": [{"b64_json": base64.b64encode(png.read_bytes()).decode()}]}
        )

    container.extras["image_transport"] = httpx2.MockTransport(handle)
    settings = client.get(f"/api/v1/companies/{cid}/media-settings").json()
    settings["cloud_image"] = {
        "base_url": "https://img.test/v1",
        "model": "free-model",
        "commercial_use_confirmed": True,
    }
    settings["asr_provider"] = "fake_asr"
    assert client.put(f"/api/v1/companies/{cid}/media-settings", json=settings).status_code == 200

    p = _project(client, cid, _sample(client))
    client.post(f"/api/v1/video-projects/{p['id']}/image-source", json={"source": "cloud"})
    jobs = client.post(f"/api/v1/video-projects/{p['id']}/images", json={"mode": "cloud"}).json()
    assert len(jobs) == len(p["scenes"])
    drain(container, 60)
    assert len(calls) == len(p["scenes"]) and calls[0].startswith("Bầu trời xanh")
    out = client.get(f"/api/v1/video-projects/{p['id']}").json()
    assert all(sc["image_asset_id"] for sc in out["scenes"])
    client.post(f"/api/v1/video-projects/{p['id']}/produce", json={})
    drain(container, 300)
    out = client.get(f"/api/v1/video-projects/{p['id']}").json()
    assert out["status"] == "ready", out["last_error"]
    asr = out["latest_render"]["qa_json"]["asr"]
    assert asr["status"] == "done" and asr["wer"] == 0
    assert any(c["id"] == "asr_wer" for c in out["latest_render"]["qa_json"]["checks"])


def test_tts_engine_down_fails_with_clear_message_and_retry(client, company, container):
    cid = company["id"]  # default profile = VieNeu, which is not running in tests
    script = {"title": "x", "profile": "short", "scenes": [{"narration": "Xin chào các bạn."}]}
    p = _project(client, cid, script)
    client.post(f"/api/v1/video-projects/{p['id']}/image-source", json={"source": "manual"})
    client.post(f"/api/v1/video-projects/{p['id']}/produce", json={"allow_placeholders": True})
    drain(container, 60)
    out = client.get(f"/api/v1/video-projects/{p['id']}").json()
    assert out["status"] == "failed" and "VieNeu" in out["last_error"]
    assert out["scenes"][0]["segments"][0]["status"] == "failed"
    r = client.post(f"/api/v1/video-projects/{p['id']}/retry")
    assert r.json()["status"] == "producing"


def test_long_sample_builds_long_profile_segments(client, company):
    _fake_voice(client, company["id"])
    p = _project(client, company["id"], _sample(client, "long_mat_troi"))
    assert p["profile"] == "long" and p["profile_limits"] == {"min_s": 180, "max_s": 600}
    assert p["estimated_duration_s"] >= 180
    norm = " ".join(s["normalized_text"] for sc in p["scenes"] for s in sc["segments"])
    assert (
        "một trăm năm mươi triệu ki lô mét" in norm and "chín mươi chín phẩy tám phần trăm" in norm
    )
