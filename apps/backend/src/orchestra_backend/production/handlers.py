"""Job handlers for video production (ADR-0029..0033). They run in worker threads."""

from __future__ import annotations

import shutil
import tempfile
import uuid
from pathlib import Path
from typing import Any

from orchestra_backend.api.deps import Container
from orchestra_backend.credentials import service as creds
from orchestra_backend.events.service import append_event
from orchestra_backend.jobs.models import Job
from orchestra_backend.jobs.runner import JobContext, JobError, enqueue
from orchestra_backend.jobs.scheduler import ResourceReq
from orchestra_backend.media import service as media
from orchestra_backend.media.models import Asset
from orchestra_backend.media.store import MediaStore
from orchestra_backend.media_gateway import audio
from orchestra_backend.media_gateway.meta import ImageRequest, TtsRequest
from orchestra_backend.media_gateway.registry import (
    FAKE_IMAGE,
    asr_provider,
    cloud_image_provider,
    get_settings,
    tts_provider,
)
from orchestra_backend.production import service as prod
from orchestra_backend.production.models import VideoProject, VideoRender, VoiceSegment
from orchestra_backend.render import ffmpeg_render, qa, subtitles
from orchestra_backend.render.presets import PROFILES
from orchestra_backend.render.timeline import (
    LEAD_IN_S,
    MOTIONS,
    SEGMENT_GAP_S,
    Canvas,
    Music,
    Timeline,
    TimelineScene,
    Visual,
    VoicePlacement,
    cues_for_segment,
)
from orchestra_backend.render.wer import wer
from orchestra_backend.voice.models import VoiceProfileVersion

MIN_SCENE_S = 1.5


def _store(c: Container) -> MediaStore:
    return c.extras["media_store"]


def _work_dir(c: Container, name: str) -> Path:
    root = c.settings.data_dir / "tmp"
    root.mkdir(parents=True, exist_ok=True)
    return Path(tempfile.mkdtemp(prefix=f"{name}-", dir=root))


def _license(meta: Any) -> dict[str, Any]:
    return meta.license.model_dump(mode="json")


# ---- TTS ------------------------------------------------------------------------------------
class TtsSegmentHandler:
    kind = "tts.segment"

    def _load(
        self, c: Container, job_payload: dict[str, Any]
    ) -> tuple[VoiceSegment, VoiceProfileVersion]:
        with c.tx() as s:
            seg = s.get(VoiceSegment, uuid.UUID(job_payload["segment_id"]))
            if seg is None:
                raise JobError("segment_gone", "Đoạn giọng đã bị xóa", retryable=False)
            ver = s.get(VoiceProfileVersion, seg.profile_version_id)
            assert ver is not None
            s.expunge(seg)
            s.expunge(ver)
            return seg, ver

    def resources(self, job: Job, c: Container) -> ResourceReq:
        try:
            _, ver = self._load(c, job.payload_json)
        except JobError:
            return ResourceReq(device="none")
        return tts_provider(ver.engine).meta.hardware.as_req()

    def run(self, ctx: JobContext) -> dict[str, Any]:
        c = ctx.container
        seg, ver = self._load(c, ctx.payload)
        if seg.generation != ctx.payload["generation"] or seg.status == "ready":
            return {"skipped": "stale"}
        provider = tts_provider(ver.engine)
        work = _work_dir(c, "tts")
        try:
            raw = work / "raw.wav"
            res = provider.synthesize(
                TtsRequest(text=seg.normalized_text, voice=ver.voice, params=dict(ver.params_json)),
                ctx.engine_url,
                raw,
            )
            ctx.check_cancelled()
            house = audio.to_house_wav(
                res.wav_path,
                work / "voice.wav",
                speed=ver.speed,
                trim_silence=not provider.meta.fake,
            )
            dur = audio.duration(house)
            if dur < 0.2:
                raise JobError("tts_too_short", f"Audio quá ngắn ({dur:.2f}s)")
            stored = _store(c).put_file(house)
            with c.tx() as s:
                seg_db = s.get(VoiceSegment, seg.id)
                if seg_db is None or seg_db.generation != ctx.payload["generation"]:
                    return {"skipped": "stale"}
                p = s.get(VideoProject, seg_db.project_id)
                assert p is not None
                asset = media.register(
                    s,
                    _store(c),
                    stored,
                    company_id=p.company_id,
                    kind="voice",
                    source="provider",
                    label=f"{p.title} — cảnh đoạn {seg_db.index + 1}",
                    provider=provider.meta.provider_id,
                    model=res.engine_version,
                    params={
                        "voice": ver.voice,
                        "profile_version_id": str(ver.id),
                        "speed": ver.speed,
                        "text": seg.normalized_text,
                        **ver.params_json,
                    },
                    license_info=_license(provider.meta),
                )
                seg_db.asset_id = asset.id
                seg_db.duration_s = dur
                seg_db.status = "ready"
                seg_db.error = None
                prod.advance(s, p.id)
            return {"asset_id": str(asset.id), "duration_s": dur, "warnings": res.warnings}
        finally:
            shutil.rmtree(work, ignore_errors=True)


# ---- images ----------------------------------------------------------------------------------
class ImageGenerateHandler:
    kind = "image.generate"

    def resources(self, job: Job, c: Container) -> ResourceReq:
        return ResourceReq(device="none")

    def run(self, ctx: JobContext) -> dict[str, Any]:
        c = ctx.container
        with c.tx() as s:
            scene = prod.get_scene(s, uuid.UUID(ctx.payload["scene_id"]))
            p = prod.get_project(s, scene.project_id)
            prof = PROFILES[p.profile]
            prompt = scene.visual_prompt or scene.narration[:400]
            company_id, project_id, scene_id = p.company_id, p.id, scene.id
            title, index = p.title, scene.index
            if ctx.payload["mode"] == "cloud":
                cfg = get_settings(s, p.company_id).cloud_image
                key = None
                if cfg.credential_id:
                    cred = creds.get(s, cfg.credential_id)
                    problem = creds.check_usable(cred, "image_api", p.company_id)
                    if problem:
                        raise JobError(problem[0], problem[1], retryable=False)
                    key = creds.handle(cred, c.extras["secrets"]).reveal()
                provider: Any = cloud_image_provider(cfg, key, c.extras.get("image_transport"))
            else:
                provider = FAKE_IMAGE
        work = _work_dir(c, "img")
        try:
            # Placeholders are rendered at canvas size; cloud images are cropped at render time.
            res = provider.generate(
                ImageRequest(prompt=prompt, width=prof.width, height=prof.height, seed=index),
                work / "image.bin",
            )
            stored = _store(c).put_file(res.path)
            with c.tx() as s:
                asset = media.register(
                    s,
                    _store(c),
                    stored,
                    company_id=company_id,
                    kind="image",
                    source="provider",
                    label=f"{title} — cảnh {index + 1}",
                    provider=provider.meta.provider_id,
                    model=res.model,
                    params={"prompt": prompt, "revised_prompt": res.revised_prompt},
                    license_info=_license(provider.meta),
                )
                scene_db = prod.get_scene(s, scene_id)
                scene_db.image_asset_id = asset.id
                prod.advance(s, project_id)
            return {"asset_id": str(asset.id), "cost_usd": res.cost_usd}
        finally:
            shutil.rmtree(work, ignore_errors=True)


# ---- render ---------------------------------------------------------------------------------
def build_timeline(c: Container, render_id: uuid.UUID) -> tuple[Timeline, dict[str, Any]]:
    with c.tx() as s:
        r = s.get(VideoRender, render_id)
        assert r is not None
        p = prod.get_project(s, r.project_id)
        st = get_settings(s, p.company_id)
        prof = PROFILES[p.profile]
        t = 0.0
        scenes: list[TimelineScene] = []
        images: dict[str, Path] = {}
        voice_parts: list[tuple[Path | None, float]] = []
        licenses: list[dict[str, Any]] = []
        placeholders: list[str] = []
        all_text: list[str] = []
        store = _store(c)
        for sc in prod.scenes_of(s, p.id):
            img = s.get(Asset, sc.image_asset_id) if sc.image_asset_id else None
            if img is None:
                raise JobError(
                    "scene_image_missing", f"Cảnh {sc.index + 1} chưa có ảnh", retryable=False
                )
            images[str(img.id)] = store.path_for(img.sha256)
            licenses.append({"asset_id": str(img.id), **img.license_json})
            if img.provider == "fake_image":
                placeholders.append("ảnh giữ chỗ")
            cursor = LEAD_IN_S if sc.index == 0 else 0.15
            voice_parts.append((None, cursor))
            placements, cues = [], []
            segs = prod.segments_of(s, sc.id)
            for i, seg in enumerate(segs):
                a = s.get(Asset, seg.asset_id) if seg.asset_id else None
                if a is None or seg.duration_s is None:
                    raise JobError("segment_not_ready", "Đoạn giọng chưa sẵn sàng", retryable=True)
                licenses.append({"asset_id": str(a.id), **a.license_json})
                if a.provider == "fake_tts":
                    placeholders.append("giọng giả")
                start = t + cursor
                placements.append(
                    VoicePlacement(
                        segment_id=seg.id,
                        asset_id=a.id,
                        start=round(start, 3),
                        duration=seg.duration_s,
                    )
                )
                cues += cues_for_segment(seg.text, start, seg.duration_s, prof.max_chars_per_line)
                voice_parts.append((store.path_for(a.sha256), seg.duration_s))
                all_text.append(seg.normalized_text)
                cursor += seg.duration_s
                if i < len(segs) - 1:
                    voice_parts.append((None, SEGMENT_GAP_S))
                    cursor += SEGMENT_GAP_S
            dur = max(MIN_SCENE_S, cursor + sc.pause_after_s)
            voice_parts.append((None, dur - cursor))
            motion = MOTIONS[sc.index % len(MOTIONS)] if sc.motion == "auto" else sc.motion
            scenes.append(
                TimelineScene(
                    id=sc.id,
                    index=sc.index,
                    start=round(t, 3),
                    duration=round(dur, 3),
                    visual=Visual(
                        asset_id=img.id, motion=motion, placeholder=img.provider == "fake_image"
                    ),
                    voice=placements,
                    cues=cues,
                )
            )
            t += round(dur, 3)
        music = None
        music_path = None
        if p.music_asset_id:
            m = s.get(Asset, p.music_asset_id)
            assert m is not None
            music = Music(asset_id=m.id, gain_db=p.music_gain_db)
            music_path = store.path_for(m.sha256)
            licenses.append({"asset_id": str(m.id), **m.license_json})
        tl = Timeline(
            profile=p.profile,
            preset=prof.preset,
            canvas=Canvas(w=prof.width, h=prof.height, fps=prof.fps),
            duration=round(t, 3),
            scenes=scenes,
            music=music,
            subtitle_style={"font_size": prof.font_size, "margin_v": prof.margin_v},
            burn_subtitles=st.burn_subtitles,
        )
        extra = {
            "images": images,
            "voice_parts": voice_parts,
            "music": music_path,
            "licenses": licenses,
            "placeholders": placeholders,
            "font": st.subtitle_font,
            "encoder": r.encoder,
            "company_id": p.company_id,
            "project_id": p.id,
            "title": p.title,
            "profile": prof,
            "asr": st.asr_provider,
            "text": " ".join(all_text),
        }
        return tl, extra


class RenderHandler:
    kind = "video.render"

    def resources(self, job: Job, c: Container) -> ResourceReq:
        with c.tx() as s:
            r = s.get(VideoRender, uuid.UUID(job.payload_json["render_id"]))
            gpu = bool(r and r.encoder == "h264_nvenc")
        return ResourceReq(
            device="gpu" if gpu else "cpu",
            est_ram_mb=c.settings.render_est_ram_mb,
            min_vram_mb=300 if gpu else 0,
        )

    def run(self, ctx: JobContext) -> dict[str, Any]:
        c = ctx.container
        render_id = uuid.UUID(ctx.payload["render_id"])
        with c.tx() as s:
            r = s.get(VideoRender, render_id)
            assert r is not None
            r.status = "running"
        tl, x = build_timeline(c, render_id)
        work = _work_dir(c, "render")
        try:
            voice = work / "voice.wav"
            audio.concat_house(x["voice_parts"], voice)
            ass_name = None
            if tl.burn_subtitles:
                subtitles.write_ass(tl, work / "subs.ass", x["font"])
                ass_name = "subs.ass"
            args = ffmpeg_render.build_args(
                tl,
                ffmpeg_render.RenderInputs(
                    images=x["images"], voice_wav=voice, music=x["music"], subtitles_ass=ass_name
                ),
                "out.mp4",
                x["encoder"],
            )
            secs, tail = ffmpeg_render.run_render(
                args,
                cwd=work,
                total_s=tl.duration,
                timeout_s=c.settings.render_timeout_s,
                progress=lambda f: ctx.progress(f, "Đang render"),
                cancelled=lambda: ctx._cancel(),
            )
            ctx.check_cancelled()
            report = qa.run_qa(
                work / "out.mp4",
                tl,
                x["profile"],
                assets_license=x["licenses"],
                placeholders=x["placeholders"],
            )
            store = _store(c)
            out_st = store.put_file(work / "out.mp4")
            voice_st = store.put_file(voice)
            ass_st = store.put_file(work / "subs.ass") if ass_name else None
            srt = subtitles.write_srt(tl, work / "subs.srt").read_text(encoding="utf-8")
            asr = x["asr"]
            with c.tx() as s:
                cid = x["company_id"]
                a_out = media.register(
                    s,
                    store,
                    out_st,
                    company_id=cid,
                    kind="render",
                    source="render",
                    label=f"{x['title']} (MP4)",
                    provider="ffmpeg",
                    model=ffmpeg_render.ffmpeg_version(),
                    license_info={"commercial": True, "source": "render"},
                )
                a_voice = media.register(
                    s,
                    store,
                    voice_st,
                    company_id=cid,
                    kind="voice",
                    source="render",
                    label=f"{x['title']} (voice track)",
                    retention="temp",
                    license_info={"commercial": True, "source": "render"},
                )
                a_ass = None
                if ass_st:
                    a_ass = media.register(
                        s,
                        store,
                        ass_st,
                        company_id=cid,
                        kind="subtitle",
                        source="render",
                        label=f"{x['title']} (ASS)",
                        license_info={"commercial": True, "source": "render"},
                    )
                r = s.get(VideoRender, render_id)
                assert r is not None
                report["srt"] = srt
                report["asr"] = (
                    {"status": "skipped", "reason": "Chưa bật ASR"}
                    if asr == "none"
                    else {"status": "pending"}
                )
                report["asr_pending"] = asr != "none"
                r.timeline_json = tl.model_dump(mode="json")
                r.asset_id, r.voice_asset_id = a_out.id, a_voice.id
                r.subtitle_asset_id = a_ass.id if a_ass else None
                r.qa_json, r.qa_passed = report, report["passed"]
                r.ffmpeg_args_json = args
                r.ffmpeg_version = ffmpeg_render.ffmpeg_version()
                r.render_seconds = round(secs, 2)
                r.log_tail = tail[-4000:]
                r.status = "succeeded"
                append_event(
                    s,
                    company_id=cid,
                    event_type="video.render_finished",
                    payload={
                        "project_id": str(x["project_id"]),
                        "render_id": str(r.id),
                        "status": r.status,
                        "qa_passed": r.qa_passed,
                    },
                    source="render",
                )
                if asr != "none":
                    enqueue(
                        s,
                        company_id=cid,
                        kind="video.asr_qa",
                        subject_id=x["project_id"],
                        payload={"render_id": str(r.id), "text": x["text"]},
                        idempotency_key=f"asr:{r.id}",
                    )
                else:
                    prod.advance(s, x["project_id"])
            return {
                "asset_id": str(a_out.id),
                "render_seconds": secs,
                "qa_passed": report["passed"],
            }
        finally:
            shutil.rmtree(work, ignore_errors=True)


class AsrQaHandler:
    kind = "video.asr_qa"

    def resources(self, job: Job, c: Container) -> ResourceReq:
        with c.tx() as s:
            r = s.get(VideoRender, uuid.UUID(job.payload_json["render_id"]))
            p = s.get(VideoProject, r.project_id) if r else None
            name = get_settings(s, p.company_id).asr_provider if p else "none"
        prov = asr_provider(name)
        return prov.meta.hardware.as_req() if prov else ResourceReq(device="none")

    def run(self, ctx: JobContext) -> dict[str, Any]:
        c = ctx.container
        with c.tx() as s:
            r = s.get(VideoRender, uuid.UUID(ctx.payload["render_id"]))
            assert r is not None and r.voice_asset_id is not None
            p = prod.get_project(s, r.project_id)
            st = get_settings(s, p.company_id)
            voice = s.get(Asset, r.voice_asset_id)
            assert voice is not None
            path = _store(c).path_for(voice.sha256)
        prov = asr_provider(st.asr_provider)
        if prov is None:
            result = {"status": "skipped", "reason": "Chưa bật ASR"}
        else:
            tr = prov.transcribe(path, ctx.engine_url, "vi", hint=ctx.payload["text"])
            score = wer(ctx.payload["text"], tr.text)
            result = {
                "status": "done",
                "provider": prov.meta.provider_id,
                "wer": round(score, 4),
                "max_wer": st.asr_max_wer,
                "transcript": tr.text[:4000],
            }
        with c.tx() as s:
            r = s.get(VideoRender, uuid.UUID(ctx.payload["render_id"]))
            assert r is not None
            report = dict(r.qa_json or {})
            report["asr"] = result
            report["asr_pending"] = False
            if result["status"] == "done":
                ok = result["wer"] <= st.asr_max_wer
                report["checks"] = [
                    *report.get("checks", []),
                    {
                        "id": "asr_wer",
                        "ok": ok,
                        "severity": "error",
                        "detail": f"WER {result['wer']:.1%} (ngưỡng {st.asr_max_wer:.0%})",
                    },
                ]
                report["passed"] = bool(report.get("passed")) and ok
            r.qa_json = report
            r.qa_passed = report.get("passed")
            prod.advance(s, r.project_id)
        return result


def register_all(runner: Any) -> None:
    for h in (TtsSegmentHandler(), ImageGenerateHandler(), RenderHandler(), AsrQaHandler()):
        runner.register(h)
    runner.after_finish.append(prod.on_job_finished)
