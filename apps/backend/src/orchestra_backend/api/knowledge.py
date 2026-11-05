from __future__ import annotations

import uuid

from fastapi import APIRouter, Query, status
from pydantic import BaseModel, ConfigDict, Field

from orchestra_backend.api.deps import ContainerDep
from orchestra_backend.companies.service import get_active_company, get_company
from orchestra_backend.core.errors import DomainValidationError, ErrorResponse
from orchestra_backend.execution import service as ex
from orchestra_backend.knowledge import service as kn
from orchestra_backend.knowledge.models import MAX_CONTENT
from orchestra_backend.knowledge.schemas import (
    KnowledgeCreate,
    KnowledgeOut,
    KnowledgeUpdate,
    LessonCreate,
    LessonOut,
    Review,
    RoleProposalCreate,
    RoleProposalOut,
    SearchResult,
)

router = APIRouter(
    tags=["knowledge"],
    responses={
        404: {"model": ErrorResponse},
        409: {"model": ErrorResponse},
        422: {"model": ErrorResponse},
    },
)


class ImportArtifact(BaseModel):
    model_config = ConfigDict(extra="forbid")

    title: str | None = Field(default=None, min_length=1, max_length=300)


@router.get("/companies/{company_id}/knowledge", response_model=list[KnowledgeOut])
def list_knowledge(c: ContainerDep, company_id: uuid.UUID) -> list[KnowledgeOut]:
    with c.tx() as s:
        get_company(s, company_id)
        return [KnowledgeOut.model_validate(i) for i in kn.list_items(s, company_id)]


@router.get("/companies/{company_id}/knowledge/search", response_model=SearchResult)
def search_knowledge(
    c: ContainerDep,
    company_id: uuid.UUID,
    q: str = Query(min_length=1, max_length=200),
    limit: int = Query(default=20, ge=1, le=50),
) -> SearchResult:
    with c.tx() as s:
        get_company(s, company_id)
        return kn.search(s, company_id, q, limit)


@router.post(
    "/companies/{company_id}/knowledge",
    response_model=KnowledgeOut,
    status_code=status.HTTP_201_CREATED,
)
def create_knowledge(c: ContainerDep, company_id: uuid.UUID, body: KnowledgeCreate) -> KnowledgeOut:
    with c.tx() as s:
        get_active_company(s, company_id)
        return KnowledgeOut.model_validate(kn.create_note(s, company_id, body))


@router.get("/knowledge/{item_id}", response_model=KnowledgeOut)
def get_knowledge(c: ContainerDep, item_id: uuid.UUID) -> KnowledgeOut:
    with c.tx() as s:
        return KnowledgeOut.model_validate(kn.get_item(s, item_id))


@router.patch("/knowledge/{item_id}", response_model=KnowledgeOut)
def update_knowledge(c: ContainerDep, item_id: uuid.UUID, body: KnowledgeUpdate) -> KnowledgeOut:
    with c.tx() as s:
        return KnowledgeOut.model_validate(kn.update_item(s, item_id, body))


@router.post("/knowledge/{item_id}/archive", response_model=KnowledgeOut)
def archive_knowledge(c: ContainerDep, item_id: uuid.UUID) -> KnowledgeOut:
    with c.tx() as s:
        return KnowledgeOut.model_validate(kn.archive_item(s, item_id))


@router.post(
    "/artifacts/{artifact_id}/to-knowledge",
    response_model=KnowledgeOut,
    status_code=status.HTTP_201_CREATED,
)
def artifact_to_knowledge(
    c: ContainerDep, artifact_id: uuid.UUID, body: ImportArtifact
) -> KnowledgeOut:
    with c.tx() as s:
        art = ex.get_artifact(s, artifact_id)
        data = ex.read_artifact(art, c.settings.artifacts_dir)
        if len(data) > MAX_CONTENT:
            raise DomainValidationError("Artifact is too large for the knowledge base")
        return KnowledgeOut.model_validate(
            kn.import_artifact(s, art, data.decode("utf-8", errors="replace"), body.title)
        )


@router.post(
    "/tasks/{task_id}/summarize", response_model=KnowledgeOut, status_code=status.HTTP_201_CREATED
)
def summarize_task(c: ContainerDep, task_id: uuid.UUID) -> KnowledgeOut:
    with c.tx() as s:
        return KnowledgeOut.model_validate(kn.summarize_task(s, task_id))


# ----- lessons -----


@router.get("/companies/{company_id}/lessons", response_model=list[LessonOut])
def list_lessons(c: ContainerDep, company_id: uuid.UUID) -> list[LessonOut]:
    with c.tx() as s:
        get_company(s, company_id)
        return [LessonOut.model_validate(x) for x in kn.list_lessons(s, company_id)]


@router.post(
    "/companies/{company_id}/lessons", response_model=LessonOut, status_code=status.HTTP_201_CREATED
)
def propose_lesson(c: ContainerDep, company_id: uuid.UUID, body: LessonCreate) -> LessonOut:
    with c.tx() as s:
        get_active_company(s, company_id)
        return LessonOut.model_validate(kn.propose_lesson(s, company_id, body, proposed_by="user"))


@router.post("/lessons/{lesson_id}/review", response_model=LessonOut)
def review_lesson(c: ContainerDep, lesson_id: uuid.UUID, body: Review) -> LessonOut:
    with c.tx() as s:
        return LessonOut.model_validate(kn.review_lesson(s, lesson_id, body))


# ----- role-change proposals -----


@router.get("/companies/{company_id}/role-proposals", response_model=list[RoleProposalOut])
def list_role_proposals(c: ContainerDep, company_id: uuid.UUID) -> list[RoleProposalOut]:
    with c.tx() as s:
        get_company(s, company_id)
        return [RoleProposalOut.model_validate(p) for p in kn.list_role_proposals(s, company_id)]


@router.post(
    "/companies/{company_id}/role-proposals",
    response_model=RoleProposalOut,
    status_code=status.HTTP_201_CREATED,
)
def propose_role_change(
    c: ContainerDep, company_id: uuid.UUID, body: RoleProposalCreate
) -> RoleProposalOut:
    with c.tx() as s:
        get_active_company(s, company_id)
        return RoleProposalOut.model_validate(
            kn.propose_role_change(s, company_id, body, proposed_by="user")
        )


@router.post("/role-proposals/{proposal_id}/review", response_model=RoleProposalOut)
def review_role_change(c: ContainerDep, proposal_id: uuid.UUID, body: Review) -> RoleProposalOut:
    with c.tx() as s:
        return RoleProposalOut.model_validate(
            kn.review_role_change(s, proposal_id, body, c.extras["registry"].ids())
        )
