"""Local backend protection (ADR-0009).

- Host header must be loopback with our port (blocks DNS rebinding).
- Origin, when present, must be in the allow-list (blocks cross-site requests).
- Every /api/ request except health must carry the per-launch token. Worker protocol calls
  (/api/v1/worker/...) instead carry a per-worker bearer token, checked by their routes.
"""

from __future__ import annotations

import hmac

from starlette.types import ASGIApp, Receive, Scope, Send

from orchestra_backend.core.config import Settings
from orchestra_backend.core.errors import error_json

TOKEN_HEADER = "x-orchestra-token"  # noqa: S105 - header name, not a secret
PUBLIC_PATHS = {"/api/v1/health"}
# Worker protocol: own bearer auth per worker (ADR-0025), not the UI token.
WORKER_PREFIX = "/api/v1/worker/"


class LocalSecurityMiddleware:
    def __init__(self, app: ASGIApp, settings: Settings):
        self.app = app
        self.settings = settings

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        headers = {k.decode("latin-1"): v.decode("latin-1") for k, v in scope["headers"]}
        host = headers.get("host", "")
        if host not in self.settings.allowed_hosts:
            await error_json(403, "forbidden_host", "Host not allowed")(scope, receive, send)
            return

        origin = headers.get("origin")
        if origin is not None and origin not in self.settings.allowed_origins:
            await error_json(403, "forbidden_origin", "Origin not allowed")(scope, receive, send)
            return

        path: str = scope["path"]
        if (
            path.startswith("/api/")
            and path not in PUBLIC_PATHS
            and not path.startswith(WORKER_PREFIX)
        ):
            supplied = headers.get(TOKEN_HEADER, "")
            if not hmac.compare_digest(supplied.encode(), self.settings.api_token.encode()):
                await error_json(401, "unauthorized", "Missing or invalid token")(
                    scope, receive, send
                )
                return

        await self.app(scope, receive, send)
