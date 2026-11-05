from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from orchestra_backend.app import create_app
from orchestra_backend.core.config import Settings

TOKEN = "test-token"
BASE_URL = "http://127.0.0.1:8765"


@pytest.fixture
def settings(tmp_path: Path) -> Settings:
    return Settings(data_dir=tmp_path / "data", token=TOKEN, port=8765, mock_step_delay_ms=0)


@pytest.fixture
def app(settings: Settings):
    return create_app(settings)


@pytest.fixture
def client(app) -> Iterator[TestClient]:
    with TestClient(app, base_url=BASE_URL, headers={"X-Orchestra-Token": TOKEN}) as c:
        yield c


@pytest.fixture
def anon_client(app) -> Iterator[TestClient]:
    with TestClient(app, base_url=BASE_URL) as c:
        yield c


@pytest.fixture
def container(app):
    return app.state.container


@pytest.fixture
def company(client: TestClient) -> dict:
    r = client.post("/api/v1/companies", json={"name": "Acme"})
    assert r.status_code == 201, r.text
    return r.json()
