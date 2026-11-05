from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from fastapi import APIRouter, Query
from pydantic import BaseModel

from orchestra_backend.api.deps import ContainerDep
from orchestra_backend.companies.service import get_company
from orchestra_backend.core.errors import ErrorResponse
from orchestra_backend.metrics import service as metrics
from orchestra_backend.metrics.pricing import load as load_prices

router = APIRouter(tags=["metrics"], responses={404: {"model": ErrorResponse}})


class KpiFigures(BaseModel):
    runs: int
    completed: int
    failed: int
    cancelled: int
    active: int
    retries: int
    success_rate: float | None
    avg_duration_ms: int | None
    tokens_input: int
    tokens_output: int
    model_calls: int
    cost_usd: float
    llm_runs: int
    priced_runs: int
    unpriced_runs: int


class AgentKpi(KpiFigures):
    agent_id: uuid.UUID
    agent_name: str
    role: str


class RuntimeKpi(KpiFigures):
    runtime_id: str


class SourceLabel(BaseModel):
    source: str
    confidence: str
    note: str


class KpiReport(BaseModel):
    company_id: uuid.UUID
    days: int
    since: datetime
    generated_at: datetime
    totals: KpiFigures
    by_agent: list[AgentKpi]
    by_runtime: list[RuntimeKpi]
    sources: dict[str, SourceLabel]
    price_table: dict[str, Any]


@router.get("/companies/{company_id}/kpis", response_model=KpiReport)
def company_kpis(
    c: ContainerDep, company_id: uuid.UUID, days: int = Query(default=30, ge=1, le=365)
) -> KpiReport:
    prices = load_prices()
    with c.tx() as s:
        get_company(s, company_id)
        data = metrics.kpis(s, company_id, days)
    return KpiReport(
        **data,
        price_table={
            "as_of": prices.as_of,
            "source": prices.source,
            "models": sorted(prices.models),
        },
    )
