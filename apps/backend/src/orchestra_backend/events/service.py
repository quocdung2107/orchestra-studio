from __future__ import annotations

import uuid
from typing import Any

from pydantic import BaseModel, ValidationError
from sqlalchemy import select, update
from sqlalchemy.orm import Session

from orchestra_backend.core.errors import DomainValidationError
from orchestra_backend.events.catalog import CATALOG, SCHEMA_VERSION
from orchestra_backend.events.models import Event, EventStream


def _next_sequence(session: Session, company_id: uuid.UUID) -> int:
    # Atomic increment; portable to PostgreSQL (row lock) and SQLite (write lock).
    result = session.execute(
        update(EventStream)
        .where(EventStream.company_id == company_id)
        .values(last_sequence=EventStream.last_sequence + 1)
        .returning(EventStream.last_sequence)
    ).scalar_one_or_none()
    if result is not None:
        return result
    session.add(EventStream(company_id=company_id, last_sequence=1))
    session.flush()
    return 1


def append_event(
    session: Session,
    *,
    company_id: uuid.UUID,
    event_type: str,
    payload: BaseModel | dict[str, Any],
    source: str,
    run_id: uuid.UUID | None = None,
    correlation_id: uuid.UUID | None = None,
    causation_id: uuid.UUID | None = None,
    idempotency_key: str | None = None,
) -> Event:
    """Validate and append one event inside the caller's transaction (ADR-0006)."""
    schema = CATALOG.get(event_type)
    if schema is None:
        raise DomainValidationError(f"Unknown event type: {event_type}", code="unknown_event_type")
    try:
        raw = payload.model_dump(mode="json") if isinstance(payload, BaseModel) else payload
        validated = schema.model_validate(raw)
    except ValidationError as exc:
        raise DomainValidationError(
            f"Invalid payload for {event_type}",
            code="invalid_event_payload",
            details=exc.errors(include_url=False, include_context=False),
        ) from exc

    if idempotency_key is not None:
        existing = session.scalar(
            select(Event).where(
                Event.company_id == company_id, Event.idempotency_key == idempotency_key
            )
        )
        if existing is not None:
            return existing

    ev = Event(
        company_id=company_id,
        run_id=run_id,
        sequence=_next_sequence(session, company_id),
        event_type=event_type,
        schema_version=SCHEMA_VERSION,
        source=source,
        correlation_id=correlation_id,
        causation_id=causation_id,
        idempotency_key=idempotency_key,
        payload_json=validated.model_dump(mode="json"),
    )
    session.add(ev)
    session.flush()
    return ev


def list_events(
    session: Session,
    company_id: uuid.UUID,
    *,
    after: int = 0,
    limit: int = 200,
    run_id: uuid.UUID | None = None,
) -> list[Event]:
    stmt = (
        select(Event)
        .where(Event.company_id == company_id, Event.sequence > after)
        .order_by(Event.sequence)
        .limit(limit)
    )
    if run_id is not None:
        stmt = stmt.where(Event.run_id == run_id)
    return list(session.scalars(stmt))
