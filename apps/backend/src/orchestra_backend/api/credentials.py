"""Credential references (ADR-0021). No endpoint ever returns a secret value."""

from __future__ import annotations

import uuid

from fastapi import APIRouter, status

from orchestra_backend.api.deps import ContainerDep
from orchestra_backend.core.errors import AppError, ErrorResponse
from orchestra_backend.credentials import service as creds
from orchestra_backend.credentials.schemas import (
    CredentialCreate,
    CredentialOut,
    CredentialRotate,
    SecretStoreInfo,
    VerifyResult,
)
from orchestra_backend.credentials.store import SecretMissing, SecretStore

router = APIRouter(
    tags=["credentials"],
    responses={
        404: {"model": ErrorResponse},
        409: {"model": ErrorResponse},
        422: {"model": ErrorResponse},
    },
)


def _store(c: ContainerDep) -> SecretStore:
    return c.extras["secrets"]


@router.get("/secret-store", response_model=SecretStoreInfo)
def secret_store_info(c: ContainerDep) -> SecretStoreInfo:
    st = _store(c)
    return SecretStoreInfo(kind=st.name, secure=bool(st.secure), description=st.describe())


@router.get("/credentials", response_model=list[CredentialOut])
def list_credentials(c: ContainerDep, company_id: uuid.UUID | None = None) -> list[CredentialOut]:
    with c.tx() as s:
        return [creds.to_out(x) for x in creds.list_all(s, company_id)]


@router.post("/credentials", response_model=CredentialOut, status_code=status.HTTP_201_CREATED)
def create_credential(c: ContainerDep, body: CredentialCreate) -> CredentialOut:
    with c.tx() as s:
        return creds.to_out(creds.create(s, body, _store(c)))


@router.post("/credentials/{credential_id}/rotate", response_model=CredentialOut)
def rotate_credential(
    c: ContainerDep, credential_id: uuid.UUID, body: CredentialRotate
) -> CredentialOut:
    with c.tx() as s:
        cred = creds.get(s, credential_id)
        return creds.to_out(creds.rotate(s, cred, body.secret.get_secret_value(), _store(c)))


@router.post("/credentials/{credential_id}/revoke", response_model=CredentialOut)
def revoke_credential(c: ContainerDep, credential_id: uuid.UUID) -> CredentialOut:
    with c.tx() as s:
        return creds.to_out(creds.revoke(s, creds.get(s, credential_id), _store(c)))


@router.post("/credentials/{credential_id}/verify", response_model=VerifyResult)
async def verify_credential(c: ContainerDep, credential_id: uuid.UUID) -> VerifyResult:
    """Makes one cheap read-only call to the provider (list models)."""

    def load(s):  # type: ignore[no-untyped-def]
        cred = creds.get(s, credential_id)
        if cred.status != "active":
            raise AppError("Credential is revoked", code="credential_revoked")
        return creds.handle(cred, _store(c))

    handle = c.run_tx(load)
    runtime = c.extras["registry"].for_provider(handle.provider)
    if runtime is None or not hasattr(runtime, "verify"):
        ok, msg = False, f"Không có runtime cho provider {handle.provider}"
    else:
        try:
            ok, msg = await runtime.verify(handle.reveal())
        except SecretMissing:
            ok, msg = False, "Không đọc được secret (biến môi trường chưa đặt hoặc đã xóa khỏi kho)"

    def record(s):  # type: ignore[no-untyped-def]
        creds.record_verify(s, creds.get(s, credential_id), ok, msg)

    c.run_tx(record)
    return VerifyResult(ok=ok, message=msg)
