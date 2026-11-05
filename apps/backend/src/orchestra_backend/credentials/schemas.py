from __future__ import annotations

import uuid
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, SecretStr, model_validator

Provider = Literal["anthropic", "openai"]


class CredentialOut(BaseModel):
    """Never contains the secret (ADR-0021)."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    provider: str
    label: str
    company_id: uuid.UUID | None
    store: str
    env_var: str | None = None
    status: str
    created_at: datetime
    updated_at: datetime
    rotated_at: datetime | None
    revoked_at: datetime | None
    last_verified_at: datetime | None
    last_verify_ok: bool | None
    last_verify_message: str | None


class CredentialCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    provider: Provider
    label: str = Field(min_length=1, max_length=200)
    company_id: uuid.UUID | None = None
    # Exactly one of: a secret to put in the OS store, or an environment variable name.
    secret: SecretStr | None = Field(default=None, min_length=8, max_length=500)
    env_var: str | None = Field(default=None, pattern=r"^[A-Za-z_][A-Za-z0-9_]{0,127}$")

    @model_validator(mode="after")
    def _one_source(self) -> CredentialCreate:
        if (self.secret is None) == (self.env_var is None):
            raise ValueError("provide exactly one of 'secret' or 'env_var'")
        return self


class CredentialRotate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    secret: SecretStr = Field(min_length=8, max_length=500)


class SecretStoreInfo(BaseModel):
    kind: str
    secure: bool
    description: str


class VerifyResult(BaseModel):
    ok: bool
    message: str
