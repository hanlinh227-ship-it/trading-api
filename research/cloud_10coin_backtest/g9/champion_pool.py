from __future__ import annotations

import hashlib
import json
import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Mapping

from .system_contract import SYSTEM_CONTRACT_VERSION


SCHEMA_VERSION = 1
KIND = "g9_continuous_champion_pool"
PRODUCTION_STRATEGY = "BYBIT-BTC-STATEFLOW-2.1"
PLANE = "RESEARCH"
AUTHORITY_LEVEL = "RESEARCH_CHAMPION"
_ALLOWED_PROFILE_STATUSES = {"RESEARCH_ONLY", "CERTIFIED_RESEARCH", "QUARANTINED"}


@dataclass(frozen=True, order=True)
class LaneKey:
    symbol: str
    regime: str
    family: str
    side: str

    def __post_init__(self) -> None:
        object.__setattr__(self, "symbol", str(self.symbol).upper())
        object.__setattr__(self, "regime", str(self.regime).upper())
        object.__setattr__(self, "family", str(self.family))
        object.__setattr__(self, "side", str(self.side).upper())
        if not all((self.symbol, self.regime, self.family, self.side)):
            raise ValueError("lane key fields must be non-empty")
        if self.side not in {"LONG", "SHORT"}:
            raise ValueError("lane side must be LONG or SHORT")

    @property
    def lane_id(self) -> str:
        return "|".join((self.symbol, self.regime, self.family, self.side))

    @classmethod
    def from_id(cls, lane_id: str) -> "LaneKey":
        parts = str(lane_id).split("|")
        if len(parts) != 4:
            raise ValueError("invalid G9 lane id")
        return cls(*parts)

    def to_dict(self) -> dict[str, str]:
        return {
            "symbol": self.symbol,
            "regime": self.regime,
            "family": self.family,
            "side": self.side,
        }


@dataclass(frozen=True)
class ResearchProfile:
    profile_id: str
    profile_hash: str
    source_sha: str
    evidence_epoch: str | None
    metrics: Mapping[str, Any]
    status: str = "RESEARCH_ONLY"
    production_execution_authority: bool = False

    def __post_init__(self) -> None:
        if not str(self.profile_id) or not str(self.profile_hash) or not str(self.source_sha):
            raise ValueError("profile id, hash and source sha are required")
        if self.status not in _ALLOWED_PROFILE_STATUSES:
            raise ValueError("invalid research profile status")
        if self.production_execution_authority is not False:
            raise ValueError("G9 research profiles cannot grant production execution authority")

    def to_dict(self) -> dict[str, Any]:
        return {
            "profile_id": str(self.profile_id),
            "profile_hash": str(self.profile_hash),
            "source_sha": str(self.source_sha),
            "evidence_epoch": self.evidence_epoch,
            "metrics": dict(self.metrics),
            "status": self.status,
            "research_only": True,
            "production_execution_authority": False,
        }

    @classmethod
    def from_dict(cls, payload: Mapping[str, Any]) -> "ResearchProfile":
        if payload.get("research_only", True) is not True:
            raise ValueError("profile must remain research-only")
        return cls(
            profile_id=str(payload["profile_id"]),
            profile_hash=str(payload["profile_hash"]),
            source_sha=str(payload["source_sha"]),
            evidence_epoch=payload.get("evidence_epoch"),
            metrics=dict(payload.get("metrics") or {}),
            status=str(payload.get("status", "RESEARCH_ONLY")),
            production_execution_authority=bool(payload.get("production_execution_authority", False)),
        )


@dataclass
class LaneState:
    champion: ResearchProfile | None = None
    fallback: ResearchProfile | None = None
    challengers: list[ResearchProfile] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "champion": None if self.champion is None else self.champion.to_dict(),
            "fallback": None if self.fallback is None else self.fallback.to_dict(),
            "challengers": [item.to_dict() for item in self.challengers],
        }

    @classmethod
    def from_dict(cls, payload: Mapping[str, Any]) -> "LaneState":
        champion = payload.get("champion")
        fallback = payload.get("fallback")
        challengers = payload.get("challengers") or []
        if not isinstance(challengers, list):
            raise ValueError("lane challengers must be a list")
        return cls(
            champion=None if champion is None else ResearchProfile.from_dict(champion),
            fallback=None if fallback is None else ResearchProfile.from_dict(fallback),
            challengers=[ResearchProfile.from_dict(item) for item in challengers],
        )


@dataclass
class ChampionPool:
    max_challengers: int = 3
    lanes: dict[str, LaneState] = field(default_factory=dict)
    quarantined: list[dict[str, str]] = field(default_factory=list)

    @classmethod
    def empty(cls, max_challengers: int = 3) -> "ChampionPool":
        if int(max_challengers) <= 0:
            raise ValueError("max_challengers must be positive")
        return cls(max_challengers=int(max_challengers), lanes={}, quarantined=[])

    def lane(self, key: LaneKey) -> LaneState:
        lane_id = key.lane_id
        if lane_id not in self.lanes:
            self.lanes[lane_id] = LaneState()
        return self.lanes[lane_id]

    def add_challenger(self, key: LaneKey, profile: ResearchProfile) -> None:
        state = self.lane(key)
        champion_id = None if state.champion is None else state.champion.profile_id
        if profile.profile_id == champion_id:
            return
        ordered = [item for item in state.challengers if item.profile_id != profile.profile_id]
        ordered.append(profile)
        if len(ordered) > self.max_challengers:
            ordered = ordered[-self.max_challengers :]
        state.challengers = ordered

    def promote(self, key: LaneKey, profile: ResearchProfile) -> None:
        state = self.lane(key)
        if state.champion is not None and state.champion.profile_id != profile.profile_id:
            state.fallback = state.champion
        state.champion = profile
        state.challengers = [item for item in state.challengers if item.profile_id != profile.profile_id]

    def rollback(self, key: LaneKey) -> None:
        state = self.lane(key)
        if state.fallback is None:
            raise ValueError("no fallback champion is available for rollback")
        previous = state.champion
        state.champion = state.fallback
        state.fallback = previous

    def quarantine(self, *, lane_key: str, profile_id: str, reason: str) -> None:
        row = {
            "lane_key": str(lane_key),
            "profile_id": str(profile_id),
            "reason": str(reason),
        }
        if not all(row.values()):
            raise ValueError("quarantine metadata must be non-empty")
        if row not in self.quarantined:
            self.quarantined.append(row)
        if len(self.quarantined) > 100:
            self.quarantined = self.quarantined[-100:]

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": SCHEMA_VERSION,
            "kind": KIND,
            "system_contract_version": SYSTEM_CONTRACT_VERSION,
            "plane": PLANE,
            "authority_level": AUTHORITY_LEVEL,
            "canonical_research_truth": True,
            "research_only": True,
            "production_execution_authority": False,
            "authority": {
                "execution": "none",
                "production_strategy": PRODUCTION_STRATEGY,
            },
            "max_challengers": int(self.max_challengers),
            "lanes": {
                lane_id: self.lanes[lane_id].to_dict()
                for lane_id in sorted(self.lanes)
            },
            "quarantined": [dict(item) for item in self.quarantined],
        }

    @classmethod
    def from_dict(cls, payload: Mapping[str, Any]) -> "ChampionPool":
        if payload.get("schema_version") != SCHEMA_VERSION or payload.get("kind") != KIND:
            raise ValueError("invalid G9 champion pool schema")
        if payload.get("research_only") is not True or payload.get("production_execution_authority") is not False:
            raise ValueError("G9 champion pool authority boundary violated")
        authority = payload.get("authority")
        if not isinstance(authority, Mapping) or authority.get("execution") != "none":
            raise ValueError("G9 champion pool execution authority is forbidden")
        if authority.get("production_strategy") != PRODUCTION_STRATEGY:
            raise ValueError("production strategy mismatch")

        # Legacy pool snapshots are accepted and normalized on the next publish.
        if "system_contract_version" in payload and payload.get("system_contract_version") != SYSTEM_CONTRACT_VERSION:
            raise ValueError("G9 champion pool system contract mismatch")
        if "plane" in payload and payload.get("plane") != PLANE:
            raise ValueError("G9 champion pool plane mismatch")
        if "authority_level" in payload and payload.get("authority_level") != AUTHORITY_LEVEL:
            raise ValueError("G9 champion pool authority level mismatch")
        if "canonical_research_truth" in payload and payload.get("canonical_research_truth") is not True:
            raise ValueError("G9 champion pool canonical truth flag invalid")

        max_challengers = int(payload.get("max_challengers", 3))
        if max_challengers <= 0:
            raise ValueError("max_challengers must be positive")
        raw_lanes = payload.get("lanes") or {}
        if not isinstance(raw_lanes, Mapping):
            raise ValueError("lanes must be an object")
        lanes: dict[str, LaneState] = {}
        for lane_id, raw_state in raw_lanes.items():
            LaneKey.from_id(str(lane_id))
            if not isinstance(raw_state, Mapping):
                raise ValueError("lane state must be an object")
            state = LaneState.from_dict(raw_state)
            if len(state.challengers) > max_challengers:
                raise ValueError("challenger pool exceeds configured bound")
            lanes[str(lane_id)] = state

        raw_quarantine = payload.get("quarantined") or []
        if not isinstance(raw_quarantine, list):
            raise ValueError("quarantined must be a list")
        quarantined: list[dict[str, str]] = []
        for raw in raw_quarantine:
            if not isinstance(raw, Mapping):
                raise ValueError("invalid quarantine row")
            row = {
                "lane_key": str(raw.get("lane_key") or ""),
                "profile_id": str(raw.get("profile_id") or ""),
                "reason": str(raw.get("reason") or ""),
            }
            if not all(row.values()):
                raise ValueError("invalid quarantine metadata")
            quarantined.append(row)
        return cls(
            max_challengers=max_challengers,
            lanes=lanes,
            quarantined=quarantined[-100:],
        )


def _dict_hash(payload: Mapping[str, Any]) -> str:
    raw = json.dumps(payload, sort_keys=True, separators=(",", ":"), allow_nan=False)
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def _pool_hash(pool: ChampionPool) -> str:
    return _dict_hash(pool.to_dict())


def publish_pool(path: str | Path, pool: ChampionPool) -> str:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    digest = _pool_hash(pool)
    payload = pool.to_dict()
    payload["pool_hash"] = digest
    tmp = path.with_name(path.name + ".tmp")
    with tmp.open("w", encoding="utf-8") as handle:
        json.dump(payload, handle, indent=2, sort_keys=True, allow_nan=False)
        handle.write("\n")
        handle.flush()
        os.fsync(handle.fileno())
    tmp.replace(path)
    return digest


def load_pool(path: str | Path) -> ChampionPool:
    path = Path(path)
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ValueError(f"invalid G9 champion pool: {path}") from exc
    if not isinstance(payload, dict):
        raise ValueError("invalid G9 champion pool payload")
    expected = payload.pop("pool_hash", None)
    if not isinstance(expected, str):
        raise ValueError("G9 champion pool hash missing")

    # Verify exactly what was persisted before applying legacy normalization.
    if expected != _dict_hash(payload):
        raise ValueError("G9 champion pool hash mismatch")
    return ChampionPool.from_dict(payload)
