"""Worker management for the UI (token-protected like the rest of /api, ADR-0009)."""

from __future__ import annotations

import uuid
from datetime import datetime, timedelta

from fastapi import APIRouter
from pydantic import BaseModel, Field

from orchestra_backend.api.deps import ContainerDep
from orchestra_backend.core.errors import ErrorResponse
from orchestra_backend.core.time import utcnow
from orchestra_backend.workers import service as wsvc
from orchestra_backend.workers.hub import WorkerHub
from orchestra_backend.workers.models import Worker

router = APIRouter(tags=["workers"], responses={404: {"model": ErrorResponse}})


class PairingCreate(BaseModel):
    name: str = Field(default="Worker", min_length=1, max_length=100)


class PairingOut(BaseModel):
    code: str
    expires_at: datetime
    command: str


class WorkerOut(BaseModel):
    id: uuid.UUID
    name: str
    status: str
    online: bool
    hostname: str
    platform: str
    version: str
    runtimes: list[str]
    last_seen_at: datetime | None
    created_at: datetime
    revoked_at: datetime | None
    active_leases: int


def _hub(c: ContainerDep) -> WorkerHub:
    return c.extras["workers"]


def _out(w: Worker, hub: WorkerHub, ttl: float, counts: dict[uuid.UUID, int]) -> WorkerOut:
    online = (
        w.status == "active"
        and w.last_seen_at is not None
        and utcnow() - w.last_seen_at < timedelta(seconds=max(60.0, 2 * ttl))
    )
    return WorkerOut(
        id=w.id,
        name=w.name,
        status=w.status,
        online=online,
        hostname=w.hostname,
        platform=w.platform,
        version=w.version,
        runtimes=list(w.runtimes_json or []),
        last_seen_at=w.last_seen_at,
        created_at=w.created_at,
        revoked_at=w.revoked_at,
        active_leases=counts.get(w.id, 0),
    )


@router.get("/workers", response_model=list[WorkerOut])
def list_workers(c: ContainerDep) -> list[WorkerOut]:
    hub = _hub(c)
    counts = hub.live_counts()
    ttl = c.settings.worker_lease_ttl_s
    with c.tx() as s:
        return [_out(w, hub, ttl, counts) for w in wsvc.list_workers(s)]


@router.post("/workers/pairing-codes", response_model=PairingOut, status_code=201)
def create_pairing(body: PairingCreate, c: ContainerDep) -> PairingOut:
    """One-time code, shown once. The worker exchanges it for its own identity."""
    with c.tx() as s:
        code, exp = wsvc.create_pairing(s, body.name, c.settings.worker_pairing_ttl_s)
    return PairingOut(code=code, expires_at=exp, command=f"pnpm worker pair {code}")


@router.post("/workers/{worker_id}/revoke", response_model=WorkerOut)
async def revoke_worker(worker_id: uuid.UUID, c: ContainerDep) -> WorkerOut:
    hub = _hub(c)
    w = c.run_tx(lambda s: wsvc.revoke(s, worker_id))
    await hub.revoke_worker(worker_id)
    with c.tx() as s:
        return _out(wsvc.get_worker(s, w.id), hub, c.settings.worker_lease_ttl_s, hub.live_counts())
