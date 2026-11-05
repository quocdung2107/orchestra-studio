"""Endpoints a worker process calls (ADR-0025). Not covered by the UI token; each call is
authenticated with the worker's own short-lived bearer token (pairing/token calls by code/secret).
Host checks of ADR-0009 still apply."""

from __future__ import annotations

import uuid
from typing import Annotated, Any

from fastapi import APIRouter, Depends, Header, Query, Response
from pydantic import BaseModel, Field

from orchestra_backend import __version__
from orchestra_backend.api.deps import ContainerDep
from orchestra_backend.core.errors import ErrorResponse
from orchestra_backend.workers import service as wsvc
from orchestra_backend.workers.hub import WorkerHub
from orchestra_backend.workers.models import Worker

PREFIX = "/worker"
router = APIRouter(
    prefix=PREFIX,
    tags=["worker-protocol"],
    responses={
        401: {"model": ErrorResponse},
        403: {"model": ErrorResponse},
        409: {"model": ErrorResponse},
    },
)


class EnrollIn(BaseModel):
    code: str = Field(min_length=4, max_length=40)
    hostname: str = Field(default="", max_length=200)
    platform: str = Field(default="", max_length=100)
    version: str = Field(default="", max_length=40)
    runtimes: list[str] = Field(default_factory=lambda: list(wsvc.WORKER_RUNTIMES), max_length=10)


class EnrollOut(BaseModel):
    worker_id: uuid.UUID
    worker_secret: str
    name: str
    server_version: str


class TokenIn(BaseModel):
    worker_id: uuid.UUID
    worker_secret: str = Field(min_length=1, max_length=200)


class TokenOut(BaseModel):
    access_token: str
    expires_in: float


class EventsIn(BaseModel):
    seq: int = Field(ge=1)
    events: list[dict[str, Any]] = Field(min_length=1, max_length=100)


class ToolCallIn(BaseModel):
    key: str = Field(min_length=1, max_length=100)
    params: dict[str, Any] = Field(default_factory=dict)


class Ack(BaseModel):
    ok: bool = True
    lease_ttl_s: float


def _hub(c: ContainerDep) -> WorkerHub:
    return c.extras["workers"]


def current_worker(c: ContainerDep, authorization: Annotated[str, Header()] = "") -> Worker:
    scheme, _, token = authorization.partition(" ")
    if scheme.lower() != "bearer" or not token:
        raise wsvc.WorkerAuthError("Thiếu token worker", code="WORKER_TOKEN_INVALID")
    with c.tx() as s:
        w = wsvc.authenticate(s, token.strip())
        s.flush()  # persist last_seen_at before detaching the object
        s.expunge(w)
    return w


WorkerDep = Annotated[Worker, Depends(current_worker)]


@router.post("/enroll", response_model=EnrollOut, status_code=201)
def enroll(body: EnrollIn, c: ContainerDep) -> EnrollOut:
    with c.tx() as s:
        e = wsvc.enroll(
            s,
            body.code,
            hostname=body.hostname,
            platform=body.platform,
            version=body.version,
            runtimes=body.runtimes,
        )
        return EnrollOut(
            worker_id=e.worker.id,
            worker_secret=e.secret,
            name=e.worker.name,
            server_version=__version__,
        )


@router.post("/token", response_model=TokenOut)
def token(body: TokenIn, c: ContainerDep) -> TokenOut:
    with c.tx() as s:
        tok, ttl = wsvc.issue_token(
            s, body.worker_id, body.worker_secret, c.settings.worker_token_ttl_s
        )
    return TokenOut(access_token=tok, expires_in=ttl)


@router.get("/lease", responses={204: {"description": "Không có việc"}})
async def next_lease(
    w: WorkerDep, c: ContainerDep, wait: Annotated[float, Query(ge=0, le=60)] = 20
) -> Any:
    lease = await _hub(c).claim(w.id, list(w.runtimes_json or []), wait)
    if lease is None:
        return Response(status_code=204)
    return lease


@router.post("/leases/{lease_id}/heartbeat", response_model=Ack)
async def heartbeat(lease_id: uuid.UUID, w: WorkerDep, c: ContainerDep) -> Ack:
    return Ack(lease_ttl_s=_hub(c).heartbeat(w.id, lease_id))


@router.post("/leases/{lease_id}/events", response_model=Ack)
async def post_events(lease_id: uuid.UUID, body: EventsIn, w: WorkerDep, c: ContainerDep) -> Ack:
    hub = _hub(c)
    await hub.post_events(w.id, lease_id, body.seq, body.events)
    return Ack(lease_ttl_s=hub.lease_ttl)


@router.post("/leases/{lease_id}/tool-calls")
async def tool_call(
    lease_id: uuid.UUID, body: ToolCallIn, w: WorkerDep, c: ContainerDep
) -> dict[str, Any]:
    return await _hub(c).tool_call(w.id, lease_id, body.key, body.params)
