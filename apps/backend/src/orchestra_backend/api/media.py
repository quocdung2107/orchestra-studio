from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any, Literal

from fastapi import APIRouter, Query, Request
from fastapi.responses import FileResponse
from pydantic import BaseModel, ConfigDict

from orchestra_backend.api.deps import ContainerDep
from orchestra_backend.core.errors import ErrorResponse
from orchestra_backend.jobs import engines as eng
from orchestra_backend.jobs import runner as jobs
from orchestra_backend.jobs.models import Job
from orchestra_backend.media import service as media
from orchestra_backend.media_gateway import registry
from orchestra_backend.production.schemas import JobOut
from orchestra_backend.voice import service as voices
from orchestra_backend.voice.normalize_vi import normalize
from orchestra_backend.voice.schemas import (
    NormalizePreview,
    NormalizePreviewOut,
    VoiceProfileCreate,
    VoiceProfileOut,
    VoiceSettings,
)
from orchestra_backend.voice.segment import split_segments

router = APIRouter(
    tags=["media"],
    responses={
        404: {"model": ErrorResponse},
        409: {"model": ErrorResponse},
        413: {"model": ErrorResponse},
        422: {"model": ErrorResponse},
    },
)


class AssetOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    company_id: uuid.UUID
    kind: str
    label: str
    sha256: str
    mime: str
    bytes: int
    duration_s: float | None
    width: int | None
    height: int | None
    source: str
    provider: str | None
    model: str | None
    license_json: dict[str, Any]
    retention: str
    created_at: datetime


UploadKind = Literal["image", "music", "reference_audio"]


@router.put("/companies/{company_id}/assets", response_model=AssetOut, status_code=201)
async def upload_asset(
    c: ContainerDep,
    request: Request,
    company_id: uuid.UUID,
    kind: UploadKind = Query(...),
    label: str = Query(default="", max_length=300),
) -> AssetOut:
    """Raw-body upload (no multipart). Format is checked from the file's magic bytes."""
    store = c.extras["media_store"]
    chunks: list[bytes] = []
    size = 0
    limit = media.UPLOAD_LIMITS[kind]
    async for chunk in request.stream():
        size += len(chunk)
        if size > limit:
            from orchestra_backend.media.store import TooLarge

            raise TooLarge(f"File lớn hơn giới hạn {limit // (1024 * 1024)} MB")
        chunks.append(chunk)

    def save(s):  # type: ignore[no-untyped-def]
        return AssetOut.model_validate(
            media.upload(s, store, company_id=company_id, kind=kind, chunks=chunks, label=label)
        )

    return c.run_tx(save)


@router.get("/companies/{company_id}/assets", response_model=list[AssetOut])
def list_assets(
    c: ContainerDep,
    company_id: uuid.UUID,
    kind: str | None = None,
    limit: int = Query(default=100, le=500),
) -> list[AssetOut]:
    with c.tx() as s:
        return [AssetOut.model_validate(a) for a in media.list_assets(s, company_id, kind, limit)]


@router.get("/assets/{asset_id}", response_model=AssetOut)
def get_asset(c: ContainerDep, asset_id: uuid.UUID) -> AssetOut:
    with c.tx() as s:
        return AssetOut.model_validate(media.get_asset(s, asset_id))


@router.get("/assets/{asset_id}/content", response_class=FileResponse)
def asset_content(c: ContainerDep, asset_id: uuid.UUID, download: bool = False) -> FileResponse:
    """Streams the file; supports `Range` (206) for video seeking."""
    with c.tx() as s:
        a = media.get_asset(s, asset_id)
        path = c.extras["media_store"].path_for(a.sha256)
        ext = {
            "image/png": "png",
            "image/jpeg": "jpg",
            "image/webp": "webp",
            "audio/wav": "wav",
            "video/mp4": "mp4",
            "audio/mpeg": "mp3",
            "text/x-ass": "ass",
        }.get(a.mime, "bin")
        name = f"{a.kind}-{str(a.id)[:8]}.{ext}"
        return FileResponse(
            path,
            media_type=a.mime,
            filename=name if download else None,
            content_disposition_type="attachment" if download else "inline",
        )


# ---- providers / engines / scheduler --------------------------------------------------------
class ProviderOut(BaseModel):
    provider_id: str
    kind: str
    label: str
    version: str
    fake: bool
    license: dict[str, Any]
    hardware: dict[str, Any]
    allowed: bool
    blocked_reason: str | None = None


@router.get("/media/providers", response_model=list[ProviderOut])
def list_providers() -> list[ProviderOut]:
    out = []
    for m in registry.catalog():
        try:
            registry.check_license(m)
            allowed, reason = True, None
        except registry.LicenseBlocked as exc:
            allowed, reason = False, exc.message
        out.append(
            ProviderOut(
                provider_id=m.provider_id,
                kind=m.kind,
                label=m.label,
                version=m.version,
                fake=m.fake,
                license=m.license.model_dump(),
                hardware=m.hardware.model_dump(),
                allowed=allowed,
                blocked_reason=reason,
            )
        )
    return out


class EngineStatus(BaseModel):
    id: str
    label: str
    base_url: str
    managed: bool
    running: bool
    started_by_orchestra: bool
    in_use: int
    install_hint: str


@router.get("/media/engines", response_model=list[EngineStatus])
def list_engines(c: ContainerDep) -> list[EngineStatus]:
    m: eng.EngineManager = c.extras["engines"]
    return [EngineStatus.model_validate(m.status(s.id)) for s in m.specs()]


@router.get("/media/engines/config", response_model=eng.EnginesConfig)
def engines_config(c: ContainerDep) -> eng.EnginesConfig:
    return eng.EnginesConfig(engines=c.extras["engines"].specs())


@router.put("/media/engines/config", response_model=eng.EnginesConfig)
def put_engines_config(c: ContainerDep, body: eng.EnginesConfig) -> eng.EnginesConfig:
    m: eng.EngineManager = c.extras["engines"]
    eng.save_config(c.settings.data_dir / "engines.json", body.engines)
    m.replace_specs(eng.load_config(c.settings.data_dir / "engines.json"))
    return eng.EnginesConfig(engines=m.specs())


@router.get("/media/scheduler")
def scheduler_status(c: ContainerDep) -> dict[str, Any]:
    return c.extras["scheduler"].snapshot()


@router.get("/media/tts/{provider_id}/voices")
def tts_voices(
    c: ContainerDep, provider_id: Literal["vieneu", "zerotts", "fake_tts"]
) -> list[dict[str, Any]]:
    """Voices reported by the running engine (the engine must be started)."""
    p = registry.tts_provider(provider_id)
    url = None
    if p.meta.hardware.engine:
        url = c.extras["engines"].ensure_running(p.meta.hardware.engine)
    return p.voices(url)


@router.get("/companies/{company_id}/media-settings", response_model=registry.MediaSettings)
def get_media_settings(c: ContainerDep, company_id: uuid.UUID) -> registry.MediaSettings:
    return c.run_tx(lambda s: registry.get_settings(s, company_id))


@router.put("/companies/{company_id}/media-settings", response_model=registry.MediaSettings)
def put_media_settings(
    c: ContainerDep, company_id: uuid.UUID, body: registry.MediaSettings
) -> registry.MediaSettings:
    return c.run_tx(lambda s: registry.put_settings(s, company_id, body))


# ---- voice ------------------------------------------------------------------------------------
@router.post("/voice/normalize-preview", response_model=NormalizePreviewOut)
def normalize_preview(body: NormalizePreview) -> NormalizePreviewOut:
    segs = [
        normalize(x, dialect=body.dialect, lexicon=body.lexicon)
        for x in split_segments(body.text, body.max_chars)
    ]
    return NormalizePreviewOut(normalized=" ".join(segs), segments=segs)


@router.get("/companies/{company_id}/voice-profiles", response_model=list[VoiceProfileOut])
def list_voice_profiles(c: ContainerDep, company_id: uuid.UUID) -> list[VoiceProfileOut]:
    def run(s):  # type: ignore[no-untyped-def]
        rows = voices.list_for(s, company_id)
        if not rows:
            rows = [voices.default_for(s, company_id)]
        return [voices.to_out(s, p) for p in rows]

    return c.run_tx(run)


@router.post(
    "/companies/{company_id}/voice-profiles", response_model=VoiceProfileOut, status_code=201
)
def create_voice_profile(
    c: ContainerDep, company_id: uuid.UUID, body: VoiceProfileCreate
) -> VoiceProfileOut:
    return c.run_tx(lambda s: voices.to_out(s, voices.create(s, company_id, body)))


@router.put("/voice-profiles/{profile_id}", response_model=VoiceProfileOut)
def update_voice_profile(
    c: ContainerDep, profile_id: uuid.UUID, body: VoiceSettings
) -> VoiceProfileOut:
    """Creates a new version; projects pick it up on their next production run."""
    return c.run_tx(lambda s: voices.to_out(s, voices.update(s, voices.get(s, profile_id), body)))


# ---- jobs -------------------------------------------------------------------------------------
@router.get("/companies/{company_id}/jobs", response_model=list[JobOut])
def list_jobs(
    c: ContainerDep,
    company_id: uuid.UUID,
    status: str | None = None,
    limit: int = Query(default=100, le=500),
) -> list[JobOut]:
    from sqlalchemy import select

    with c.tx() as s:
        q = select(Job).where(Job.company_id == company_id)
        if status:
            q = q.where(Job.status == status)
        return [
            JobOut.model_validate(j)
            for j in s.scalars(q.order_by(Job.created_at.desc()).limit(limit))
        ]


@router.post("/jobs/{job_id}/retry", response_model=JobOut)
def retry_job(c: ContainerDep, job_id: uuid.UUID) -> JobOut:
    out = c.run_tx(lambda s: JobOut.model_validate(jobs.retry_job(s, jobs.get_job(s, job_id))))
    c.extras["job_runner"].wake()
    return out


@router.post("/jobs/{job_id}/cancel", response_model=JobOut)
def cancel_job(c: ContainerDep, job_id: uuid.UUID) -> JobOut:
    return c.run_tx(lambda s: JobOut.model_validate(jobs.cancel_job(s, jobs.get_job(s, job_id))))
