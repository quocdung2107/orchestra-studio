"""Secret stores (ADR-0021). Only this module and the runtime adapters ever see secret values."""

from __future__ import annotations

import os
import re
import threading
from dataclasses import dataclass
from typing import Protocol

from orchestra_backend.core.errors import AppError
from orchestra_backend.core.redact import register_secret

SERVICE = "orchestra-studio"
ENV_NAME = re.compile(r"^[A-Za-z_][A-Za-z0-9_]{0,127}$")


class SecretStoreUnavailable(AppError):
    status_code = 409
    code = "secret_store_unavailable"


class SecretMissing(AppError):
    status_code = 409
    code = "secret_missing"


class SecretStore(Protocol):
    name: str
    secure: bool

    def set(self, ref: str, value: str) -> None: ...
    def get(self, ref: str) -> str | None: ...
    def delete(self, ref: str) -> None: ...
    def describe(self) -> str: ...


class MemorySecretStore:
    """Process memory only. For tests and throwaway dev; never the default."""

    name = "memory"
    secure = False

    def __init__(self) -> None:
        self._data: dict[str, str] = {}
        self._lock = threading.Lock()

    def set(self, ref: str, value: str) -> None:
        with self._lock:
            self._data[ref] = value

    def get(self, ref: str) -> str | None:
        with self._lock:
            return self._data.get(ref)

    def delete(self, ref: str) -> None:
        with self._lock:
            self._data.pop(ref, None)

    def describe(self) -> str:
        return "Bộ nhớ tạm (mất khi tắt backend, chỉ dùng để thử)"


class KeyringSecretStore:
    """OS-backed store: Windows Credential Manager, macOS Keychain, Secret Service."""

    name = "keyring"

    def __init__(self) -> None:
        import keyring  # local import: optional backend discovery is slow-ish

        self._keyring = keyring

    def _backend_name(self) -> str:
        kr = self._keyring.get_keyring()
        return f"{type(kr).__module__}.{type(kr).__name__}"

    @staticmethod
    def _is_secure(kr: object) -> bool:
        name = f"{type(kr).__module__}.{type(kr).__name__}".lower()
        if "chainer" in name:
            inner = list(getattr(kr, "backends", []) or [])
            return bool(inner) and all(KeyringSecretStore._is_secure(b) for b in inner)
        return not any(bad in name for bad in ("fail", "plaintext", "null", "keyrings.alt"))

    @property
    def secure(self) -> bool:
        return self._is_secure(self._keyring.get_keyring())

    def _require(self) -> None:
        if not self.secure:
            raise SecretStoreUnavailable(
                "No secure OS credential store is available on this machine",
                details={"backend": self._backend_name()},
            )

    def set(self, ref: str, value: str) -> None:
        self._require()
        self._keyring.set_password(SERVICE, ref, value)

    def get(self, ref: str) -> str | None:
        if not self.secure:
            return None
        return self._keyring.get_password(SERVICE, ref)

    def delete(self, ref: str) -> None:
        if not self.secure:
            return
        try:
            self._keyring.delete_password(SERVICE, ref)
        except self._keyring.errors.PasswordDeleteError:
            pass

    def describe(self) -> str:
        return self._backend_name()


def make_store(kind: str) -> SecretStore:
    if kind == "memory":
        return MemorySecretStore()
    if kind == "keyring":
        return KeyringSecretStore()
    raise ValueError(f"unknown secret store: {kind}")


@dataclass(frozen=True)
class SecretHandle:
    """Reads the secret only when an adapter actually needs it. Never serialized."""

    credential_id: str
    provider: str
    store: str
    store_ref: str
    _secrets: SecretStore

    def reveal(self) -> str:
        if self.store == "env":
            value = os.environ.get(self.store_ref)
        else:
            value = self._secrets.get(self.store_ref)
        if not value:
            raise SecretMissing(
                "Secret for credential is not available",
                details={"credential_id": self.credential_id, "store": self.store},
            )
        register_secret(value)
        return value

    def __repr__(self) -> str:  # never leak through debug output
        return f"SecretHandle({self.credential_id}, {self.provider}, {self.store})"
