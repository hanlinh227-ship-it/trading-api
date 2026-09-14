from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
import hashlib
import hmac
import json
from typing import Any, Mapping


class JobType(str, Enum):
    IMAGE_RENDER = "IMAGE_RENDER"
    IMAGE_SETUP = "IMAGE_SETUP"
    VIDEO_RENDER = "VIDEO_RENDER"
    VOICE_RENDER = "VOICE_RENDER"
    FINAL_RENDER = "FINAL_RENDER"
    MEDIA_PROBE = "MEDIA_PROBE"


@dataclass(frozen=True)
class JobEnvelope:
    payload: dict[str, Any]
    signature: str
    algorithm: str = "HMAC-SHA256"

    def to_dict(self) -> dict[str, Any]:
        return {
            "algorithm": self.algorithm,
            "payload": self.payload,
            "signature": self.signature,
        }


def canonical_json(payload: Mapping[str, Any]) -> bytes:
    return json.dumps(
        payload,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
    ).encode("utf-8")


def sign_payload(payload: Mapping[str, Any], secret: bytes) -> JobEnvelope:
    from .allowlist import validate_job_request

    normalized = validate_job_request(dict(payload))
    signature = hmac.new(secret, canonical_json(normalized), hashlib.sha256).hexdigest()
    return JobEnvelope(payload=normalized, signature=signature)


def verify_envelope(
    envelope: JobEnvelope | Mapping[str, Any],
    secret: bytes,
) -> dict[str, Any]:
    from .allowlist import validate_job_request

    if isinstance(envelope, Mapping):
        envelope = JobEnvelope(
            payload=dict(envelope.get("payload") or {}),
            signature=str(envelope.get("signature") or ""),
            algorithm=str(envelope.get("algorithm") or "HMAC-SHA256"),
        )
    if envelope.algorithm != "HMAC-SHA256":
        raise ValueError("Unsupported signature algorithm")
    if not envelope.signature:
        raise ValueError("Missing signature")
    expected = hmac.new(
        secret,
        canonical_json(envelope.payload),
        hashlib.sha256,
    ).hexdigest()
    if not hmac.compare_digest(expected, envelope.signature):
        raise ValueError("Invalid signature")
    return validate_job_request(dict(envelope.payload))
