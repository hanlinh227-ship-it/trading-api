from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from jsonschema import Draft202012Validator


V4_ROOT = Path(__file__).resolve().parents[1]
LEDGER_SCHEMA_PATH = V4_ROOT / "schemas/capability_evidence_ledger.schema.json"


def _parse_timestamp(value: object) -> datetime | None:
    text = str(value or "").strip()
    if not text:
        return None
    try:
        parsed = datetime.fromisoformat(text.replace("Z", "+00:00"))
    except ValueError:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def _bounded_score(value: object) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return 0.0
    number = float(value)
    if number != number or number in {float("inf"), float("-inf")}:
        return 0.0
    return max(0.0, min(1.0, number))


def _resolve(root: Path, path: Path) -> Path:
    root = Path(root).resolve()
    path = Path(path)
    return path if path.is_absolute() else root / path


def load_capability_ledger(root: Path, ledger_path: Path) -> dict:
    """Load and strictly validate the canonical capability evidence ledger."""
    path = _resolve(root, ledger_path)
    schema_path = _resolve(root, Path("AI_SKILL_LIBRARY/v4/schemas/capability_evidence_ledger.schema.json"))
    try:
        ledger = json.loads(path.read_text(encoding="utf-8"))
        schema = json.loads(schema_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ValueError(f"capability evidence ledger load failed: {exc}") from exc
    if not isinstance(ledger, dict):
        raise ValueError("capability evidence ledger root must be an object")
    Draft202012Validator.check_schema(schema)
    errors = sorted(Draft202012Validator(schema).iter_errors(ledger), key=lambda item: list(item.path))
    if errors:
        detail = "; ".join(error.message for error in errors[:6])
        raise ValueError(f"invalid capability evidence ledger: {detail}")
    ids = [str(row.get("evidence_id")) for row in ledger.get("records", []) if isinstance(row, dict)]
    if len(ids) != len(set(ids)):
        raise ValueError("capability evidence ledger evidence_id values must be unique")
    return ledger


def index_evidence_records(ledger: dict) -> dict[tuple[str, str, str], list[dict]]:
    """Index records by exact provider/model/capability identity."""
    if not isinstance(ledger, dict):
        raise TypeError("ledger must be a mapping")
    records = ledger.get("records", [])
    if not isinstance(records, list):
        raise ValueError("ledger records must be an array")
    result: dict[tuple[str, str, str], list[dict]] = {}
    for row in records:
        if not isinstance(row, dict):
            continue
        key = (str(row.get("provider_id", "")), str(row.get("model_id", "")), str(row.get("capability", "")))
        if not all(key):
            continue
        result.setdefault(key, []).append(row)
    for rows in result.values():
        rows.sort(
            key=lambda row: (
                _parse_timestamp(row.get("measured_at")) or datetime.min.replace(tzinfo=timezone.utc),
                str(row.get("evidence_id", "")),
            ),
            reverse=True,
        )
    return result


def _provider_declaration(candidate: dict, capability: str) -> dict[str, Any] | None:
    caps = candidate.get("capabilities", {}) if isinstance(candidate, dict) else {}
    row = caps.get(capability) if isinstance(caps, dict) else None
    return row if isinstance(row, dict) else None


def capability_evidence_state(
    candidate: dict,
    capability: str,
    evidence_map: dict,
    *,
    now: str,
    freshness_hours: int,
) -> dict:
    """Return VERIFIED/PROVISIONAL/UNKNOWN/STALE for one exact candidate capability."""
    if not isinstance(candidate, dict):
        raise TypeError("candidate must be a mapping")
    capability = str(capability or "").strip()
    if not capability:
        raise ValueError("capability is required")
    if not isinstance(evidence_map, dict):
        raise TypeError("evidence_map must be a mapping")
    now_dt = _parse_timestamp(now)
    if now_dt is None:
        raise ValueError("now must be an ISO-8601 timestamp")
    if isinstance(freshness_hours, bool) or not isinstance(freshness_hours, int) or freshness_hours <= 0:
        raise ValueError("freshness_hours must be a positive integer")

    provider_id = str(candidate.get("provider_id", ""))
    model_id = str(candidate.get("model_id", ""))
    model_family = str(candidate.get("model_family", ""))
    rows = evidence_map.get((provider_id, model_id, capability), [])
    if not isinstance(rows, list):
        rows = []
    matching = [row for row in rows if isinstance(row, dict) and str(row.get("model_family", "")) == model_family]
    matching.sort(
        key=lambda row: (
            _parse_timestamp(row.get("measured_at")) or datetime.min.replace(tzinfo=timezone.utc),
            str(row.get("evidence_id", "")),
        ),
        reverse=True,
    )

    for row in matching:
        measured = _parse_timestamp(row.get("measured_at"))
        if measured is None or measured > now_dt:
            continue
        age_hours = (now_dt - measured).total_seconds() / 3600.0
        passed = row.get("passed") is True and _bounded_score(row.get("score")) >= _bounded_score(row.get("threshold"))
        if passed:
            return {
                "state": "VERIFIED" if age_hours <= freshness_hours else "STALE",
                "score": _bounded_score(row.get("score")),
                "evidence_ids": [str(row.get("evidence_id"))],
                "measured_at": str(row.get("measured_at")),
            }
        return {
            "state": "PROVISIONAL",
            "score": _bounded_score(row.get("score")),
            "evidence_ids": [str(row.get("evidence_id"))],
            "measured_at": str(row.get("measured_at")),
        }

    declaration = _provider_declaration(candidate, capability)
    if declaration is not None:
        return {
            "state": "PROVISIONAL",
            "score": _bounded_score(declaration.get("score")),
            "evidence_ids": [],
            "measured_at": None,
        }
    return {"state": "UNKNOWN", "score": 0.0, "evidence_ids": [], "measured_at": None}
