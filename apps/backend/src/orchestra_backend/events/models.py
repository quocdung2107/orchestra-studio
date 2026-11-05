from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import ForeignKey, Index, String, UniqueConstraint, event
from sqlalchemy.orm import Mapped, mapped_column

from orchestra_backend.core.time import utcnow
from orchestra_backend.db.base import Base, IdMixin


class EventStream(Base):
    """Per-company sequence counter (ADR-0007). Only the backend assigns sequences."""

    __tablename__ = "event_streams"

    company_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("companies.id"), primary_key=True)
    last_sequence: Mapped[int] = mapped_column(default=0)


class Event(IdMixin, Base):
    __tablename__ = "events"
    __table_args__ = (
        UniqueConstraint("company_id", "sequence", name="uq_events_company_sequence"),
        UniqueConstraint("company_id", "idempotency_key", name="uq_events_company_idempotency"),
        Index("ix_events_run_sequence", "run_id", "sequence"),
    )

    company_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("companies.id"))
    run_id: Mapped[uuid.UUID | None] = mapped_column(default=None)
    sequence: Mapped[int]
    event_type: Mapped[str] = mapped_column(String(100))
    schema_version: Mapped[int] = mapped_column(default=1)
    occurred_at: Mapped[datetime] = mapped_column(default=utcnow)
    source: Mapped[str] = mapped_column(String(100))
    correlation_id: Mapped[uuid.UUID | None] = mapped_column(default=None)
    causation_id: Mapped[uuid.UUID | None] = mapped_column(default=None)
    idempotency_key: Mapped[str | None] = mapped_column(String(200), default=None)
    payload_json: Mapped[dict[str, Any]]


class AppendOnlyViolation(RuntimeError):
    pass


@event.listens_for(Event, "before_update")
def _no_update(*_: Any) -> None:
    raise AppendOnlyViolation("events are append-only")


@event.listens_for(Event, "before_delete")
def _no_delete(*_: Any) -> None:
    raise AppendOnlyViolation("events are append-only")
