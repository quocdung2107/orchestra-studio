from __future__ import annotations

import uuid

from fastapi import APIRouter, Query

from orchestra_backend.api.deps import ContainerDep
from orchestra_backend.companies.service import get_company
from orchestra_backend.core.errors import ErrorResponse
from orchestra_backend.events.schemas import EventPage, to_out
from orchestra_backend.events.service import list_events

router = APIRouter(tags=["events"], responses={404: {"model": ErrorResponse}})


@router.get("/companies/{company_id}/events", response_model=EventPage)
def query_events(
    c: ContainerDep,
    company_id: uuid.UUID,
    after: int = Query(default=0, ge=0),
    limit: int = Query(default=200, ge=1, le=1000),
    run_id: uuid.UUID | None = None,
) -> EventPage:
    with c.tx() as s:
        get_company(s, company_id)
        rows = list_events(s, company_id, after=after, limit=limit, run_id=run_id)
        items = [to_out(e) for e in rows]
    return EventPage(items=items, next_after=items[-1].sequence if items else after)
