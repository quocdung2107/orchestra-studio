"""Approval records bound to an exact payload checksum (ADR-0018, SECURITY §8)."""

from __future__ import annotations

import hashlib
import json
import uuid
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from orchestra_backend.approvals.models import Approval
from orchestra_backend.approvals.schemas import ApprovalDecision
from orchestra_backend.core.errors import DomainValidationError, InvalidStateError, NotFoundError
from orchestra_backend.core.time import utcnow
from orchestra_backend.events.catalog import ApprovalClosed, ApprovalRequested
from orchestra_backend.events.service import append_event

SOURCE = "approvals"


def canonical_checksum(payload: dict[str, Any]) -> str:
    raw = json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return "sha256:" + hashlib.sha256(raw.encode("utf-8")).hexdigest()


def create(
    session: Session,
    *,
    company_id: uuid.UUID,
    run_id: uuid.UUID,
    task_id: uuid.UUID | None,
    agent_id: uuid.UUID,
    tool_id: uuid.UUID,
    action_type: str,
    request: dict[str, Any],
    required_level: int,
    correlation_id: uuid.UUID | None,
) -> Approval:
    a = Approval(
        company_id=company_id,
        run_id=run_id,
        task_id=task_id,
        requested_by_agent_id=agent_id,
        tool_id=tool_id,
        action_type=action_type,
        request_json=request,
        checksum=canonical_checksum(request),
        required_level=required_level,
    )
    session.add(a)
    session.flush()
    append_event(
        session,
        company_id=company_id,
        event_type="approval.requested",
        source=SOURCE,
        run_id=run_id,
        correlation_id=correlation_id,
        payload=ApprovalRequested(
            approval_id=a.id,
            run_id=run_id,
            task_id=task_id,
            action_type=action_type,
            checksum=a.checksum,
            required_level=required_level,
        ),
    )
    return a


def get(session: Session, approval_id: uuid.UUID) -> Approval:
    a = session.get(Approval, approval_id)
    if a is None:
        raise NotFoundError("Approval not found")
    return a


def list_for_company(
    session: Session, company_id: uuid.UUID, status: str | None = None
) -> list[Approval]:
    stmt = select(Approval).where(Approval.company_id == company_id)
    if status:
        stmt = stmt.where(Approval.status == status)
    return list(session.scalars(stmt.order_by(Approval.created_at.desc()).limit(200)))


def decide(session: Session, approval_id: uuid.UUID, data: ApprovalDecision) -> Approval:
    """Human decision. Only from `pending`; checksum must match the stored payload."""
    a = get(session, approval_id)
    if a.status != "pending":
        raise InvalidStateError(f"Approval is already {a.status}", code="approval_closed")
    if data.checksum != a.checksum or canonical_checksum(a.request_json) != a.checksum:
        raise DomainValidationError(
            "Checksum does not match the requested action", code="checksum_mismatch"
        )
    a.status = "approved" if data.decision == "approve" else "rejected"
    a.decided_by = "user"
    a.decision_note = data.note or None
    a.decided_at = utcnow()
    append_event(
        session,
        company_id=a.company_id,
        event_type="approval.decided",
        source="api.approvals",
        run_id=a.run_id,
        payload=ApprovalClosed(approval_id=a.id, status=a.status, decided_by="user"),
    )
    return a


def close(session: Session, a: Approval, status: str, source: str = SOURCE) -> None:
    """System closure: cancelled (run cancelled) or expired (backend restart)."""
    if a.status != "pending":
        return
    a.status = status
    a.decided_at = utcnow()
    a.decided_by = "system"
    append_event(
        session,
        company_id=a.company_id,
        event_type="approval.closed",
        source=source,
        run_id=a.run_id,
        payload=ApprovalClosed(approval_id=a.id, status=status, decided_by="system"),
    )


def pending_for_run(session: Session, run_id: uuid.UUID) -> list[Approval]:
    return list(
        session.scalars(
            select(Approval).where(Approval.run_id == run_id, Approval.status == "pending")
        )
    )


def expire_all_pending(session: Session) -> int:
    rows = list(session.scalars(select(Approval).where(Approval.status == "pending")))
    for a in rows:
        close(session, a, "expired", source="orchestrator.recovery")
    return len(rows)
