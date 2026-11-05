from __future__ import annotations

from datetime import datetime

from fastapi import APIRouter
from pydantic import BaseModel

from orchestra_backend.api.deps import ContainerDep
from orchestra_backend.backup import service as backup
from orchestra_backend.core.errors import ErrorResponse

router = APIRouter(tags=["backups"], responses={409: {"model": ErrorResponse}})


class BackupOut(BaseModel):
    name: str
    size_bytes: int
    created_at: datetime
    files: int | None
    app_version: str | None


class BackupList(BaseModel):
    directory: str
    items: list[BackupOut]
    restore_command: str


def _out(b: backup.BackupInfo) -> BackupOut:
    return BackupOut(**b.__dict__)


@router.get("/backups", response_model=BackupList)
def list_backups(c: ContainerDep) -> BackupList:
    s = c.settings
    return BackupList(
        directory=str(backup.backups_dir(s)),
        items=[_out(b) for b in backup.list_backups(s)],
        restore_command="pnpm restore <tên file>",
    )


@router.post("/backups", response_model=BackupOut, status_code=201)
def create_backup(c: ContainerDep) -> BackupOut:
    """Snapshot the database, artifacts and workspaces into one zip (no secrets)."""
    return _out(backup.create_backup(c.settings))
