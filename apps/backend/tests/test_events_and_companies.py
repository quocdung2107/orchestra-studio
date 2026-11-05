from __future__ import annotations

import uuid

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import text
from sqlalchemy.exc import DBAPIError

from orchestra_backend.core.errors import DomainValidationError
from orchestra_backend.events.models import AppendOnlyViolation, Event
from orchestra_backend.events.service import append_event


def _events(client: TestClient, company_id: str, after: int = 0) -> list[dict]:
    r = client.get(f"/api/v1/companies/{company_id}/events", params={"after": after})
    assert r.status_code == 200
    return r.json()["items"]


def test_company_crud_emits_events(client: TestClient, company: dict) -> None:
    cid = company["id"]
    assert client.get(f"/api/v1/companies/{cid}").json()["name"] == "Acme"

    r = client.patch(f"/api/v1/companies/{cid}", json={"description": "AI studio"})
    assert r.status_code == 200 and r.json()["description"] == "AI studio"

    r = client.post(f"/api/v1/companies/{cid}/archive")
    assert r.json()["status"] == "archived"
    assert client.get("/api/v1/companies").json() == []
    assert len(client.get("/api/v1/companies", params={"include_archived": True}).json()) == 1

    evs = _events(client, cid)
    assert [e["event_type"] for e in evs] == [
        "company.created",
        "company.updated",
        "company.archived",
    ]
    assert [e["sequence"] for e in evs] == [1, 2, 3]
    assert evs[1]["payload"] == {"changes": {"description": "AI studio"}}
    assert evs[0]["schema_version"] == 1
    assert evs[0]["occurred_at"].endswith("Z") or "+00:00" in evs[0]["occurred_at"]


def test_archived_company_rejects_update(client: TestClient, company: dict) -> None:
    client.post(f"/api/v1/companies/{company['id']}/archive")
    r = client.patch(f"/api/v1/companies/{company['id']}", json={"name": "X"})
    assert r.status_code == 409
    assert r.json()["error"]["code"] == "invalid_state"


def test_blank_name_rejected(client: TestClient) -> None:
    assert client.post("/api/v1/companies", json={"name": "   "}).status_code == 422
    assert client.post("/api/v1/companies", json={"name": "a", "x": 1}).status_code == 422


def test_sequences_are_per_company(client: TestClient) -> None:
    a = client.post("/api/v1/companies", json={"name": "A"}).json()
    b = client.post("/api/v1/companies", json={"name": "B"}).json()
    client.patch(f"/api/v1/companies/{a['id']}", json={"name": "A2"})
    assert [e["sequence"] for e in _events(client, a["id"])] == [1, 2]
    assert [e["sequence"] for e in _events(client, b["id"])] == [1]
    assert _events(client, a["id"], after=1)[0]["event_type"] == "company.updated"


def test_unknown_event_type_rejected(container, company: dict) -> None:
    with pytest.raises(DomainValidationError), container.tx() as s:
        append_event(
            s, company_id=uuid.UUID(company["id"]), event_type="made.up", payload={}, source="test"
        )


def test_invalid_payload_rejected(container, company: dict) -> None:
    with pytest.raises(DomainValidationError), container.tx() as s:
        append_event(
            s,
            company_id=uuid.UUID(company["id"]),
            event_type="company.created",
            payload={"name": "x", "extra": 1},
            source="test",
        )


def test_idempotency_key(container, company: dict) -> None:
    cid = uuid.UUID(company["id"])
    with container.tx() as s:
        e1 = append_event(
            s,
            company_id=cid,
            event_type="company.archived",
            payload={},
            source="t",
            idempotency_key="k1",
        )
        e2 = append_event(
            s,
            company_id=cid,
            event_type="company.archived",
            payload={},
            source="t",
            idempotency_key="k1",
        )
        assert e1.id == e2.id


def test_events_append_only_orm(container, company: dict) -> None:
    with pytest.raises(AppendOnlyViolation), container.tx() as s:
        ev = s.query(Event).first()
        ev.source = "tampered"
        s.flush()


def test_events_append_only_db_trigger(container, company: dict) -> None:
    with pytest.raises(DBAPIError), container.tx() as s:
        s.execute(text("UPDATE events SET source = 'x'"))
    with pytest.raises(DBAPIError), container.tx() as s:
        s.execute(text("DELETE FROM events"))


def test_events_survive_restart(settings, company: dict) -> None:
    from orchestra_backend.app import create_app
    from tests.conftest import BASE_URL, TOKEN

    app2 = create_app(settings)
    with TestClient(app2, base_url=BASE_URL, headers={"X-Orchestra-Token": TOKEN}) as c:
        assert _events(c, company["id"])[0]["event_type"] == "company.created"
