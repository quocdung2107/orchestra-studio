"""Settings. Values come from ORCHESTRA_* environment variables."""

from __future__ import annotations

import secrets
from functools import cached_property
from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

# apps/backend/src/orchestra_backend/core/config.py -> repo root is parents[5]
_REPO_ROOT = Path(__file__).resolve().parents[5]

LOOPBACK_HOST = "127.0.0.1"  # ADR-0009: never bind to other interfaces


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="ORCHESTRA_", extra="ignore")

    port: int = 8765
    data_dir: Path = Field(default=_REPO_ROOT / "data")
    database_url: str | None = None
    # When unset, a random token is generated per process start (ADR-0009).
    token: str | None = None
    # Extra browser origins allowed to call the API (e.g. the Vite dev server).
    dev_origins: list[str] = Field(
        default_factory=lambda: ["http://localhost:5173", "http://127.0.0.1:5173"]
    )
    templates_dir: Path = Field(default=_REPO_ROOT / "templates")
    # Directory with the built renderer (served at / when present).
    static_dir: Path | None = None
    run_migrations_on_startup: bool = True
    # Mock runtime pacing; tests set 0 for instant, deterministic progression.
    mock_step_delay_ms: int = 400
    # Base delay for automatic retries; doubles per attempt (ADR-0016).
    retry_backoff_ms: int = 1000
    # Where secrets live (ADR-0021): "keyring" (OS store) or "memory" (tests/dev only).
    secret_store: str = "keyring"  # noqa: S105 - store kind, not a secret
    # Local model server (ADR-0024).
    ollama_url: str = "http://127.0.0.1:11434"
    ollama_max_concurrency: int = Field(default=1, ge=1, le=8)
    # Network timeout (seconds) for one model call.
    model_timeout_s: float = 300.0
    # Workers (ADR-0025).
    worker_lease_ttl_s: float = Field(default=30.0, gt=0)
    worker_token_ttl_s: float = Field(default=900.0, gt=0)
    worker_pairing_ttl_s: float = Field(default=900.0, gt=0)
    worker_dispatch_timeout_s: float = Field(default=300.0, gt=0)
    worker_poll_max_s: float = Field(default=25.0, ge=0)
    # Media production (ADR-0028..0033).
    ffmpeg: str = "ffmpeg"  # executable name in PATH or full path
    ffprobe: str = "ffprobe"
    media_max_parallel: int = Field(default=1, ge=1, le=8)
    media_cpu_slots: int = Field(default=1, ge=1, le=16)
    # RAM gate (ADR-0029). Reserve kept for OS + backend + UI; render estimate measured
    # 2026-11-06 as ~620-880 MB peak RSS for 1080x1920 libx264 (bench R1/R2).
    media_memory_gate: bool = True
    media_ram_reserve_mb: int = Field(default=256, ge=0, le=8192)
    render_est_ram_mb: int = Field(default=900, ge=0, le=16384)
    media_poll_s: float = Field(default=1.0, gt=0)
    job_lease_s: float = Field(default=120.0, gt=0)
    engine_keep_warm_s: float = Field(default=0.0, ge=0)
    engine_start_timeout_s: float = Field(default=180.0, gt=0)
    render_timeout_s: float = Field(default=3600.0, gt=0)
    # Disable the background media runner (tests drive it explicitly).
    media_runner_enabled: bool = True

    @cached_property
    def api_token(self) -> str:
        return self.token or secrets.token_urlsafe(32)

    @property
    def resolved_database_url(self) -> str:
        if self.database_url:
            return self.database_url
        return f"sqlite:///{(self.data_dir / 'orchestra.db').as_posix()}"

    @property
    def token_file(self) -> Path:
        return self.data_dir / "backend-token"

    @property
    def artifacts_dir(self) -> Path:
        return self.data_dir / "artifacts"

    @property
    def media_dir(self) -> Path:
        return self.data_dir / "media"

    @property
    def render_work_dir(self) -> Path:
        return self.data_dir / "render-work"

    @property
    def workspaces_dir(self) -> Path:
        return self.data_dir / "workspaces"

    @property
    def allowed_hosts(self) -> set[str]:
        return {f"127.0.0.1:{self.port}", f"localhost:{self.port}"}

    @property
    def allowed_origins(self) -> set[str]:
        own = {f"http://127.0.0.1:{self.port}", f"http://localhost:{self.port}"}
        return own | set(self.dev_origins)
