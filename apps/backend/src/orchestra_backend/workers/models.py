"""Workers (ADR-0025). Only hashes of worker secrets, pairing codes and tokens are stored."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import JSON, ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column

from orchestra_backend.db.base import Base, IdMixin, TimestampMixin


class Worker(IdMixin, TimestampMixin, Base):
    __tablename__ = "workers"

    name: Mapped[str] = mapped_column(String(100))
    status: Mapped[str] = mapped_column(String(20), default="active")  # active | revoked
    secret_hash: Mapped[str] = mapped_column(String(64))
    hostname: Mapped[str] = mapped_column(String(200), default="")
    platform: Mapped[str] = mapped_column(String(100), default="")
    version: Mapped[str] = mapped_column(String(40), default="")
    runtimes_json: Mapped[list[Any]] = mapped_column(JSON, default=list)
    last_seen_at: Mapped[datetime | None] = mapped_column(default=None)
    revoked_at: Mapped[datetime | None] = mapped_column(default=None)


class WorkerPairing(IdMixin, TimestampMixin, Base):
    """One-time pairing code, valid for a short time."""

    __tablename__ = "worker_pairings"

    code_hash: Mapped[str] = mapped_column(String(64), unique=True)
    name: Mapped[str] = mapped_column(String(100))
    expires_at: Mapped[datetime]
    used_at: Mapped[datetime | None] = mapped_column(default=None)
    worker_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("workers.id"), default=None)


class WorkerToken(IdMixin, TimestampMixin, Base):
    __tablename__ = "worker_tokens"

    worker_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("workers.id"), index=True)
    token_hash: Mapped[str] = mapped_column(String(64), unique=True)
    expires_at: Mapped[datetime]


class WorkerLease(IdMixin, TimestampMixin, Base):
    """One attempt of a run handed to a worker. Live state is in the hub; this is the record."""

    __tablename__ = "worker_leases"

    run_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("agent_runs.id"), index=True)
    worker_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("workers.id"), default=None)
    pinned_worker_id: Mapped[uuid.UUID | None] = mapped_column(default=None)
    runtime_id: Mapped[str] = mapped_column(String(50))
    # pending | active | finished | cancelled | lost | revoked | unavailable
    status: Mapped[str] = mapped_column(String(20), default="pending")
    last_seq: Mapped[int] = mapped_column(default=0)
    claimed_at: Mapped[datetime | None] = mapped_column(default=None)
    finished_at: Mapped[datetime | None] = mapped_column(default=None)
    error_code: Mapped[str | None] = mapped_column(String(50), default=None)
