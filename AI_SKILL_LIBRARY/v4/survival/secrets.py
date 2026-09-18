"""Immutable secret references and resolution (Tasks 1-2).

Secret values are never logged or persisted; plaintext serialization is
rejected outright.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, Mapping, Optional


class SecretError(Exception):
    """Raised for secret handling violations."""


@dataclass(frozen=True)
class SecretRef:
    provider: str
    path: str
    version: str

    def __post_init__(self) -> None:
        for name in ("provider", "path", "version"):
            value = getattr(self, name)
            if not isinstance(value, str) or not value.strip():
                raise SecretError("invalid_secret_ref_%s" % name)

    def __repr__(self) -> str:
        return "SecretRef(provider=%r, path=%r, version=%r)" % (
            self.provider,
            self.path,
            self.version,
        )

    def __str__(self) -> str:
        return self.__repr__()

    def to_dict(self) -> Dict[str, str]:
        return {"provider": self.provider, "path": self.path, "version": self.version}


def _lookup(backend: Any, ref: SecretRef) -> Optional[str]:
    if backend is None:
        return None
    if isinstance(backend, Mapping):
        for key in (
            (ref.provider, ref.path, ref.version),
            "%s:%s:%s" % (ref.provider, ref.path, ref.version),
            "%s/%s@%s" % (ref.provider, ref.path, ref.version),
            ref.path,
        ):
            if key in backend:
                value = backend[key]
                return value if isinstance(value, str) else None
        return None
    getter = getattr(backend, "get_secret", None)
    if callable(getter):
        value = getter(ref.provider, ref.path, ref.version)
        return value if isinstance(value, str) else None
    return None


def resolve_secret(ref: SecretRef, backend: Any) -> str:
    """Resolve a SecretRef against a backend without logging or persisting it."""
    if not isinstance(ref, SecretRef):
        raise SecretError("invalid_secret_ref")
    value = _lookup(backend, ref)
    if value is None:
        raise SecretError("secret_not_found")
    return value


def serialize_secret(*args: Any, **kwargs: Any) -> None:
    """Plaintext secret serialization is always rejected."""
    raise SecretError("plaintext_secret_serialization_rejected")


def reject_plaintext(payload: Any) -> None:
    """Reject any attempt to serialize a resolved secret value."""
    raise SecretError("plaintext_secret_serialization_rejected")
