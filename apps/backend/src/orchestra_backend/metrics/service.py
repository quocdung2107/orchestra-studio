"""Usage/cost metrics and KPIs, every number labelled with source and confidence (ADR-0023)."""

from __future__ import annotations

import uuid
from collections import defaultdict
from datetime import timedelta
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from orchestra_backend.agents.models import Agent
from orchestra_backend.core.time import utcnow
from orchestra_backend.events.catalog import RunUsageRecorded
from orchestra_backend.events.service import append_event
from orchestra_backend.execution.models import AgentRun
from orchestra_backend.metrics.models import Metric
from orchestra_backend.metrics.pricing import PriceTable
from orchestra_backend.runtime.normalize import Usage

LOCAL_PROVIDERS = {"ollama"}


def record_usage(s: Session, run: AgentRun, u: Usage, prices: PriceTable) -> None:
    agent = s.get(Agent, run.agent_id)
    dims: dict[str, Any] = dict(
        company_id=run.company_id,
        agent_id=run.agent_id,
        department_id=agent.department_id if agent else None,
        task_id=run.task_id,
        run_id=run.id,
    )
    meta = {"provider": u.provider, "model": u.model, "runtime_id": run.runtime_id}
    usage_conf = "reported"

    cost: float | None
    cost_source: str | None
    if u.provider in LOCAL_PROVIDERS:
        cost, cost_source, cost_conf = 0.0, "local_no_api_fee", "measured"
        cost_meta = {**meta, "note": "no API fee; electricity/hardware not counted"}
    else:
        cost = prices.cost_usd(u.model, u.input_tokens, u.output_tokens)
        cost_source = "price_table_estimate" if cost is not None else None
        cost_conf = "estimated"
        cost_meta = {**meta, "price_as_of": prices.as_of, "price_source": prices.source}

    ev = append_event(
        s,
        company_id=run.company_id,
        event_type="agent.run.usage_recorded",
        source="orchestrator",
        run_id=run.id,
        payload=RunUsageRecorded(
            run_id=run.id,
            provider=u.provider,
            model=u.model,
            input_tokens=u.input_tokens,
            output_tokens=u.output_tokens,
            token_source=u.source,
            cost_usd=cost,
            cost_source=cost_source,
            price_as_of=prices.as_of if cost_source == "price_table_estimate" else None,
        ),
    )
    rows = [
        ("tokens_input", float(u.input_tokens), "tokens", u.source, usage_conf, meta),
        ("tokens_output", float(u.output_tokens), "tokens", u.source, usage_conf, meta),
        ("model_calls", 1.0, "count", "orchestrator", "measured", meta),
    ]
    if u.duration_ms is not None:
        rows.append(("model_latency_ms", float(u.duration_ms), "ms", u.source, usage_conf, meta))
    if cost is not None and cost_source is not None:
        rows.append(("cost_usd", cost, "usd", cost_source, cost_conf, cost_meta))
    for name, value, unit, source, conf, md in rows:
        s.add(
            Metric(
                **dims,
                metric_name=name,
                metric_value=value,
                unit=unit,
                source=source,
                confidence=conf,
                metadata_json=md,
                source_event_id=ev.id,
            )
        )
    # Keep a running total on the run for the inspector.
    total = dict(run.usage_json or {})
    total["input_tokens"] = total.get("input_tokens", 0) + u.input_tokens
    total["output_tokens"] = total.get("output_tokens", 0) + u.output_tokens
    total["model_calls"] = total.get("model_calls", 0) + 1
    total["model"] = u.model
    total["provider"] = u.provider
    if cost is not None:
        total["cost_usd"] = round(total.get("cost_usd", 0.0) + cost, 6)
        total["cost_source"] = cost_source
    else:
        total["cost_unpriced"] = True
    run.usage_json = total
    s.flush()


# ---------------- KPIs ----------------

SOURCES = {
    "runs": {
        "source": "orchestrator",
        "confidence": "measured",
        "note": "Đếm từ bản ghi run trong cơ sở dữ liệu",
    },
    "duration": {
        "source": "orchestrator",
        "confidence": "measured",
        "note": "Từ lúc run bắt đầu đến lúc kết thúc, gồm thời gian chờ duyệt",
    },
    "tokens": {
        "source": "provider_reported | local_runtime_reported",
        "confidence": "reported",
        "note": "Số token do provider hoặc Ollama báo về",
    },
    "cost": {
        "source": "price_table_estimate | local_no_api_fee",
        "confidence": "estimated",
        "note": "Token × bảng giá có ngày; model không có giá thì không tính",
    },
}


def _bucket() -> dict[str, Any]:
    return {
        "runs": 0,
        "completed": 0,
        "failed": 0,
        "cancelled": 0,
        "active": 0,
        "retries": 0,
        "duration_ms_total": 0.0,
        "duration_n": 0,
        "tokens_input": 0,
        "tokens_output": 0,
        "model_calls": 0,
        "cost_usd": 0.0,
        "llm_runs": set(),
        "priced_runs": set(),
    }


def _finish(b: dict[str, Any]) -> dict[str, Any]:
    done = b["completed"] + b["failed"] + b["cancelled"]
    llm, priced = len(b["llm_runs"]), len(b["priced_runs"])
    return {
        "runs": b["runs"],
        "completed": b["completed"],
        "failed": b["failed"],
        "cancelled": b["cancelled"],
        "active": b["active"],
        "retries": b["retries"],
        "success_rate": round(b["completed"] / done, 4) if done else None,
        "avg_duration_ms": round(b["duration_ms_total"] / b["duration_n"])
        if b["duration_n"]
        else None,
        "tokens_input": b["tokens_input"],
        "tokens_output": b["tokens_output"],
        "model_calls": b["model_calls"],
        "cost_usd": round(b["cost_usd"], 6),
        "llm_runs": llm,
        "priced_runs": priced,
        "unpriced_runs": llm - priced,
    }


def kpis(s: Session, company_id: uuid.UUID, days: int) -> dict[str, Any]:
    since = utcnow() - timedelta(days=days)
    agents = {a.id: a for a in s.scalars(select(Agent).where(Agent.company_id == company_id))}
    total = _bucket()
    by_agent: dict[uuid.UUID, dict[str, Any]] = defaultdict(_bucket)
    by_runtime: dict[str, dict[str, Any]] = defaultdict(_bucket)
    run_runtime: dict[uuid.UUID, str] = {}

    runs = s.scalars(
        select(AgentRun).where(AgentRun.company_id == company_id, AgentRun.created_at >= since)
    )
    for r in runs:
        run_runtime[r.id] = r.runtime_id
        for b in (total, by_agent[r.agent_id], by_runtime[r.runtime_id]):
            b["runs"] += 1
            if r.status in ("completed", "failed", "cancelled"):
                b[r.status] += 1
            else:
                b["active"] += 1
            if r.attempt > 1:
                b["retries"] += 1
            if r.started_at and r.finished_at:
                b["duration_ms_total"] += (r.finished_at - r.started_at).total_seconds() * 1000
                b["duration_n"] += 1

    metrics = s.scalars(
        select(Metric).where(Metric.company_id == company_id, Metric.recorded_at >= since)
    )
    for m in metrics:
        rt = run_runtime.get(m.run_id) if m.run_id else None
        targets = [total]
        if m.agent_id is not None:
            targets.append(by_agent[m.agent_id])
        if rt is not None:
            targets.append(by_runtime[rt])
        for b in targets:
            if m.metric_name in ("tokens_input", "tokens_output", "model_calls"):
                b[m.metric_name] += int(m.metric_value)
                if m.metric_name == "model_calls" and m.run_id:
                    b["llm_runs"].add(m.run_id)
            elif m.metric_name == "cost_usd":
                b["cost_usd"] += m.metric_value
                if m.run_id:
                    b["priced_runs"].add(m.run_id)

    return {
        "company_id": company_id,
        "days": days,
        "since": since,
        "generated_at": utcnow(),
        "totals": _finish(total),
        "by_agent": sorted(
            (
                {
                    "agent_id": aid,
                    "agent_name": agents[aid].name if aid in agents else "?",
                    "role": agents[aid].role if aid in agents else "",
                    **_finish(b),
                }
                for aid, b in by_agent.items()
            ),
            key=lambda x: (-x["runs"], x["agent_name"]),
        ),
        "by_runtime": sorted(
            ({"runtime_id": rid, **_finish(b)} for rid, b in by_runtime.items()),
            key=lambda x: x["runtime_id"],
        ),
        "sources": SOURCES,
    }
