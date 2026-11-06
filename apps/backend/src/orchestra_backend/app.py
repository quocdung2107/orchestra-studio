from __future__ import annotations

import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import APIRouter, FastAPI
from fastapi.staticfiles import StaticFiles

from orchestra_backend import __version__
from orchestra_backend.api import (
    agents,
    approvals,
    backups,
    capabilities,
    companies,
    credentials,
    events,
    execution,
    health,
    knowledge,
    media,
    metrics,
    organization,
    production,
    stream,
    templates,
    worker_protocol,
    workers,
)
from orchestra_backend.api.deps import Container
from orchestra_backend.core.config import Settings
from orchestra_backend.core.errors import install_error_handlers
from orchestra_backend.core.redact import install_log_redaction
from orchestra_backend.core.security import LocalSecurityMiddleware
from orchestra_backend.credentials.store import make_store
from orchestra_backend.db import migrate
from orchestra_backend.db.session import make_engine, make_session_factory
from orchestra_backend.jobs.engines import EngineManager, load_config
from orchestra_backend.jobs.runner import JobRunner
from orchestra_backend.jobs.scheduler import ResourceScheduler
from orchestra_backend.media.store import MediaStore
from orchestra_backend.media_gateway import audio
from orchestra_backend.orchestrator.service import Orchestrator
from orchestra_backend.production.handlers import register_all
from orchestra_backend.render import probe
from orchestra_backend.runtime.llm.anthropic_rt import AnthropicRuntime
from orchestra_backend.runtime.llm.ollama_rt import OllamaRuntime
from orchestra_backend.runtime.llm.openai_rt import OpenAIRuntime
from orchestra_backend.runtime.mock.runtime import MockRuntime
from orchestra_backend.runtime.registry import RuntimeRegistry
from orchestra_backend.runtime.worker_rt import WorkerRuntime
from orchestra_backend.workers.hub import WorkerHub

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

    install_log_redaction()
    secrets = make_store(settings.secret_store)
    registry = RuntimeRegistry()
    registry.register(MockRuntime(step_delay_ms=settings.mock_step_delay_ms))
    registry.register(
        OllamaRuntime(
            base_url=settings.ollama_url,
            max_concurrency=settings.ollama_max_concurrency,
            timeout_s=settings.model_timeout_s,
        )
    )
    registry.register(AnthropicRuntime(timeout_s=settings.model_timeout_s))
    registry.register(OpenAIRuntime(timeout_s=settings.model_timeout_s))
    hub = WorkerHub(container)
    registry.register(
        WorkerRuntime(hub, {"mock": registry.get("mock"), "ollama": registry.get("ollama")})
    )
    orchestrator = Orchestrator(container, registry, secrets)
    container.extras.update(
        registry=registry, orchestrator=orchestrator, secrets=secrets, workers=hub
    )

    # Media production (ADR-0028..0033).
    audio.configure(settings.ffmpeg)
    probe.configure(settings.ffprobe)
    engines = EngineManager(
        load_config(settings.data_dir / "engines.json"),
        log_dir=settings.data_dir / "logs" / "engines",
        keep_warm_s=settings.engine_keep_warm_s,
        start_timeout_s=settings.engine_start_timeout_s,
    )
    scheduler = ResourceScheduler(
        max_parallel=settings.media_max_parallel,
        cpu_slots=settings.media_cpu_slots,
        engines=engines,
        ram_reserve_mb=settings.media_ram_reserve_mb,
        memory_gate=settings.media_memory_gate,
    )
    job_runner = JobRunner(
        container, scheduler, engines, lease_s=settings.job_lease_s, poll_s=settings.media_poll_s
    )
    register_all(job_runner)
    container.extras.update(
        media_store=MediaStore(settings.media_dir),
        engines=engines,
        scheduler=scheduler,
        job_runner=job_runner,
    )

    @asynccontextmanager
    async def lifespan(_: FastAPI) -> AsyncIterator[None]:
        _write_token_file(settings)
        await orchestrator.recover()
        await hub.start()
        if settings.media_runner_enabled:
            await job_runner.start()
        else:
            job_runner.recover()
        yield
        await job_runner.stop()
        await orchestrator.shutdown()
        await hub.stop()
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
    api.include_router(organization.router)
    api.include_router(capabilities.router)
    api.include_router(credentials.router)
    api.include_router(metrics.router)
    api.include_router(backups.router)
    api.include_router(workers.router)
    api.include_router(worker_protocol.router)
    api.include_router(templates.router)
    api.include_router(approvals.router)
    api.include_router(knowledge.router)
    api.include_router(media.router)
    api.include_router(production.router)
    app.include_router(api)

    if settings.static_dir and settings.static_dir.is_dir():
        app.mount("/", StaticFiles(directory=settings.static_dir, html=True), name="renderer")

    return app
