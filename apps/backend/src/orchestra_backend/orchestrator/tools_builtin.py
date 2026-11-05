"""Built-in tool executors behind the Tool Gateway (ADR-0018).

Each executor runs inside the gateway's transaction. They never touch the network.
"""

from __future__ import annotations

import json
import re
import uuid
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path, PurePosixPath
from typing import Any

from sqlalchemy.orm import Session

from orchestra_backend.capabilities.models import Tool
from orchestra_backend.core.config import Settings
from orchestra_backend.execution import service as ex
from orchestra_backend.execution.models import AgentRun, Task
from orchestra_backend.knowledge import service as kn

MAX_WRITE_BYTES = 1_000_000


class ToolError(Exception):
    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code
        self.message = message


@dataclass
class ToolContext:
    session: Session
    settings: Settings
    run: AgentRun
    tool: Tool
    correlation_id: uuid.UUID | None

    def root_task(self) -> Task:
        task = ex.get_task(self.session, self.run.task_id)  # type: ignore[arg-type]
        while task.parent_task_id is not None:
            task = ex.get_task(self.session, task.parent_task_id)
        return task


Executor = Callable[[ToolContext, dict[str, Any]], dict[str, Any]]


# ---------- input validation (subset of JSON Schema; no extra dependency) ----------

_TYPES: dict[str, tuple[type, ...]] = {
    "string": (str,),
    "integer": (int,),
    "number": (int, float),
    "boolean": (bool,),
    "object": (dict,),
    "array": (list,),
}


def validate_input(schema: dict[str, Any], params: dict[str, Any]) -> str | None:
    """Return an error message or None. Supports type/properties/required/maxLength."""
    if not isinstance(params, dict):
        return "params must be an object"
    for key in schema.get("required", []):
        if key not in params:
            return f"missing required field '{key}'"
    props: dict[str, Any] = schema.get("properties", {})
    for key, value in params.items():
        spec = props.get(key)
        if spec is None:
            if schema.get("additionalProperties") is False:
                return f"unknown field '{key}'"
            continue
        t = spec.get("type")
        if t in _TYPES:
            ok = isinstance(value, _TYPES[t]) and not (t == "integer" and isinstance(value, bool))
            if not ok:
                return f"field '{key}' must be {t}"
        if isinstance(value, str) and "maxLength" in spec and len(value) > spec["maxLength"]:
            return f"field '{key}' is too long"
    return None


# ---------- executors ----------


def kb_search(ctx: ToolContext, params: dict[str, Any]) -> dict[str, Any]:
    q = str(params.get("query", ""))
    limit = int(params.get("limit", 5)) if str(params.get("limit", "5")).isdigit() else 5
    res = kn.search(ctx.session, ctx.run.company_id, q, limit=max(1, min(limit, 20)))
    return {
        "engine": res.engine,
        "results": [
            {"id": str(h.id), "title": h.title, "source_type": h.source_type, "snippet": h.snippet}
            for h in res.hits
        ],
    }


def _slug(s: str) -> str:
    s = re.sub(r"[^\w\-. ]+", "", s, flags=re.UNICODE).strip() or "draft"
    return s[:80]


def doc_draft(ctx: ToolContext, params: dict[str, Any]) -> dict[str, Any]:
    title = str(params.get("title") or "Bản nháp")
    body = str(params.get("body") or params.get("content") or "")
    if len(body.encode("utf-8")) > MAX_WRITE_BYTES:
        raise ToolError("TOOL_LIMIT_EXCEEDED", "Draft is larger than 1 MB")
    art = ex.store_artifact(
        ctx.session,
        ctx.run,
        name=f"{_slug(title)}.md",
        mime_type="text/markdown",
        content=f"# {title}\n\n{body}\n",
        artifacts_dir=ctx.settings.artifacts_dir,
        correlation_id=ctx.correlation_id,
    )
    return {"artifact_id": str(art.id), "name": art.name}


def safe_workspace_path(root: Path, rel: str, allowed_prefixes: list[str]) -> Path:
    """Resolve `rel` inside `root`; reject absolute paths, '..', and paths outside the allowlist."""
    if not rel or "\\" in rel or "\x00" in rel:
        raise ToolError("TOOL_PATH_DENIED", "Path must be a non-empty POSIX relative path")
    p = PurePosixPath(rel)
    if p.is_absolute() or any(part in {"..", ""} for part in p.parts) or ":" in p.parts[0]:
        raise ToolError("TOOL_PATH_DENIED", "Path must stay inside the workspace")
    if allowed_prefixes and not any(
        rel == pre.rstrip("/") or rel.startswith(pre.rstrip("/") + "/") for pre in allowed_prefixes
    ):
        raise ToolError("TOOL_PATH_DENIED", f"Path not in allowed paths {allowed_prefixes}")
    root = root.resolve()
    target = (root / Path(*p.parts)).resolve()
    if not target.is_relative_to(root):
        raise ToolError("TOOL_PATH_DENIED", "Path escapes the workspace")
    return target


def workspace_write(ctx: ToolContext, params: dict[str, Any]) -> dict[str, Any]:
    rel = str(params.get("path", ""))
    content = str(params.get("content", ""))
    data = content.encode("utf-8")
    if len(data) > MAX_WRITE_BYTES:
        raise ToolError("TOOL_LIMIT_EXCEEDED", "File is larger than 1 MB")
    root = ctx.settings.workspaces_dir / str(ctx.run.company_id) / str(ctx.root_task().id)
    root.mkdir(parents=True, exist_ok=True)
    target = safe_workspace_path(root, rel, list(ctx.tool.policy_json.get("allowed_paths", [])))
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_bytes(data)
    return {"path": rel, "bytes": len(data), "workspace": str(ctx.root_task().id)}


def social_publish(ctx: ToolContext, params: dict[str, Any]) -> dict[str, Any]:
    """Simulated external action: records an outbox entry, never calls the network."""
    record = {
        "simulated": True,
        "channel": params.get("channel", "default"),
        "text": params.get("text", ""),
        "note": "Mô phỏng P2: không gửi ra ngoài. Kết nối thật ở P4/P5.",
    }
    art = ex.store_artifact(
        ctx.session,
        ctx.run,
        name=f"outbox-{_slug(str(record['channel']))}.json",
        mime_type="application/json",
        content=json.dumps(record, ensure_ascii=False, indent=2),
        artifacts_dir=ctx.settings.artifacts_dir,
        correlation_id=ctx.correlation_id,
    )
    return {"simulated": True, "post_id": f"sim-{art.id}", "artifact_id": str(art.id)}


EXECUTORS: dict[str, Executor] = {
    "kb.search": kb_search,
    "doc.draft": doc_draft,
    "workspace.write": workspace_write,
    "social.publish": social_publish,
}
