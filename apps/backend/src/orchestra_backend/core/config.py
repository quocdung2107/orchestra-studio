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
    def workspaces_dir(self) -> Path:
        return self.data_dir / "workspaces"

    @property
    def allowed_hosts(self) -> set[str]:
        return {f"127.0.0.1:{self.port}", f"localhost:{self.port}"}

    @property
    def allowed_origins(self) -> set[str]:
        own = {f"http://127.0.0.1:{self.port}", f"http://localhost:{self.port}"}
        return own | set(self.dev_origins)
