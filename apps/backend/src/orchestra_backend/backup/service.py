"""Backup and restore of local data (ADR-0027).

A backup is one zip in `data/backups/`:
  orchestra.db            consistent copy via SQLite's online backup API
  artifacts/**, workspaces/**
  manifest.json           format, time, versions, SHA-256 of every file
Secrets are never included: they live in the OS store (ADR-0021); the token file is skipped.
Restore runs only while the app is stopped (CLI), keeps the current data in
`data/pre-restore-<time>/`, and refuses archives whose checksums or paths are wrong.
"""

from __future__ import annotations

import hashlib
import json
import shutil
import socket
import sqlite3
import tempfile
import threading
import zipfile
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path, PurePosixPath

from orchestra_backend import __version__
from orchestra_backend.core.config import LOOPBACK_HOST, Settings
from orchestra_backend.core.errors import AppError, ConflictError, NotFoundError

FORMAT = 1
DB_NAME = "orchestra.db"
MANIFEST = "manifest.json"
TREES = ("artifacts", "workspaces")
_lock = threading.Lock()


class BackupInvalid(AppError):
    status_code = 422
    code = "BACKUP_INVALID"


@dataclass
class BackupInfo:
    name: str
    size_bytes: int
    created_at: datetime
    files: int | None
    app_version: str | None


def backups_dir(settings: Settings) -> Path:
    return settings.data_dir / "backups"


def _db_path(settings: Settings) -> Path:
    url = settings.resolved_database_url
    if not url.startswith("sqlite:///"):
        raise ConflictError(
            "Chỉ sao lưu được cơ sở dữ liệu SQLite cục bộ", code="BACKUP_UNSUPPORTED"
        )
    return Path(url.removeprefix("sqlite:///"))


def _sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def _alembic_revision(db: Path) -> str | None:
    con = sqlite3.connect(db)
    try:
        row = con.execute("SELECT version_num FROM alembic_version").fetchone()
        return row[0] if row else None
    except sqlite3.Error:
        return None
    finally:
        con.close()


def create_backup(settings: Settings) -> BackupInfo:
    if not _lock.acquire(blocking=False):
        raise ConflictError("Đang có một bản sao lưu khác chạy", code="BACKUP_BUSY")
    try:
        return _create(settings)
    finally:
        _lock.release()


def _create(settings: Settings) -> BackupInfo:
    src_db = _db_path(settings)
    out_dir = backups_dir(settings)
    out_dir.mkdir(parents=True, exist_ok=True)
    now = datetime.now(UTC)
    name = f"orchestra-backup-{now:%Y%m%d-%H%M%S-%f}.zip"
    with tempfile.TemporaryDirectory(dir=out_dir) as tmp:
        snap = Path(tmp) / DB_NAME
        src = sqlite3.connect(src_db)
        dst = sqlite3.connect(snap)
        try:
            src.backup(dst)
        finally:
            dst.close()
            src.close()
        files: dict[str, Path] = {DB_NAME: snap}
        for tree in TREES:
            root = settings.data_dir / tree
            if root.is_dir():
                for p in sorted(root.rglob("*")):
                    if p.is_file() and not p.is_symlink():
                        files[f"{tree}/{p.relative_to(root).as_posix()}"] = p
        manifest = {
            "format": FORMAT,
            "created_at": now.isoformat(),
            "app_version": __version__,
            "schema_revision": _alembic_revision(snap),
            "files": {
                arc: {"sha256": _sha256(p), "size": p.stat().st_size} for arc, p in files.items()
            },
        }
        part = Path(tmp) / (name + ".part")
        with zipfile.ZipFile(part, "w", compression=zipfile.ZIP_DEFLATED) as z:
            z.writestr(MANIFEST, json.dumps(manifest, ensure_ascii=False, indent=2))
            for arc, p in files.items():
                z.write(p, arc)
        final = out_dir / name
        part.replace(final)
    return _info(final, manifest)


def _info(path: Path, manifest: dict | None) -> BackupInfo:
    st = path.stat()
    created = datetime.fromtimestamp(st.st_mtime, UTC)
    if manifest and manifest.get("created_at"):
        created = datetime.fromisoformat(manifest["created_at"])
    return BackupInfo(
        name=path.name,
        size_bytes=st.st_size,
        created_at=created,
        files=len(manifest["files"]) if manifest else None,
        app_version=manifest.get("app_version") if manifest else None,
    )


def _read_manifest(z: zipfile.ZipFile) -> dict:
    try:
        manifest = json.loads(z.read(MANIFEST))
    except (KeyError, ValueError) as exc:
        raise BackupInvalid("Thiếu hoặc hỏng manifest.json") from exc
    if not isinstance(manifest, dict) or manifest.get("format") != FORMAT:
        raise BackupInvalid("Định dạng bản sao lưu không được hỗ trợ")
    return manifest


def list_backups(settings: Settings) -> list[BackupInfo]:
    d = backups_dir(settings)
    if not d.is_dir():
        return []
    out = []
    for p in d.glob("orchestra-backup-*.zip"):
        try:
            with zipfile.ZipFile(p) as z:
                manifest: dict | None = _read_manifest(z)
        except (zipfile.BadZipFile, BackupInvalid, OSError):
            manifest = None
        out.append(_info(p, manifest))
    return sorted(out, key=lambda b: b.created_at, reverse=True)


def backup_path(settings: Settings, name: str) -> Path:
    if "/" in name or "\\" in name or not name.startswith("orchestra-backup-"):
        raise NotFoundError("Không có bản sao lưu này", details={"name": name})
    p = backups_dir(settings) / name
    if not p.is_file():
        raise NotFoundError("Không có bản sao lưu này", details={"name": name})
    return p


def _safe(arc: str) -> bool:
    pp = PurePosixPath(arc)
    if pp.is_absolute() or ".." in pp.parts or "\\" in arc or ":" in arc:
        return False
    return arc == DB_NAME or (len(pp.parts) >= 2 and pp.parts[0] in TREES)


def verify(path: Path) -> dict:
    """Check structure, paths and every checksum. Returns the manifest."""
    try:
        z = zipfile.ZipFile(path)
    except (zipfile.BadZipFile, OSError) as exc:
        raise BackupInvalid(f"Không mở được file zip: {exc}") from exc
    with z:
        manifest = _read_manifest(z)
        listed = manifest.get("files") or {}
        names = set(z.namelist()) - {MANIFEST}
        if DB_NAME not in listed:
            raise BackupInvalid("Bản sao lưu không có cơ sở dữ liệu")
        if names != set(listed):
            raise BackupInvalid("Danh sách file không khớp manifest")
        for arc, meta in listed.items():
            if not _safe(arc):
                raise BackupInvalid(f"Đường dẫn không hợp lệ trong bản sao lưu: {arc}")
            h = hashlib.sha256()
            with z.open(arc) as f:
                for chunk in iter(lambda f=f: f.read(1 << 20), b""):
                    h.update(chunk)
            if h.hexdigest() != meta.get("sha256"):
                raise BackupInvalid(f"Checksum sai: {arc}")
    return manifest


def backend_running(settings: Settings) -> bool:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.settimeout(0.5)
        return s.connect_ex((LOOPBACK_HOST, settings.port)) == 0


def restore(settings: Settings, path: Path, *, check_running: bool = True) -> Path:
    """Replace current data with the backup. Returns where the old data was moved."""
    if check_running and backend_running(settings):
        raise ConflictError(
            f"Backend đang chạy ở cổng {settings.port}. Tắt app trước khi khôi phục.",
            code="BACKEND_RUNNING",
        )
    verify(path)
    db = _db_path(settings)
    data = settings.data_dir
    keep = data / f"pre-restore-{datetime.now(UTC):%Y%m%d-%H%M%S-%f}"
    keep.mkdir(parents=True)
    for p in (db, db.with_name(db.name + "-wal"), db.with_name(db.name + "-shm")):
        if p.exists():
            shutil.move(p, keep / p.name)
    for tree in TREES:
        if (data / tree).exists():
            shutil.move(data / tree, keep / tree)
    with zipfile.ZipFile(path) as z:
        for arc in z.namelist():
            if arc == MANIFEST:
                continue
            target = db if arc == DB_NAME else data / arc
            target.parent.mkdir(parents=True, exist_ok=True)
            with z.open(arc) as src, target.open("wb") as dst:
                shutil.copyfileobj(src, dst)
    return keep
