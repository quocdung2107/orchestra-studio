"""Worker identity: pairing, secrets, short-lived tokens, revocation (ADR-0025).

Secrets, pairing codes and tokens are random and high-entropy; only SHA-256 hashes are stored.
"""

from __future__ import annotations

import hashlib
import hmac
import secrets
import uuid
from dataclasses import dataclass
from datetime import datetime, timedelta

from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from orchestra_backend.core.errors import AppError, NotFoundError
from orchestra_backend.core.time import utcnow
from orchestra_backend.workers.models import Worker, WorkerPairing, WorkerToken

SEEN_EVERY_S = 5.0  # throttle last_seen_at writes
WORKER_RUNTIMES = ("mock", "ollama")  # runtimes that need no control-plane secret
_CODE_ALPHABET = "ABCDEFGHJKMNPQRSTUVWXYZ23456789"  # no 0/O, 1/I/L


class WorkerAuthError(AppError):
    status_code = 401
    code = "WORKER_AUTH"


class WorkerRevokedError(AppError):
    status_code = 403
    code = "WORKER_REVOKED"


def _h(value: str) -> str:
    return hashlib.sha256(value.encode()).hexdigest()


def _normalize_code(code: str) -> str:
    return "".join(ch for ch in code.upper() if ch.isalnum())


def create_pairing(s: Session, name: str, ttl_s: float) -> tuple[str, datetime]:
    raw = "".join(secrets.choice(_CODE_ALPHABET) for _ in range(10))
    exp = utcnow() + timedelta(seconds=ttl_s)
    s.add(WorkerPairing(code_hash=_h(raw), name=name.strip()[:100] or "Worker", expires_at=exp))
    return f"{raw[:5]}-{raw[5:]}", exp


@dataclass
class Enrolled:
    worker: Worker
    secret: str


def enroll(
    s: Session, code: str, *, hostname: str, platform: str, version: str, runtimes: list[str]
) -> Enrolled:
    pairing = s.scalar(
        select(WorkerPairing).where(WorkerPairing.code_hash == _h(_normalize_code(code)))
    )
    if pairing is None or pairing.used_at is not None or pairing.expires_at < utcnow():
        raise WorkerAuthError("Mã ghép nối sai, đã dùng hoặc đã hết hạn", code="PAIRING_INVALID")
    secret = secrets.token_urlsafe(32)
    worker = Worker(
        name=pairing.name,
        secret_hash=_h(secret),
        hostname=hostname[:200],
        platform=platform[:100],
        version=version[:40],
        runtimes_json=[r for r in runtimes if r in WORKER_RUNTIMES],
        last_seen_at=utcnow(),
    )
    s.add(worker)
    s.flush()
    pairing.used_at = utcnow()
    pairing.worker_id = worker.id
    return Enrolled(worker, secret)


def issue_token(s: Session, worker_id: uuid.UUID, secret: str, ttl_s: float) -> tuple[str, float]:
    worker = s.get(Worker, worker_id)
    if worker is None or not hmac.compare_digest(worker.secret_hash, _h(secret)):
        raise WorkerAuthError("Sai worker_id hoặc secret")
    if worker.status != "active":
        raise WorkerRevokedError("Worker đã bị thu hồi")
    now = utcnow()
    s.execute(
        delete(WorkerToken).where(WorkerToken.worker_id == worker.id, WorkerToken.expires_at < now)
    )
    token = secrets.token_urlsafe(32)
    s.add(
        WorkerToken(
            worker_id=worker.id, token_hash=_h(token), expires_at=now + timedelta(seconds=ttl_s)
        )
    )
    worker.last_seen_at = now
    return token, ttl_s


def authenticate(s: Session, token: str) -> Worker:
    row = s.scalar(select(WorkerToken).where(WorkerToken.token_hash == _h(token)))
    if row is None or row.expires_at < utcnow():
        raise WorkerAuthError(
            "Token worker không hợp lệ hoặc đã hết hạn", code="WORKER_TOKEN_INVALID"
        )
    worker = s.get(Worker, row.worker_id)
    assert worker is not None
    if worker.status != "active":
        raise WorkerRevokedError("Worker đã bị thu hồi")
    now = utcnow()
    if worker.last_seen_at is None or (now - worker.last_seen_at).total_seconds() > SEEN_EVERY_S:
        worker.last_seen_at = now
    return worker


def revoke(s: Session, worker_id: uuid.UUID) -> Worker:
    worker = get_worker(s, worker_id)
    if worker.status != "revoked":
        worker.status = "revoked"
        worker.revoked_at = utcnow()
        s.execute(delete(WorkerToken).where(WorkerToken.worker_id == worker.id))
    return worker


def get_worker(s: Session, worker_id: uuid.UUID) -> Worker:
    worker = s.get(Worker, worker_id)
    if worker is None:
        raise NotFoundError("Worker not found", details={"worker_id": str(worker_id)})
    return worker


def list_workers(s: Session) -> list[Worker]:
    return list(s.scalars(select(Worker).order_by(Worker.created_at)))


def active_workers_for(s: Session, runtime_id: str, pinned: uuid.UUID | None) -> list[Worker]:
    q = select(Worker).where(Worker.status == "active")
    if pinned is not None:
        q = q.where(Worker.id == pinned)
    return [w for w in s.scalars(q) if runtime_id in (w.runtimes_json or [])]
