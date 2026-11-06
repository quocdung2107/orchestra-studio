from __future__ import annotations

import json
import uuid

from fastapi import APIRouter

from orchestra_backend.api.deps import ContainerDep
from orchestra_backend.core.errors import ErrorResponse, NotFoundError
from orchestra_backend.production import service as prod
from orchestra_backend.production.models import VideoProject, VoiceSegment
from orchestra_backend.production.schemas import (
    ImageSourceIn,
    ImagesRequest,
    JobOut,
    MusicIn,
    ProduceIn,
    ProjectCreate,
    ProjectOut,
    ProjectSummary,
    SampleScript,
    SceneImageIn,
    SceneUpdate,
    ScriptIn,
    VoiceProfileChoice,
)

router = APIRouter(
    tags=["production"],
    responses={
        404: {"model": ErrorResponse},
        409: {"model": ErrorResponse},
        422: {"model": ErrorResponse},
    },
)


def _wake(c: ContainerDep) -> None:
    c.extras["job_runner"].wake()


@router.get("/video-samples", response_model=list[SampleScript])
def video_samples(c: ContainerDep) -> list[SampleScript]:
    d = c.settings.templates_dir / "video_samples"
    out = []
    for f in sorted(d.glob("*.json")) if d.is_dir() else []:
        out.append(
            SampleScript(
                id=f.stem, script=ScriptIn.model_validate(json.loads(f.read_text("utf-8")))
            )
        )
    return out


@router.post("/companies/{company_id}/video-projects", response_model=ProjectOut, status_code=201)
def create_project(c: ContainerDep, company_id: uuid.UUID, body: ProjectCreate) -> ProjectOut:
    return c.run_tx(
        lambda s: prod.project_out(
            s, prod.create_project(s, company_id, body.script, body.voice_profile_id)
        )
    )


@router.get("/companies/{company_id}/video-projects", response_model=list[ProjectSummary])
def list_projects(c: ContainerDep, company_id: uuid.UUID) -> list[ProjectSummary]:
    from sqlalchemy import select

    with c.tx() as s:
        rows = s.scalars(
            select(VideoProject)
            .where(VideoProject.company_id == company_id)
            .order_by(VideoProject.created_at.desc())
        )
        return [ProjectSummary.model_validate(p) for p in rows]


@router.get("/video-projects/{project_id}", response_model=ProjectOut)
def get_project(c: ContainerDep, project_id: uuid.UUID) -> ProjectOut:
    return c.run_tx(lambda s: prod.project_out(s, prod.get_project(s, project_id)))


@router.post("/video-projects/{project_id}/image-source", response_model=ProjectOut)
def set_image_source(c: ContainerDep, project_id: uuid.UUID, body: ImageSourceIn) -> ProjectOut:
    def run(s):  # type: ignore[no-untyped-def]
        p = prod.confirm_image_source(s, prod.get_project(s, project_id), body.source)
        return prod.project_out(s, p)

    return c.run_tx(run)


@router.patch("/video-scenes/{scene_id}", response_model=ProjectOut)
def update_scene(c: ContainerDep, scene_id: uuid.UUID, body: SceneUpdate) -> ProjectOut:
    def run(s):  # type: ignore[no-untyped-def]
        sc = prod.update_scene(s, prod.get_scene(s, scene_id), body)
        return prod.project_out(s, prod.get_project(s, sc.project_id))

    out = c.run_tx(run)
    _wake(c)
    return out


@router.put("/video-scenes/{scene_id}/image", response_model=ProjectOut)
def set_scene_image(c: ContainerDep, scene_id: uuid.UUID, body: SceneImageIn) -> ProjectOut:
    def run(s):  # type: ignore[no-untyped-def]
        sc = prod.set_scene_image(s, prod.get_scene(s, scene_id), body.asset_id)
        return prod.project_out(s, prod.get_project(s, sc.project_id))

    return c.run_tx(run)


@router.post("/video-projects/{project_id}/images", response_model=list[JobOut])
def request_images(c: ContainerDep, project_id: uuid.UUID, body: ImagesRequest) -> list[JobOut]:
    out = c.run_tx(
        lambda s: [
            JobOut.model_validate(j)
            for j in prod.request_images(
                s, prod.get_project(s, project_id), body.mode, body.scene_ids, body.replace
            )
        ]
    )
    _wake(c)
    return out


@router.put("/video-projects/{project_id}/voice-profile", response_model=ProjectOut)
def set_voice_profile(
    c: ContainerDep, project_id: uuid.UUID, body: VoiceProfileChoice
) -> ProjectOut:
    return c.run_tx(
        lambda s: prod.project_out(
            s, prod.change_voice(s, prod.get_project(s, project_id), body.voice_profile_id)
        )
    )


@router.put("/video-projects/{project_id}/music", response_model=ProjectOut)
def set_music(c: ContainerDep, project_id: uuid.UUID, body: MusicIn) -> ProjectOut:
    return c.run_tx(
        lambda s: prod.project_out(
            s, prod.set_music(s, prod.get_project(s, project_id), body.asset_id, body.gain_db)
        )
    )


@router.post("/video-projects/{project_id}/produce", response_model=ProjectOut)
def produce(c: ContainerDep, project_id: uuid.UUID, body: ProduceIn) -> ProjectOut:
    """Voice for every segment -> render -> QA. Runs in the background; poll the project."""
    out = c.run_tx(
        lambda s: prod.project_out(
            s, prod.produce(s, prod.get_project(s, project_id), body.allow_placeholders)
        )
    )
    _wake(c)
    return out


@router.post("/video-projects/{project_id}/retry", response_model=ProjectOut)
def retry(c: ContainerDep, project_id: uuid.UUID) -> ProjectOut:
    def run(s):  # type: ignore[no-untyped-def]
        p = prod.get_project(s, project_id)
        prod.retry(s, p)
        prod.advance(s, p.id)
        return prod.project_out(s, p)

    out = c.run_tx(run)
    _wake(c)
    return out


@router.post("/voice-segments/{segment_id}/regenerate", response_model=ProjectOut)
def regenerate_segment(c: ContainerDep, segment_id: uuid.UUID) -> ProjectOut:
    """Only this segment is synthesized again; every other segment keeps its file."""

    def run(s):  # type: ignore[no-untyped-def]
        seg = s.get(VoiceSegment, segment_id)
        if seg is None:
            raise NotFoundError("Segment not found", code="segment_not_found")
        prod.regenerate_segment(s, seg)
        return prod.project_out(s, prod.get_project(s, seg.project_id))

    out = c.run_tx(run)
    _wake(c)
    return out
