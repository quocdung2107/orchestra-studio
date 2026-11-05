from __future__ import annotations

from fastapi import APIRouter
from fastapi.testclient import TestClient
from sqlalchemy import text

from orchestra_backend.core.config import LOOPBACK_HOST, Settings
from orchestra_backend.db import migrate
from orchestra_backend.db.session import make_engine
from tests.conftest import BASE_URL, TOKEN


def test_health_is_public(anon_client: TestClient) -> None:
    r = anon_client.get("/api/v1/health")
    assert r.status_code == 200
    assert r.json()["status"] == "ok"
    assert r.json()["database"] == "ok"


def test_loopback_only() -> None:
    assert LOOPBACK_HOST == "127.0.0.1"


def test_token_required(anon_client: TestClient) -> None:
    r = anon_client.get("/api/v1/companies")
    assert r.status_code == 401
    assert r.json()["error"]["code"] == "unauthorized"


def test_wrong_token_rejected(anon_client: TestClient) -> None:
    r = anon_client.get("/api/v1/companies", headers={"X-Orchestra-Token": "nope"})
    assert r.status_code == 401


def test_foreign_host_rejected(app) -> None:
    with TestClient(app, base_url="http://evil.example:8765") as c:
        r = c.get("/api/v1/health", headers={"X-Orchestra-Token": TOKEN})
    assert r.status_code == 403
    assert r.json()["error"]["code"] == "forbidden_host"


def test_foreign_origin_rejected(client: TestClient) -> None:
    r = client.get("/api/v1/companies", headers={"Origin": "https://evil.example"})
    assert r.status_code == 403
    assert r.json()["error"]["code"] == "forbidden_origin"


def test_dev_origin_allowed(client: TestClient) -> None:
    r = client.get("/api/v1/companies", headers={"Origin": "http://localhost:5173"})
    assert r.status_code == 200


def test_token_file_written(client: TestClient, settings: Settings) -> None:
    assert settings.token_file.read_text(encoding="utf-8") == TOKEN


def test_generated_token_when_unset(tmp_path) -> None:
    s = Settings(data_dir=tmp_path)
    assert len(s.api_token) >= 32
    assert s.api_token == s.api_token  # stable for the process


def test_structured_404(client: TestClient) -> None:
    r = client.get("/api/v1/companies/00000000-0000-0000-0000-000000000000")
    assert r.status_code == 404
    assert r.json()["error"]["code"] == "not_found"


def test_structured_validation_error(client: TestClient) -> None:
    r = client.post("/api/v1/companies", json={"name": ""})
    assert r.status_code == 422
    body = r.json()["error"]
    assert body["code"] == "validation_error"
    assert isinstance(body["details"], list)


def test_unhandled_error_does_not_leak(app) -> None:
    router = APIRouter()

    @router.get("/api/v1/boom")
    def boom() -> None:
        raise RuntimeError("secret=sk-live-123")

    app.include_router(router)
    with TestClient(
        app, base_url=BASE_URL, headers={"X-Orchestra-Token": TOKEN}, raise_server_exceptions=False
    ) as c:
        r = c.get("/api/v1/boom")
    assert r.status_code == 500
    assert "sk-live" not in r.text
    assert r.json()["error"]["code"] == "internal_error"


def test_migrations_up_down_up(tmp_path) -> None:
    url = f"sqlite:///{(tmp_path / 'm.db').as_posix()}"
    migrate.upgrade(url)
    migrate.downgrade(url, "base")
    migrate.upgrade(url)
    engine = make_engine(url)
    with engine.connect() as conn:
        assert conn.execute(text("PRAGMA foreign_keys")).scalar() == 1
        tables = {r[0] for r in conn.execute(text("SELECT name FROM sqlite_master"))}
    assert {"companies", "events", "event_streams"} <= tables
    engine.dispose()


def test_openapi_available(client: TestClient) -> None:
    r = client.get("/openapi.json")
    assert r.status_code == 200
    assert "/api/v1/companies" in r.json()["paths"]
