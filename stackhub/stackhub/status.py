from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Mapping


_SECRET_MARKERS = (
    "token",
    "secret",
    "password",
    "passphrase",
    "seed",
    "private_key",
    "privatekey",
    "api_key",
    "apikey",
)


def _is_secret_key(key: str) -> bool:
    normalized = key.strip().lower()
    return any(marker in normalized for marker in _SECRET_MARKERS)


def _redact(value: Any) -> Any:
    if isinstance(value, Mapping):
        return {
            str(key): "[REDACTED]" if _is_secret_key(str(key)) else _redact(item)
            for key, item in value.items()
        }
    if isinstance(value, list):
        return [_redact(item) for item in value]
    if isinstance(value, tuple):
        return tuple(_redact(item) for item in value)
    return value


def build_status(
    environment: str,
    ledger_summary: Mapping[str, Any],
    extra: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    return {
        "version": "0.1.0",
        "updated_utc": datetime.now(timezone.utc).isoformat(),
        "environment": environment,
        "ledger": _redact(dict(ledger_summary)),
        "extra": _redact(dict(extra or {})),
    }
