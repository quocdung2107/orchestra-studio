from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from orchestra_backend.events.models import Event


class EventOut(BaseModel):
    """Versioned event envelope (EVENTS.md §2)."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    company_id: uuid.UUID
    run_id: uuid.UUID | None
    sequence: int
    event_type: str
    schema_version: int
    occurred_at: datetime
    source: str
    correlation_id: uuid.UUID | None
    causation_id: uuid.UUID | None
    idempotency_key: str | None
    payload: dict[str, Any] = Field(validation_alias="payload_json")


class EventPage(BaseModel):
    items: list[EventOut]
    next_after: int


def to_out(ev: Event) -> EventOut:
    return EventOut.model_validate(ev)
