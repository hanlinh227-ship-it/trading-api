from __future__ import annotations

from datetime import datetime
import hashlib
import json
import os
from pathlib import Path
from typing import Any, Iterable


_SCHEMA_VERSION = "g9-experience-v1"


def _iso(value: datetime) -> str:
    if value.tzinfo is None:
        raise ValueError("timestamps must be timezone-aware")
    return value.isoformat()


def _stable_id(prefix: str, payload: dict[str, Any]) -> str:
    canonical = json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=True)
    return f"{prefix}-{hashlib.sha256(canonical.encode('utf-8')).hexdigest()[:24]}"


class ExperienceStore:
    def __init__(self, path: Path | str):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)

    def _append(self, payload: dict[str, Any]) -> None:
        line = json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=True) + "\n"
        with self.path.open("a", encoding="utf-8") as handle:
            handle.write(line)
            handle.flush()
            os.fsync(handle.fileno())

    def append_observation(
        self,
        *,
        symbol: str,
        event_time: datetime,
        market_snapshot_id: str,
        action: str,
        model_confidence: float,
        live_quality_score: float,
        uncertainty: float,
        reason_codes: Iterable[str],
        horizon_close: datetime,
    ) -> str:
        payload = {
            "schema_version": _SCHEMA_VERSION,
            "record_type": "observation",
            "symbol": symbol,
            "event_time": _iso(event_time),
            "market_snapshot_id": market_snapshot_id,
            "action": action,
            "model_confidence": float(model_confidence),
            "live_quality_score": float(live_quality_score),
            "uncertainty": float(uncertainty),
            "reason_codes": list(reason_codes),
            "horizon_close": _iso(horizon_close),
            "research_only": True,
            "production_execution_authority": False,
        }
        observation_id = _stable_id("obs", payload)
        payload["observation_id"] = observation_id
        self._append(payload)
        return observation_id

    def append_outcome(
        self,
        *,
        observation_id: str,
        now: datetime,
        horizon_close: datetime,
        tp_hit: bool,
        sl_hit: bool,
        mfe: float,
        mae: float,
        rr_outcome: str,
    ) -> str:
        if now.tzinfo is None or horizon_close.tzinfo is None:
            raise ValueError("timestamps must be timezone-aware")
        if now < horizon_close:
            raise ValueError("horizon has not closed")
        payload = {
            "schema_version": _SCHEMA_VERSION,
            "record_type": "outcome",
            "observation_id": observation_id,
            "matured_at": _iso(now),
            "horizon_close": _iso(horizon_close),
            "tp_hit": bool(tp_hit),
            "sl_hit": bool(sl_hit),
            "mfe": float(mfe),
            "mae": float(mae),
            "rr_outcome": rr_outcome,
            "research_only": True,
            "production_execution_authority": False,
        }
        outcome_id = _stable_id("out", payload)
        payload["outcome_id"] = outcome_id
        self._append(payload)
        return outcome_id
