from __future__ import annotations

import hashlib
import json
import os
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path


@dataclass(frozen=True)
class TrialRecord:
    trial_id: str
    generation: int
    parent_trial_id: str | None
    symbol: str
    seed: int
    candidate_hash: str
    source_sha: str
    candidate_spec: dict
    evidence_window_ids: tuple[str, ...]
    metrics: dict
    promotion_decision: str
    rejection_reasons: tuple[str, ...]
    falsification_status: str
    created_at: str

    @classmethod
    def build(
        cls,
        *,
        generation: int,
        parent_trial_id: str | None,
        symbol: str,
        seed: int,
        candidate_hash: str,
        source_sha: str,
        candidate_spec: dict,
        evidence_window_ids: tuple[str, ...] = (),
        metrics: dict | None = None,
        promotion_decision: str = "PENDING",
        rejection_reasons: tuple[str, ...] = (),
        falsification_status: str = "NOT_RUN",
        created_at: str | None = None,
    ) -> "TrialRecord":
        symbol = str(symbol).upper()
        created_at = created_at or datetime.now(timezone.utc).isoformat()
        identity = {
            "generation": int(generation),
            "parent_trial_id": parent_trial_id,
            "symbol": symbol,
            "seed": int(seed),
            "candidate_hash": str(candidate_hash),
            "source_sha": str(source_sha),
            "evidence_window_ids": list(evidence_window_ids),
        }
        raw = json.dumps(identity, sort_keys=True, separators=(",", ":"))
        trial_id = "g8-" + hashlib.sha256(raw.encode()).hexdigest()[:20]
        return cls(
            trial_id=trial_id,
            generation=int(generation),
            parent_trial_id=parent_trial_id,
            symbol=symbol,
            seed=int(seed),
            candidate_hash=str(candidate_hash),
            source_sha=str(source_sha),
            candidate_spec=dict(candidate_spec),
            evidence_window_ids=tuple(str(x) for x in evidence_window_ids),
            metrics=dict(metrics or {}),
            promotion_decision=str(promotion_decision),
            rejection_reasons=tuple(str(x) for x in rejection_reasons),
            falsification_status=str(falsification_status),
            created_at=str(created_at),
        )

    @classmethod
    def example(cls, symbol: str, candidate_hash: str) -> "TrialRecord":
        return cls.build(
            generation=1,
            parent_trial_id=None,
            symbol=symbol,
            seed=7,
            candidate_hash=candidate_hash,
            source_sha="example-sha",
            candidate_spec={"symbol": str(symbol).upper(), "candidate_hash": candidate_hash},
            evidence_window_ids=("example-oof",),
            metrics={
                "trades": 120,
                "rr2_wr": 0.60,
                "worst_fold_wr": 0.55,
                "wilson_lower": 0.50,
                "expectancy_r": 0.40,
                "cost_stress_expectancy_r": 0.25,
                "max_drawdown_r": 5.0,
                "pbo": 0.20,
                "leakage_ok": True,
                "falsification_ok": True,
                "provenance_complete": True,
            },
            promotion_decision="PROMOTE",
            rejection_reasons=(),
            falsification_status="PASS",
            created_at="2026-09-13T00:00:00+00:00",
        )

    def to_dict(self) -> dict:
        payload = asdict(self)
        payload["evidence_window_ids"] = list(self.evidence_window_ids)
        payload["rejection_reasons"] = list(self.rejection_reasons)
        return payload

    @classmethod
    def from_dict(cls, payload: dict) -> "TrialRecord":
        try:
            return cls(
                trial_id=str(payload["trial_id"]),
                generation=int(payload["generation"]),
                parent_trial_id=None if payload.get("parent_trial_id") is None else str(payload["parent_trial_id"]),
                symbol=str(payload["symbol"]).upper(),
                seed=int(payload["seed"]),
                candidate_hash=str(payload["candidate_hash"]),
                source_sha=str(payload["source_sha"]),
                candidate_spec=dict(payload.get("candidate_spec") or {}),
                evidence_window_ids=tuple(str(x) for x in payload.get("evidence_window_ids", ())),
                metrics=dict(payload.get("metrics") or {}),
                promotion_decision=str(payload.get("promotion_decision", "UNKNOWN")),
                rejection_reasons=tuple(str(x) for x in payload.get("rejection_reasons", ())),
                falsification_status=str(payload.get("falsification_status", "UNKNOWN")),
                created_at=str(payload["created_at"]),
            )
        except (KeyError, TypeError, ValueError) as exc:
            raise ValueError("invalid G8 trial record") from exc


def append_trial(path: str | Path, record: TrialRecord) -> None:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    line = json.dumps(record.to_dict(), sort_keys=True, separators=(",", ":")) + "\n"
    with path.open("a", encoding="utf-8") as handle:
        handle.write(line)
        handle.flush()
        os.fsync(handle.fileno())


def iter_trials(path: str | Path):
    path = Path(path)
    if not path.exists():
        return
    with path.open(encoding="utf-8") as handle:
        for line_no, line in enumerate(handle, start=1):
            text = line.strip()
            if not text:
                continue
            try:
                payload = json.loads(text)
                yield TrialRecord.from_dict(payload)
            except (json.JSONDecodeError, ValueError) as exc:
                raise ValueError(f"invalid G8 trial ledger at line {line_no}") from exc


def seen_candidate_hashes(path: str | Path, symbol: str) -> set[str]:
    symbol = str(symbol).upper()
    return {record.candidate_hash for record in iter_trials(path) if record.symbol == symbol}
