from __future__ import annotations

import hashlib
import json
import os
from dataclasses import dataclass
from pathlib import Path

from g8.ledger import TrialRecord


SCHEMA_VERSION = 1


@dataclass
class ChampionRegistry:
    schema_version: int
    generation: int
    symbols: dict[str, dict]

    @classmethod
    def empty(cls, symbols: list[str]) -> "ChampionRegistry":
        normalized = [str(symbol).upper() for symbol in symbols]
        if not normalized or len(set(normalized)) != len(normalized):
            raise ValueError("champion registry symbols must be non-empty and unique")
        rows = {}
        for symbol in normalized:
            rows[symbol] = {
                "research_champion_id": None,
                "certified_champion_id": None,
                "research_champion": None,
                "certified_champion": None,
                "hall_of_fame": [],
                "profile_hash": None,
                "source_sha": None,
                "data_cutoff": None,
                "status": "QUARANTINED",
            }
        return cls(schema_version=SCHEMA_VERSION, generation=0, symbols=rows)

    def to_dict(self) -> dict:
        return {
            "schema_version": int(self.schema_version),
            "generation": int(self.generation),
            "symbols": {symbol: dict(row) for symbol, row in sorted(self.symbols.items())},
        }

    @classmethod
    def from_dict(cls, payload: dict) -> "ChampionRegistry":
        try:
            schema_version = int(payload["schema_version"])
            generation = int(payload.get("generation", 0))
            symbols = {str(k).upper(): dict(v) for k, v in dict(payload["symbols"]).items()}
        except (KeyError, TypeError, ValueError) as exc:
            raise ValueError("invalid G8 champion registry") from exc
        if schema_version != SCHEMA_VERSION or generation < 0 or not symbols:
            raise ValueError("invalid G8 champion registry schema")
        return cls(schema_version, generation, symbols)


def promote_champion(registry: ChampionRegistry, symbol: str, record: TrialRecord) -> None:
    symbol = str(symbol).upper()
    if record.symbol != symbol:
        raise ValueError("trial symbol does not match promotion symbol")
    if symbol not in registry.symbols:
        raise KeyError(f"unknown G8 registry symbol: {symbol}")
    row = registry.symbols[symbol]
    previous = row.get("research_champion_id")
    hall = list(row.get("hall_of_fame") or [])
    if previous and previous != record.trial_id and previous not in hall:
        hall.append(previous)
    row.update(
        {
            "research_champion_id": record.trial_id,
            "research_champion": record.to_dict(),
            "hall_of_fame": hall,
            "profile_hash": record.candidate_hash,
            "source_sha": record.source_sha,
            "status": "RESEARCH_ONLY",
        }
    )
    registry.generation = max(int(registry.generation), int(record.generation))


def certify_champion(registry: ChampionRegistry, symbol: str, record: TrialRecord) -> None:
    symbol = str(symbol).upper()
    if symbol not in registry.symbols:
        raise KeyError(f"unknown G8 registry symbol: {symbol}")
    if record.symbol != symbol:
        raise ValueError("trial symbol does not match certification symbol")
    row = registry.symbols[symbol]
    row["certified_champion_id"] = record.trial_id
    row["certified_champion"] = record.to_dict()
    row["status"] = "CERTIFIED_RESEARCH"


def _canonical_payload(registry: ChampionRegistry) -> dict:
    return registry.to_dict()


def snapshot_hash(registry: ChampionRegistry) -> str:
    raw = json.dumps(_canonical_payload(registry), sort_keys=True, separators=(",", ":"), allow_nan=False)
    return hashlib.sha256(raw.encode()).hexdigest()


def publish_snapshot(path: str | Path, registry: ChampionRegistry) -> str:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    digest = snapshot_hash(registry)
    payload = _canonical_payload(registry)
    payload["snapshot_hash"] = digest
    tmp = path.with_name(path.name + ".tmp")
    with tmp.open("w", encoding="utf-8") as handle:
        json.dump(payload, handle, indent=2, sort_keys=True)
        handle.write("\n")
        handle.flush()
        os.fsync(handle.fileno())
    tmp.replace(path)
    return digest


def load_registry(path: str | Path) -> ChampionRegistry:
    path = Path(path)
    try:
        payload = json.loads(path.read_text())
        expected = payload.pop("snapshot_hash", None)
        registry = ChampionRegistry.from_dict(payload)
        if expected is not None and expected != snapshot_hash(registry):
            raise ValueError("snapshot hash mismatch")
        return registry
    except (OSError, json.JSONDecodeError, TypeError, ValueError) as exc:
        raise ValueError(f"invalid G8 champion snapshot: {path}") from exc
