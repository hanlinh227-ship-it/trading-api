from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from datetime import datetime
from enum import Enum, IntEnum
from typing import Any, Iterable, Mapping


SYSTEM_CONTRACT_VERSION = 1
PRODUCTION_STRATEGY = "BYBIT-BTC-STATEFLOW-2.1"


class DataPlane(str, Enum):
    PRODUCTION_AUTHORITY = "PRODUCTION_AUTHORITY"
    VERIFIED_RUNTIME = "VERIFIED_RUNTIME"
    STABLE_EVIDENCE = "STABLE_EVIDENCE"
    LIVE_CONTEXT = "LIVE_CONTEXT"
    RESEARCH = "RESEARCH"
    EXPERIMENTAL = "EXPERIMENTAL"
    IMPORTED = "IMPORTED"


class AuthorityLevel(IntEnum):
    IMPORTED = 10
    EXPERIMENTAL = 20
    LIVE_CONTEXT = 30
    RESEARCH_CHAMPION = 40
    CERTIFIED_RESEARCH = 50
    STABLE_EVIDENCE = 60
    VERIFIED_RUNTIME = 70
    PRODUCTION_AUTHORITY = 80


class Freshness(str, Enum):
    FRESH = "FRESH"
    DEGRADED = "DEGRADED"
    STALE = "STALE"
    UNKNOWN = "UNKNOWN"


_FRESHNESS_RANK = {
    Freshness.UNKNOWN: 0,
    Freshness.STALE: 1,
    Freshness.DEGRADED: 2,
    Freshness.FRESH: 3,
}


def _iso(value: datetime) -> str:
    if not isinstance(value, datetime) or value.tzinfo is None:
        raise ValueError("timestamps must be timezone-aware")
    return value.isoformat()


def _canonical(payload: Mapping[str, Any]) -> str:
    clean = dict(payload)
    clean.pop("envelope_hash", None)
    return json.dumps(clean, sort_keys=True, separators=(",", ":"), allow_nan=False)


def compute_envelope_hash(payload: Mapping[str, Any]) -> str:
    return hashlib.sha256(_canonical(payload).encode("utf-8")).hexdigest()


@dataclass(frozen=True)
class EvidenceEnvelope:
    kind: str
    subject: str
    value: Any
    source: str
    source_sha: str
    plane: DataPlane
    authority: AuthorityLevel
    freshness: Freshness
    event_time: datetime
    ingest_time: datetime
    research_only: bool
    production_execution_authority: bool
    envelope_hash: str

    @classmethod
    def build(
        cls,
        *,
        kind: str,
        subject: str,
        value: Any,
        source: str,
        source_sha: str,
        plane: DataPlane,
        authority: AuthorityLevel,
        freshness: Freshness,
        event_time: datetime,
        ingest_time: datetime,
        research_only: bool,
        production_execution_authority: bool,
    ) -> "EvidenceEnvelope":
        if not all((str(kind).strip(), str(subject).strip(), str(source).strip(), str(source_sha).strip())):
            raise ValueError("kind, subject, source and source_sha are required")
        if event_time.tzinfo is None or ingest_time.tzinfo is None:
            raise ValueError("timestamps must be timezone-aware")
        if ingest_time < event_time:
            raise ValueError("ingest_time must be greater than or equal to event_time")
        if production_execution_authority is not False:
            raise ValueError("production execution authority cannot be granted by evidence envelope")
        base = {
            "contract_version": SYSTEM_CONTRACT_VERSION,
            "kind": str(kind),
            "subject": str(subject).upper(),
            "value": value,
            "source": str(source),
            "source_sha": str(source_sha),
            "plane": DataPlane(plane).value,
            "authority": AuthorityLevel(authority).name,
            "authority_rank": int(AuthorityLevel(authority)),
            "freshness": Freshness(freshness).value,
            "event_time": _iso(event_time),
            "ingest_time": _iso(ingest_time),
            "research_only": bool(research_only),
            "production_execution_authority": False,
        }
        digest = compute_envelope_hash(base)
        return cls(
            kind=base["kind"],
            subject=base["subject"],
            value=value,
            source=base["source"],
            source_sha=base["source_sha"],
            plane=DataPlane(base["plane"]),
            authority=AuthorityLevel[base["authority"]],
            freshness=Freshness(base["freshness"]),
            event_time=event_time,
            ingest_time=ingest_time,
            research_only=bool(research_only),
            production_execution_authority=False,
            envelope_hash=digest,
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "contract_version": SYSTEM_CONTRACT_VERSION,
            "kind": self.kind,
            "subject": self.subject,
            "value": self.value,
            "source": self.source,
            "source_sha": self.source_sha,
            "plane": self.plane.value,
            "authority": self.authority.name,
            "authority_rank": int(self.authority),
            "freshness": self.freshness.value,
            "event_time": _iso(self.event_time),
            "ingest_time": _iso(self.ingest_time),
            "research_only": self.research_only,
            "production_execution_authority": False,
            "envelope_hash": self.envelope_hash,
        }


@dataclass(frozen=True)
class ConflictResolution:
    status: str
    selected: EvidenceEnvelope | None
    reason: str
    candidates: tuple[str, ...]


def validate_envelope(payload: Mapping[str, Any]) -> list[str]:
    if not isinstance(payload, Mapping):
        return ["ENVELOPE_MUST_BE_OBJECT"]
    errors: list[str] = []
    if payload.get("contract_version") != SYSTEM_CONTRACT_VERSION:
        errors.append("CONTRACT_VERSION_INVALID")
    for key in ("kind", "subject", "source", "source_sha"):
        if not isinstance(payload.get(key), str) or not str(payload.get(key)).strip():
            errors.append(f"{key.upper()}_REQUIRED")
    try:
        plane = DataPlane(str(payload.get("plane")))
    except ValueError:
        plane = None
        errors.append("PLANE_INVALID")
    try:
        authority = AuthorityLevel[str(payload.get("authority"))]
    except (KeyError, TypeError):
        authority = None
        errors.append("AUTHORITY_INVALID")
    if authority is not None and payload.get("authority_rank") != int(authority):
        errors.append("AUTHORITY_RANK_MISMATCH")
    try:
        Freshness(str(payload.get("freshness")))
    except ValueError:
        errors.append("FRESHNESS_INVALID")
    if payload.get("production_execution_authority") is not False:
        errors.append("PRODUCTION_EXECUTION_AUTHORITY_FORBIDDEN")
    if plane is not DataPlane.PRODUCTION_AUTHORITY and payload.get("research_only") is not True:
        errors.append("RESEARCH_ONLY_REQUIRED")
    try:
        event_time = datetime.fromisoformat(str(payload.get("event_time")))
        ingest_time = datetime.fromisoformat(str(payload.get("ingest_time")))
        if event_time.tzinfo is None or ingest_time.tzinfo is None:
            raise ValueError
        if ingest_time < event_time:
            errors.append("TIMESTAMP_ORDER_INVALID")
    except (TypeError, ValueError):
        errors.append("TIMESTAMP_INVALID")
    expected = payload.get("envelope_hash")
    if not isinstance(expected, str) or len(expected) != 64:
        errors.append("ENVELOPE_HASH_INVALID")
    elif expected != compute_envelope_hash(payload):
        errors.append("ENVELOPE_HASH_MISMATCH")
    return errors


def _selection_rank(item: EvidenceEnvelope) -> tuple[int, int, float]:
    return (
        int(item.authority),
        _FRESHNESS_RANK[item.freshness],
        item.ingest_time.timestamp(),
    )


def resolve_conflict(candidates: Iterable[EvidenceEnvelope]) -> ConflictResolution:
    items = list(candidates)
    if not items:
        return ConflictResolution("BLOCKED", None, "NO_EVIDENCE", ())
    subjects = {(item.kind, item.subject) for item in items}
    if len(subjects) != 1:
        return ConflictResolution(
            "BLOCKED",
            None,
            "INCOMPARABLE_EVIDENCE",
            tuple(item.envelope_hash for item in items),
        )
    for item in items:
        errors = validate_envelope(item.to_dict())
        if errors:
            return ConflictResolution(
                "BLOCKED",
                None,
                "INVALID_EVIDENCE",
                tuple(candidate.envelope_hash for candidate in items),
            )
    ordered = sorted(items, key=_selection_rank, reverse=True)
    top = ordered[0]
    same_rank = [item for item in ordered if _selection_rank(item)[:2] == _selection_rank(top)[:2]]
    values = {_canonical({"value": item.value}) for item in same_rank}
    if len(values) > 1:
        return ConflictResolution(
            "BLOCKED",
            None,
            "UNRESOLVED_EQUAL_AUTHORITY_CONFLICT",
            tuple(item.envelope_hash for item in same_rank),
        )
    reason = "HIGHER_AUTHORITY" if any(item.authority != top.authority for item in ordered[1:]) else "FRESHER_EVIDENCE"
    return ConflictResolution(
        "RESOLVED",
        top,
        reason,
        tuple(item.envelope_hash for item in ordered),
    )
