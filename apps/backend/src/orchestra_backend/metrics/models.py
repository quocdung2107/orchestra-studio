from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import ForeignKey, Index, String
from sqlalchemy.orm import Mapped, mapped_column

from orchestra_backend.core.time import utcnow
from orchestra_backend.db.base import Base, IdMixin

SOURCES = (
    "provider_reported",
    "local_runtime_reported",
    "price_table_estimate",
    "local_no_api_fee",
    "orchestrator",
)
CONFIDENCE = ("measured", "reported", "estimated")


class Metric(IdMixin, Base):
    """One measured/reported/estimated number with its provenance (ADR-0023)."""

    __tablename__ = "metrics"
    __table_args__ = (
        Index("ix_metrics_company_recorded", "company_id", "recorded_at"),
        Index("ix_metrics_run", "run_id"),
    )

    company_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("companies.id"))
    agent_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("agents.id"), default=None)
    department_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("departments.id"), default=None
    )
    task_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("tasks.id"), default=None)
    run_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("agent_runs.id"), default=None)
    metric_name: Mapped[str] = mapped_column(String(60))
    metric_value: Mapped[float]
    unit: Mapped[str] = mapped_column(String(20))
    source: Mapped[str] = mapped_column(String(40))
    confidence: Mapped[str] = mapped_column(String(20))
    metadata_json: Mapped[dict[str, Any]] = mapped_column(default=dict)
    source_event_id: Mapped[uuid.UUID | None] = mapped_column(default=None)
    recorded_at: Mapped[datetime] = mapped_column(default=utcnow)
