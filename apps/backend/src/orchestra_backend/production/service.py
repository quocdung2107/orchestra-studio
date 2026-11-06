"""Video project pipeline, driven by state (ADR-0033).

`advance()` looks at what is missing and enqueues jobs (TTS per segment -> render -> ASR QA).
Every job handler calls `advance()` when it finishes, so the pipeline continues after a restart.
"""

from __future__ import annotations

import hashlib
import json
import uuid
from typing import Any

from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from orchestra_backend.companies.service import get_company
from orchestra_backend.core.errors import DomainValidationError, InvalidStateError, NotFoundError
from orchestra_backend.core.time import utcnow
from orchestra_backend.events.service import append_event
from orchestra_backend.jobs.models import Job
from orchestra_backend.jobs.runner import enqueue, retry_job
from orchestra_backend.media.models import Asset
from orchestra_backend.media_gateway.registry import get_settings, tts_provider
from orchestra_backend.production.models import VideoProject, VideoRender, VideoScene, VoiceSegment
from orchestra_backend.production.schemas import (
    JobOut,
    ProjectOut,
    RenderOut,
    SceneOut,
    SceneUpdate,
    ScriptIn,
    SegmentOut,
)
from orchestra_backend.render.presets import PROFILES
from orchestra_backend.voice import service as voices
from orchestra_backend.voice.models import VoiceProfileVersion
from orchestra_backend.voice.normalize_vi import normalize
from orchestra_backend.voice.segment import split_segments

CHARS_PER_SECOND = 14.0  # rough Vietnamese narration speed for estimates only


# ---- lookups ---------------------------------------------------------------------------
def get_project(s: Session, project_id: uuid.UUID) -> VideoProject:
    p = s.get(VideoProject, project_id)
    if p is None:
        raise NotFoundError("Video project not found", code="video_project_not_found")
    return p


def get_scene(s: Session, scene_id: uuid.UUID) -> VideoScene:
    sc = s.get(VideoScene, scene_id)
    if sc is None:
        raise NotFoundError("Scene not found", code="scene_not_found")
    return sc


def scenes_of(s: Session, project_id: uuid.UUID) -> list[VideoScene]:
    return list(
        s.scalars(
            select(VideoScene).where(VideoScene.project_id == project_id).order_by(VideoScene.index)
        )
    )


def segments_of(s: Session, scene_id: uuid.UUID) -> list[VoiceSegment]:
    return list(
        s.scalars(
            select(VoiceSegment)
            .where(VoiceSegment.scene_id == scene_id)
            .order_by(VoiceSegment.index)
        )
    )


def renders_of(s: Session, project_id: uuid.UUID) -> list[VideoRender]:
    return list(
        s.scalars(
            select(VideoRender)
            .where(VideoRender.project_id == project_id)
            .order_by(VideoRender.version.desc())
        )
    )


# ---- segments ----------------------------------------------------------------------------
def build_segments(
    s: Session, project: VideoProject, scene: VideoScene, version: VoiceProfileVersion
) -> list[VoiceSegment]:
    """Split the original narration (for subtitles) and normalize each piece (for TTS)."""
    s.execute(delete(VoiceSegment).where(VoiceSegment.scene_id == scene.id))
    lexicon = {str(k): str(v) for k, v in (version.lexicon_json or {}).items()}
    out: list[VoiceSegment] = []
    idx = 0
    for piece in split_segments(scene.narration, version.max_chars):
        norm = normalize(piece, dialect=version.dialect, lexicon=lexicon)  # type: ignore[arg-type]
        # A normalized piece can be much longer than its source ("2026" -> 7 words).
        sub = (
            [norm]
            if len(norm) <= version.max_chars * 1.6
            else split_segments(norm, version.max_chars)
        )
        for part in sub:
            seg = VoiceSegment(
                project_id=project.id,
                scene_id=scene.id,
                index=idx,
                text=piece if len(sub) == 1 else part,
                normalized_text=part,
                profile_version_id=version.id,
            )
            s.add(seg)
            out.append(seg)
            idx += 1
    s.flush()
    return out


def _all_segments(s: Session, project_id: uuid.UUID) -> list[VoiceSegment]:
    rows = s.execute(
        select(VoiceSegment, VideoScene.index)
        .join(VideoScene, VideoScene.id == VoiceSegment.scene_id)
        .where(VoiceSegment.project_id == project_id)
        .order_by(VideoScene.index, VoiceSegment.index)
    ).all()
    return [r[0] for r in rows]


# ---- project lifecycle -------------------------------------------------------------------
def create_project(
    s: Session, company_id: uuid.UUID, script: ScriptIn, voice_profile_id: uuid.UUID | None
) -> VideoProject:
    get_company(s, company_id)
    profile = (
        voices.get(s, voice_profile_id) if voice_profile_id else voices.default_for(s, company_id)
    )
    if profile.company_id != company_id:
        raise DomainValidationError("Voice profile thuộc công ty khác", code="voice_profile_scope")
    p = VideoProject(
        company_id=company_id,
        title=script.title,
        profile=script.profile,
        voice_profile_id=profile.id,
        script_json=script.model_dump(mode="json"),
    )
    s.add(p)
    s.flush()
    version = voices.current_version(s, profile)
    for i, sc in enumerate(script.scenes):
        scene = VideoScene(
            project_id=p.id,
            index=i,
            narration=sc.narration.strip(),
            visual_prompt=sc.visual_prompt,
            motion=sc.motion,
        )
        s.add(scene)
        s.flush()
        build_segments(s, p, scene, version)
    append_event(
        s,
        company_id=company_id,
        event_type="video.project_created",
        payload={"project_id": str(p.id), "title": p.title, "profile": p.profile},
        source="production",
    )
    return p


def confirm_image_source(s: Session, p: VideoProject, source: str) -> VideoProject:
    p.image_source = source
    p.image_source_confirmed_at = utcnow()
    return p


def set_scene_image(s: Session, scene: VideoScene, asset_id: uuid.UUID) -> VideoScene:
    p = get_project(s, scene.project_id)
    a = s.get(Asset, asset_id)
    if a is None or a.company_id != p.company_id or a.kind != "image":
        raise DomainValidationError("Ảnh không hợp lệ", code="invalid_image_asset")
    scene.image_asset_id = a.id
    _touch(p)
    return scene


def _touch(p: VideoProject) -> None:
    """An input changed: a ready video becomes outdated until it is produced again."""
    if p.status in ("ready", "qa_failed", "failed"):
        p.status = "draft"


def update_scene(s: Session, scene: VideoScene, data: SceneUpdate) -> VideoScene:
    p = get_project(s, scene.project_id)
    if data.visual_prompt is not None:
        scene.visual_prompt = data.visual_prompt
    if data.motion is not None:
        scene.motion = data.motion
    if data.pause_after_s is not None:
        scene.pause_after_s = data.pause_after_s
    if data.narration is not None and data.narration.strip() != scene.narration:
        scene.narration = data.narration.strip()
        prof = voices.get(s, p.voice_profile_id)
        build_segments(s, p, scene, voices.current_version(s, prof))
    _touch(p)
    if p.status == "producing":
        advance(s, p.id)
    return scene


def change_voice(s: Session, p: VideoProject, profile_id: uuid.UUID) -> VideoProject:
    prof = voices.get(s, profile_id)
    if prof.company_id != p.company_id:
        raise DomainValidationError("Voice profile thuộc công ty khác", code="voice_profile_scope")
    p.voice_profile_id = prof.id
    version = voices.current_version(s, prof)
    for sc in scenes_of(s, p.id):
        build_segments(s, p, sc, version)
    _touch(p)
    return p


def refresh_voice_version(s: Session, p: VideoProject) -> int:
    """Rebuild segments whose profile version is older than the profile's current version."""
    prof = voices.get(s, p.voice_profile_id)
    version = voices.current_version(s, prof)
    n = 0
    for sc in scenes_of(s, p.id):
        segs = segments_of(s, sc.id)
        if any(x.profile_version_id != version.id for x in segs):
            build_segments(s, p, sc, version)
            n += 1
    if n:
        _touch(p)
    return n


def set_music(
    s: Session, p: VideoProject, asset_id: uuid.UUID | None, gain_db: float
) -> VideoProject:
    if asset_id is not None:
        a = s.get(Asset, asset_id)
        if a is None or a.company_id != p.company_id or a.kind != "music":
            raise DomainValidationError("Nhạc nền không hợp lệ", code="invalid_music_asset")
    p.music_asset_id = asset_id
    p.music_gain_db = gain_db
    _touch(p)
    return p


def regenerate_segment(s: Session, seg: VoiceSegment) -> VoiceSegment:
    seg.generation += 1
    seg.status = "pending"
    seg.asset_id = None
    seg.duration_s = None
    seg.error = None
    p = get_project(s, seg.project_id)
    p.status = "producing"
    p.last_error = None
    advance(s, p.id)
    return seg


def request_images(
    s: Session, p: VideoProject, mode: str, scene_ids: list[uuid.UUID] | None, replace: bool
) -> list[Job]:
    if mode == "cloud":
        if p.image_source != "cloud":
            raise InvalidStateError(
                "Dự án đang ở chế độ ảnh nhập tay; hãy đổi nguồn ảnh sang cloud",
                code="image_source_not_cloud",
            )
        cfg = get_settings(s, p.company_id).cloud_image
        if not cfg.configured:
            raise DomainValidationError(
                "Chưa cấu hình dịch vụ ảnh cloud", code="cloud_image_not_configured"
            )
    jobs = []
    for sc in scenes_of(s, p.id):
        if scene_ids is not None and sc.id not in scene_ids:
            continue
        if sc.image_asset_id and not replace:
            continue
        active = [
            j
            for j in s.scalars(
                select(Job).where(
                    Job.subject_id == p.id,
                    Job.kind == "image.generate",
                    Job.status.in_(("queued", "running")),
                )
            )
            if j.payload_json.get("scene_id") == str(sc.id)
        ]
        if active:
            jobs.extend(active)
            continue
        jobs.append(
            enqueue(
                s,
                company_id=p.company_id,
                kind="image.generate",
                subject_id=p.id,
                payload={"scene_id": str(sc.id), "mode": mode},
                idempotency_key=f"img:{sc.id}:{uuid.uuid4().hex}",
                priority=1,
            )
        )
    return jobs


def produce(s: Session, p: VideoProject, allow_placeholders: bool) -> VideoProject:
    if p.image_source is None:
        raise InvalidStateError(
            "Hãy xác nhận cách nhận ảnh (nhập tay hoặc cloud) trước",
            code="image_source_not_confirmed",
        )
    if any(r.status in ("queued", "running") for r in renders_of(s, p.id)):
        raise InvalidStateError("Đang render, hãy chờ", code="render_in_progress")
    refresh_voice_version(s, p)
    missing = [sc for sc in scenes_of(s, p.id) if sc.image_asset_id is None]
    if missing:
        if not allow_placeholders:
            nums = ", ".join(str(m.index + 1) for m in missing)
            raise DomainValidationError(
                f"{len(missing)} cảnh chưa có ảnh (cảnh {nums})",
                code="scene_images_missing",
                details={"scene_ids": [str(m.id) for m in missing]},
            )
        request_images(s, p, "placeholder", [m.id for m in missing], replace=False)
    # Segments that failed earlier get another chance.
    for seg in _all_segments(s, p.id):
        if seg.status == "failed":
            seg.generation += 1
            seg.status = "pending"
            seg.error = None
    p.status = "producing"
    p.last_error = None
    advance(s, p.id)
    return p


def retry(s: Session, p: VideoProject) -> int:
    n = 0
    for job in s.scalars(select(Job).where(Job.subject_id == p.id, Job.status == "failed")):
        retry_job(s, job)
        n += 1
    for seg in _all_segments(s, p.id):
        if seg.status == "failed":
            seg.status = "pending"
            seg.error = None
    p.status = "producing"
    p.last_error = None
    return n


def content_key(s: Session, p: VideoProject) -> str:
    st = get_settings(s, p.company_id)
    data: dict[str, Any] = {
        "profile": p.profile,
        "music": [str(p.music_asset_id), p.music_gain_db],
        "encoder": st.encoder,
        "font": st.subtitle_font,
        "burn": st.burn_subtitles,
        "scenes": [],
    }
    for sc in scenes_of(s, p.id):
        data["scenes"].append(
            {
                "img": str(sc.image_asset_id),
                "motion": sc.motion,
                "pause": sc.pause_after_s,
                "segs": [[str(x.asset_id), x.text] for x in segments_of(s, sc.id)],
            }
        )
    return hashlib.sha256(json.dumps(data, sort_keys=True).encode()).hexdigest()


def advance(s: Session, project_id: uuid.UUID) -> None:
    p = get_project(s, project_id)
    if p.status != "producing":
        return
    segs = _all_segments(s, p.id)
    if any(x.status == "failed" for x in segs):
        return
    prof = voices.get(s, p.voice_profile_id)
    engine = voices.current_version(s, prof).engine
    tts_provider(engine)  # license check before queueing anything
    pending = [x for x in segs if x.status == "pending"]
    for seg in pending:
        enqueue(
            s,
            company_id=p.company_id,
            kind="tts.segment",
            subject_id=p.id,
            payload={"segment_id": str(seg.id), "generation": seg.generation},
            idempotency_key=f"tts:{seg.id}:{seg.generation}",
            max_attempts=3,
        )
    if pending:
        return
    if any(sc.image_asset_id is None for sc in scenes_of(s, p.id)):
        return  # waiting for image jobs
    renders = renders_of(s, p.id)
    if renders and renders[0].status in ("queued", "running"):
        return
    key = content_key(s, p)
    if renders and renders[0].content_key == key and renders[0].status == "succeeded":
        if renders[0].qa_json is not None and renders[0].qa_json.get("asr_pending"):
            return
        p.latest_render_id = renders[0].id
        p.status = "ready" if renders[0].qa_passed else "qa_failed"
        return
    if renders and renders[0].content_key == key and renders[0].status == "failed":
        return  # same inputs failed already; user must retry
    r = VideoRender(
        project_id=p.id,
        version=(renders[0].version + 1) if renders else 1,
        content_key=key,
        encoder=get_settings(s, p.company_id).encoder,
    )
    s.add(r)
    s.flush()
    enqueue(
        s,
        company_id=p.company_id,
        kind="video.render",
        subject_id=p.id,
        payload={"render_id": str(r.id)},
        idempotency_key=f"render:{r.id}",
        max_attempts=2,
    )


def on_job_finished(s: Session, job: Job) -> None:
    """Runner callback: record failures on the entity the job worked on."""
    if job.status != "failed" or job.subject_id is None:
        return
    p = s.get(VideoProject, job.subject_id)
    if p is None:
        return
    msg = f"{job.kind}: {job.error or job.error_code}"
    if job.kind == "tts.segment":
        seg = s.get(VoiceSegment, uuid.UUID(job.payload_json["segment_id"]))
        if seg is not None and seg.generation == job.payload_json.get("generation"):
            seg.status = "failed"
            seg.error = (job.error or "")[:1000]
    elif job.kind == "video.render":
        r = s.get(VideoRender, uuid.UUID(job.payload_json["render_id"]))
        if r is not None:
            r.status = "failed"
            r.error = (job.error or "")[:2000]
    p.status = "failed"
    p.last_error = msg[:2000]


# ---- output ------------------------------------------------------------------------------
def project_out(s: Session, p: VideoProject) -> ProjectOut:
    prof = voices.get(s, p.voice_profile_id)
    scenes = []
    total_chars = 0
    for sc in scenes_of(s, p.id):
        segs = segments_of(s, sc.id)
        total_chars += sum(len(x.normalized_text) for x in segs)
        img = s.get(Asset, sc.image_asset_id) if sc.image_asset_id else None
        scenes.append(
            SceneOut(
                id=sc.id,
                index=sc.index,
                narration=sc.narration,
                visual_prompt=sc.visual_prompt,
                motion=sc.motion,
                pause_after_s=sc.pause_after_s,
                image_asset_id=sc.image_asset_id,
                image_is_placeholder=bool(img and img.provider == "fake_image"),
                segments=[SegmentOut.model_validate(x) for x in segs],
            )
        )
    renders = renders_of(s, p.id)
    jobs = list(
        s.scalars(
            select(Job).where(Job.subject_id == p.id).order_by(Job.created_at.desc()).limit(60)
        )
    )
    prof_limits = PROFILES[p.profile]
    latest = next(
        (r for r in renders if r.id == p.latest_render_id), renders[0] if renders else None
    )
    return ProjectOut(
        id=p.id,
        company_id=p.company_id,
        title=p.title,
        profile=p.profile,
        status=p.status,
        image_source=p.image_source,
        created_at=p.created_at,
        updated_at=p.updated_at,
        image_source_confirmed_at=p.image_source_confirmed_at,
        voice_profile_id=p.voice_profile_id,
        voice_profile_name=prof.name,
        music_asset_id=p.music_asset_id,
        music_gain_db=p.music_gain_db,
        last_error=p.last_error,
        estimated_duration_s=round(total_chars / CHARS_PER_SECOND + 0.6 * len(scenes), 1),
        profile_limits={"min_s": prof_limits.min_s, "max_s": prof_limits.max_s},
        scenes=scenes,
        latest_render=RenderOut.model_validate(latest) if latest else None,
        renders=[RenderOut.model_validate(r) for r in renders[:10]],
        jobs=[JobOut.model_validate(j) for j in jobs],
    )
