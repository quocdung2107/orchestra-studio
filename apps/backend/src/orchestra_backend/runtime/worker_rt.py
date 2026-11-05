"""Runtime adapter that runs an agent on a paired worker process (ADR-0025).

Settings: {"runtime": "mock"|"ollama", "worker_id": optional pin, "settings": {...inner}}.
The adapter holds no state; leases live in the WorkerHub.
"""

from __future__ import annotations

import uuid
from collections.abc import AsyncIterator
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, ValidationError

from orchestra_backend.core.errors import DomainValidationError
from orchestra_backend.runtime.interface import RunRequest, RuntimeCapabilities, RuntimeEvent
from orchestra_backend.workers.hub import WorkerHub


class WorkerSettings(BaseModel):
    model_config = ConfigDict(extra="forbid")

    runtime: Literal["mock", "ollama"] = "mock"
    worker_id: uuid.UUID | None = None
    settings: dict[str, Any] = {}


class WorkerRuntime:
    runtime_id = "worker"
    display_name = "Worker (tiến trình riêng)"
    provider = None
    requires_credential = False
    capabilities = RuntimeCapabilities(supports_cancel=True, supports_tool_calls=True)
    settings_model = WorkerSettings

    def __init__(self, hub: WorkerHub, inner: dict[str, Any]) -> None:
        self.hub = hub
        self._inner = inner  # runtime_id -> local runtime instance (for settings validation)

    def validate_settings(self, settings: dict[str, Any]) -> dict[str, Any]:
        try:
            ws = WorkerSettings.model_validate(settings)
        except ValidationError as exc:
            raise DomainValidationError(
                "Invalid settings for runtime 'worker'",
                code="invalid_runtime_settings",
                details=[
                    {"loc": list(e["loc"]), "msg": e["msg"]} for e in exc.errors(include_url=False)
                ],
            ) from exc
        inner = self._inner.get(ws.runtime)
        validate = getattr(inner, "validate_settings", None)
        ws.settings = validate(ws.settings) if validate else ws.settings
        return ws.model_dump(mode="json", exclude_none=True)

    def execute(self, request: RunRequest) -> AsyncIterator[RuntimeEvent]:
        ws = WorkerSettings.model_validate(request.settings)
        return self.hub.dispatch(request, ws.runtime, ws.settings, ws.worker_id)

    def cancel(self, run_id: uuid.UUID) -> None:
        self.hub.cancel(run_id)

    async def health_check(self) -> dict[str, Any]:
        return {"status": "ok"}
