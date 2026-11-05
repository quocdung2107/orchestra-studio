from __future__ import annotations

import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import APIRouter, FastAPI
from fastapi.staticfiles import StaticFiles

from orchestra_backend import __version__
from orchestra_backend.api import agents, companies, events, execution, health, stream
from orchestra_backend.api.deps import Container
from orchestra_backend.core.config import Settings
from orchestra_backend.core.errors import install_error_handlers
from orchestra_backend.core.security import LocalSecurityMiddleware
from orchestra_backend.db import migrate
from orchestra_backend.db.session import make_engine, make_session_factory
from orchestra_backend.orchestrator.service import Orchestrator
from orchestra_backend.runtime.mock.runtime import MockRuntime
from orchestra_backend.runtime.registry import RuntimeRegistry

log = logging.getLogger(__name__)


def _write_token_file(settings: Settings) -> None:
    settings.data_dir.mkdir(parents=True, exist_ok=True)
    settings.token_file.write_text(settings.api_token, encoding="utf-8")


def create_app(settings: Settings | None = None) -> FastAPI:
    settings = settings or Settings()
    settings.data_dir.mkdir(parents=True, exist_ok=True)

    if settings.run_migrations_on_startup:
        migrate.upgrade(settings.resolved_database_url)

    engine = make_engine(settings.resolved_database_url)
    container = Container(
        settings=settings, engine=engine, session_factory=make_session_factory(engine)
    )

    registry = RuntimeRegistry()
    registry.register(MockRuntime(step_delay_ms=settings.mock_step_delay_ms))
    orchestrator = Orchestrator(container, registry)
    container.extras.update(registry=registry, orchestrator=orchestrator)

    @asynccontextmanager
    async def lifespan(_: FastAPI) -> AsyncIterator[None]:
        _write_token_file(settings)
        await orchestrator.recover()
        yield
        await orchestrator.shutdown()
        engine.dispose()

    app = FastAPI(title="Orchestra Studio API", version=__version__, lifespan=lifespan)
    app.state.container = container
    install_error_handlers(app)
    app.add_middleware(LocalSecurityMiddleware, settings=settings)

    api = APIRouter(prefix="/api/v1")
    api.include_router(health.router)
    api.include_router(companies.router)
    api.include_router(events.router)
    api.include_router(stream.router)
    api.include_router(agents.router)
    api.include_router(execution.router)
    app.include_router(api)

    if settings.static_dir and settings.static_dir.is_dir():
        app.mount("/", StaticFiles(directory=settings.static_dir, html=True), name="renderer")

    return app
