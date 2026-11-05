from __future__ import annotations

import asyncio
import uuid

from fastapi import APIRouter

from orchestra_backend.api.deps import ContainerDep
from orchestra_backend.approvals import service as approvals
from orchestra_backend.approvals.schemas import ApprovalDecision, ApprovalOut, ApprovalStatus
from orchestra_backend.companies.service import get_company
from orchestra_backend.core.errors import ErrorResponse

router = APIRouter(
    tags=["approvals"],
    responses={
        404: {"model": ErrorResponse},
        409: {"model": ErrorResponse},
        422: {"model": ErrorResponse},
    },
)


@router.get("/companies/{company_id}/approvals", response_model=list[ApprovalOut])
def list_approvals(
    c: ContainerDep, company_id: uuid.UUID, status: ApprovalStatus | None = None
) -> list[ApprovalOut]:
    with c.tx() as s:
        get_company(s, company_id)
        return [
            ApprovalOut.model_validate(a) for a in approvals.list_for_company(s, company_id, status)
        ]


@router.get("/approvals/{approval_id}", response_model=ApprovalOut)
def get_approval(c: ContainerDep, approval_id: uuid.UUID) -> ApprovalOut:
    with c.tx() as s:
        return ApprovalOut.model_validate(approvals.get(s, approval_id))


@router.post("/approvals/{approval_id}/decide", response_model=ApprovalOut)
async def decide(c: ContainerDep, approval_id: uuid.UUID, body: ApprovalDecision) -> ApprovalOut:
    """Human decision only (the app token). Binds to the shown checksum (ADR-0018)."""
    out = await asyncio.to_thread(
        c.run_tx, lambda s: ApprovalOut.model_validate(approvals.decide(s, approval_id, body))
    )
    c.orchestrator.gateway.approval_closed(approval_id, out.status)
    return out
