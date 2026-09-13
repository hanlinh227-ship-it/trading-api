from __future__ import annotations

import hashlib
import json
from dataclasses import asdict, dataclass
from pathlib import Path


SCHEMA_VERSION = 1


@dataclass
class EvidenceEpoch:
    epoch_id: str
    data_cutoff: str
    max_adaptive_trials: int
    consumed_trials: dict[str, int]

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, payload: dict) -> "EvidenceEpoch":
        try:
            epoch_id = str(payload["epoch_id"])
            data_cutoff = str(payload.get("data_cutoff", "unknown"))
            max_adaptive_trials = int(payload["max_adaptive_trials"])
            consumed_trials = {str(k): int(v) for k, v in dict(payload["consumed_trials"]).items()}
        except (KeyError, TypeError, ValueError) as exc:
            raise ValueError("invalid G8 checkpoint evidence epoch") from exc
        if max_adaptive_trials < 0 or any(v < 0 for v in consumed_trials.values()):
            raise ValueError("invalid G8 checkpoint evidence budget")
        return cls(epoch_id, data_cutoff, max_adaptive_trials, consumed_trials)


@dataclass
class LoopState:
    schema_version: int
    generation: int
    source_sha: str
    symbols: list[str]
    epoch: EvidenceEpoch
    last_snapshot_hash: str | None

    @classmethod
    def new(
        cls,
        *,
        symbols: list[str],
        source_sha: str,
        max_adaptive_trials: int,
        data_cutoff: str = "unknown",
    ) -> "LoopState":
        normalized = [str(symbol).upper() for symbol in symbols]
        if not normalized or len(set(normalized)) != len(normalized):
            raise ValueError("G8 symbols must be non-empty and unique")
        if int(max_adaptive_trials) < 0:
            raise ValueError("max_adaptive_trials must be non-negative")
        raw = json.dumps(
            {
                "symbols": normalized,
                "source_sha": str(source_sha),
                "data_cutoff": str(data_cutoff),
            },
            sort_keys=True,
            separators=(",", ":"),
        )
        epoch = EvidenceEpoch(
            epoch_id=hashlib.sha256(raw.encode()).hexdigest()[:16],
            data_cutoff=str(data_cutoff),
            max_adaptive_trials=int(max_adaptive_trials),
            consumed_trials={symbol: 0 for symbol in normalized},
        )
        return cls(
            schema_version=SCHEMA_VERSION,
            generation=0,
            source_sha=str(source_sha),
            symbols=normalized,
            epoch=epoch,
            last_snapshot_hash=None,
        )

    def to_dict(self) -> dict:
        return {
            "schema_version": int(self.schema_version),
            "generation": int(self.generation),
            "source_sha": str(self.source_sha),
            "symbols": list(self.symbols),
            "epoch": self.epoch.to_dict(),
            "last_snapshot_hash": self.last_snapshot_hash,
        }

    @classmethod
    def from_dict(cls, payload: dict) -> "LoopState":
        try:
            schema_version = int(payload["schema_version"])
            generation = int(payload["generation"])
            source_sha = str(payload["source_sha"])
            symbols = [str(x).upper() for x in payload["symbols"]]
            epoch = EvidenceEpoch.from_dict(dict(payload["epoch"]))
            last_snapshot_hash = payload.get("last_snapshot_hash")
        except (KeyError, TypeError, ValueError) as exc:
            raise ValueError("invalid G8 checkpoint") from exc
        if schema_version != SCHEMA_VERSION or generation < 0:
            raise ValueError("invalid G8 checkpoint schema")
        if not symbols or len(set(symbols)) != len(symbols):
            raise ValueError("invalid G8 checkpoint symbols")
        if set(epoch.consumed_trials) != set(symbols):
            raise ValueError("invalid G8 checkpoint evidence symbols")
        if last_snapshot_hash is not None:
            last_snapshot_hash = str(last_snapshot_hash)
        return cls(schema_version, generation, source_sha, symbols, epoch, last_snapshot_hash)


def can_promote(state: LoopState, symbol: str) -> bool:
    symbol = str(symbol).upper()
    if symbol not in state.epoch.consumed_trials:
        return False
    return state.epoch.consumed_trials[symbol] < state.epoch.max_adaptive_trials


def consume_promotion_trial(state: LoopState, symbol: str) -> None:
    symbol = str(symbol).upper()
    if symbol not in state.epoch.consumed_trials:
        raise KeyError(f"unknown G8 symbol: {symbol}")
    if not can_promote(state, symbol):
        raise RuntimeError(f"promotion evidence budget exhausted for {symbol}")
    state.epoch.consumed_trials[symbol] += 1


def load_loop_state(path: str | Path) -> LoopState:
    path = Path(path)
    try:
        payload = json.loads(path.read_text())
        if not isinstance(payload, dict):
            raise TypeError("checkpoint root must be an object")
        return LoopState.from_dict(payload)
    except (OSError, json.JSONDecodeError, TypeError, ValueError) as exc:
        raise ValueError(f"invalid G8 checkpoint: {path}") from exc


def save_loop_state(path: str | Path, state: LoopState) -> None:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(path.name + ".tmp")
    payload = json.dumps(state.to_dict(), indent=2, sort_keys=True) + "\n"
    tmp.write_text(payload)
    tmp.replace(path)
