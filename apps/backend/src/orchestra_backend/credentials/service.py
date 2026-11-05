"""Credential references (ADR-0021). Secrets go to the SecretStore, never to the DB or events."""

from __future__ import annotations

import logging
import uuid

from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from orchestra_backend.companies.service import get_company
from orchestra_backend.core.errors import InvalidStateError, NotFoundError
from orchestra_backend.core.redact import forget_secret, register_secret
from orchestra_backend.core.time import utcnow
from orchestra_backend.credentials.models import Credential
from orchestra_backend.credentials.schemas import CredentialCreate, CredentialOut
from orchestra_backend.credentials.store import SecretHandle, SecretStore
from orchestra_backend.events.catalog import CredentialChanged
from orchestra_backend.events.service import append_event

log = logging.getLogger(__name__)
SOURCE = "credentials"


def to_out(c: Credential) -> CredentialOut:
    out = CredentialOut.model_validate(c)
    if c.store == "env":
        out.env_var = c.store_ref  # a variable *name*, not a secret
    return out


def _audit(s: Session, c: Credential, event_type: str, **extra: object) -> None:
    log.info("credential %s %s (%s, %s)", c.id, event_type, c.provider, c.label)
    if c.company_id is None:
        return  # global credential: audit lives in the row timestamps + log
    append_event(
        s,
        company_id=c.company_id,
        event_type=event_type,
        source=SOURCE,
        payload=CredentialChanged(
            credential_id=c.id, provider=c.provider, label=c.label, store=c.store, **extra
        ),
    )


def get(s: Session, credential_id: uuid.UUID) -> Credential:
    c = s.get(Credential, credential_id)
    if c is None:
        raise NotFoundError("Credential not found", details={"credential_id": str(credential_id)})
    return c


def list_all(s: Session, company_id: uuid.UUID | None = None) -> list[Credential]:
    q = select(Credential).order_by(Credential.created_at)
    if company_id is not None:
        q = q.where(or_(Credential.company_id.is_(None), Credential.company_id == company_id))
    return list(s.scalars(q))


def create(s: Session, data: CredentialCreate, secrets: SecretStore) -> Credential:
    if data.company_id is not None:
        get_company(s, data.company_id)
    c = Credential(
        id=uuid.uuid4(),
        provider=data.provider,
        label=data.label,
        company_id=data.company_id,
        store="env" if data.env_var else secrets.name,
        store_ref="",
    )
    if data.env_var:
        c.store_ref = data.env_var
    else:
        assert data.secret is not None
        value = data.secret.get_secret_value()
        c.store_ref = str(c.id)
        secrets.set(c.store_ref, value)  # raises if no secure store: nothing persisted
        register_secret(value)
    s.add(c)
    s.flush()
    _audit(s, c, "credential.created")
    return c


def rotate(s: Session, c: Credential, value: str, secrets: SecretStore) -> Credential:
    if c.status != "active":
        raise InvalidStateError("Credential is revoked", details={"credential_id": str(c.id)})
    if c.store == "env":
        raise InvalidStateError(
            "Environment-variable credentials are rotated by changing the variable",
            code="rotate_not_supported",
        )
    old = secrets.get(c.store_ref)
    secrets.set(c.store_ref, value)
    register_secret(value)
    if old:
        forget_secret(old)
    c.rotated_at = utcnow()
    c.last_verified_at, c.last_verify_ok, c.last_verify_message = None, None, None
    s.flush()
    _audit(s, c, "credential.rotated")
    return c


def revoke(s: Session, c: Credential, secrets: SecretStore) -> Credential:
    if c.status == "revoked":
        return c
    if c.store != "env":
        secrets.delete(c.store_ref)
    c.status = "revoked"
    c.revoked_at = utcnow()
    s.flush()
    _audit(s, c, "credential.revoked")
    return c


def record_verify(s: Session, c: Credential, ok: bool, message: str) -> Credential:
    c.last_verified_at = utcnow()
    c.last_verify_ok = ok
    c.last_verify_message = message[:500]
    s.flush()
    _audit(s, c, "credential.verified", ok=ok)
    return c


def handle(c: Credential, secrets: SecretStore) -> SecretHandle:
    return SecretHandle(
        credential_id=str(c.id),
        provider=c.provider,
        store=c.store,
        store_ref=c.store_ref,
        _secrets=secrets,
    )


def check_usable(c: Credential, provider: str, company_id: uuid.UUID) -> tuple[str, str] | None:
    """Return (error_code, message) when this credential may not be used for this run."""
    if c.status != "active":
        return "CREDENTIAL_REVOKED", f"Credential '{c.label}' has been revoked"
    if c.provider != provider:
        return "CREDENTIAL_PROVIDER_MISMATCH", f"Credential '{c.label}' is for {c.provider}"
    if c.company_id is not None and c.company_id != company_id:
        return "CREDENTIAL_SCOPE_DENIED", f"Credential '{c.label}' belongs to another company"
    return None
