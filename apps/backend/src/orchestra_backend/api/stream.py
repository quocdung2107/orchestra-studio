"""SSE event stream (EVENTS.md §4, ADR-0006): reads committed events by sequence."""

from __future__ import annotations

import asyncio
import json
import time
import uuid
from collections.abc import AsyncIterator

from fastapi import APIRouter, Header, Query, Request
from fastapi.responses import StreamingResponse

from orchestra_backend.api.deps import Container, ContainerDep
from orchestra_backend.companies.service import get_company
from orchestra_backend.core.errors import ErrorResponse
from orchestra_backend.events.schemas import to_out
from orchestra_backend.events.service import list_events

router = APIRouter(tags=["events"], responses={404: {"model": ErrorResponse}})

POLL_SECONDS = 0.3
HEARTBEAT_SECONDS = 15.0
BATCH = 500


def format_sse(sequence: int, data: str) -> str:
    return f"id: {sequence}\nevent: event\ndata: {data}\n\n"


def _fetch(c: Container, company_id: uuid.UUID, after: int) -> list[tuple[int, str]]:
    with c.tx() as s:
        rows = list_events(s, company_id, after=after, limit=BATCH)
        return [
            (e.sequence, json.dumps(to_out(e).model_dump(mode="json"), ensure_ascii=False))
            for e in rows
        ]


async def event_source(
    request: Request, c: Container, company_id: uuid.UUID, after: int, until_idle: bool
) -> AsyncIterator[str]:
    yield "retry: 2000\n\n"
    last_beat = time.monotonic()
    while True:
        if await request.is_disconnected():
            return
        batch = await asyncio.to_thread(_fetch, c, company_id, after)
        for seq, data in batch:
            after = seq
            yield format_sse(seq, data)
        if not batch:
            if until_idle:
                return
            if time.monotonic() - last_beat > HEARTBEAT_SECONDS:
                last_beat = time.monotonic()
                yield ": heartbeat\n\n"
            await asyncio.sleep(POLL_SECONDS)


@router.get(
    "/companies/{company_id}/events/stream",
    response_class=StreamingResponse,
    responses={200: {"content": {"text/event-stream": {}}}},
)
def stream_events(
    request: Request,
    c: ContainerDep,
    company_id: uuid.UUID,
    after: int | None = Query(default=None, ge=0),
    until_idle: bool = Query(default=False, description="Close when caught up (tests/debug)"),
    last_event_id: str | None = Header(default=None),
) -> StreamingResponse:
    with c.tx() as s:
        get_company(s, company_id)
    start = after
    if start is None and last_event_id and last_event_id.isdigit():
        start = int(last_event_id)  # reconnect resume (EventSource sends Last-Event-ID)
    return StreamingResponse(
        event_source(request, c, company_id, start or 0, until_idle),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )
