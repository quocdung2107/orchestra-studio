from __future__ import annotations

from fastapi import APIRouter
from pydantic import BaseModel
from sqlalchemy import text

from orchestra_backend import __version__
from orchestra_backend.api.deps import ContainerDep

router = APIRouter(tags=["system"])


class Health(BaseModel):
    status: str
    version: str
    database: str


@router.get("/health", response_model=Health)
def health(c: ContainerDep) -> Health:
    try:
        with c.session_factory() as s:
            s.execute(text("SELECT 1"))
        db = "ok"
    except Exception:  # noqa: BLE001 - health must report, not raise
        db = "error"
    return Health(status="ok" if db == "ok" else "degraded", version=__version__, database=db)
