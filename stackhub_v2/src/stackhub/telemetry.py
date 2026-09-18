from __future__ import annotations

import json
import re
from typing import Any

_SECRET_KEYS = {"api_key", "apikey", "authorization", "private_key", "seed_phrase", "mnemonic", "token", "secret"}
_TB_KEY = re.compile(r"tb_live_[A-Za-z0-9_-]{8,}")
_BEARER = re.compile(r"Bearer\s+[A-Za-z0-9._~+/-]{8,}", re.I)


def _redact_string(value: str) -> str:
    value = _TB_KEY.sub("[REDACTED]", value)
    value = _BEARER.sub("Bearer [REDACTED]", value)
    return value


def redact(value: Any) -> Any:
    if isinstance(value, dict):
        out = {}
        for key, item in value.items():
            if str(key).lower() in _SECRET_KEYS:
                out[key] = "[REDACTED]"
            else:
                out[key] = redact(item)
        return out
    if isinstance(value, (list, tuple)):
        return [redact(x) for x in value]
    if isinstance(value, str):
        return _redact_string(value)
    return value


def json_line(event: str, payload: dict[str, Any]) -> str:
    return json.dumps({"event": event, **redact(payload)}, sort_keys=True, default=str)
