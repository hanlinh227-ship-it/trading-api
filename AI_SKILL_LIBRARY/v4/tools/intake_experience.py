from __future__ import annotations

import argparse
import json
import re
from pathlib import Path
from typing import Any


_ALLOWED = {
    "experience_id", "timestamp", "request_class", "role_id", "skill_ids",
    "model_id", "provider_id", "worker_id", "latency_ms", "success",
    "failure_class", "verifier_passed", "retry_count", "escalation_path",
    "fallback_path", "resource_observation", "quota_impact",
    "user_feedback_signal", "evidence_ref",
}
_REQUIRED = {
    "experience_id", "timestamp", "request_class", "role_id", "skill_ids",
    "model_id", "success", "verifier_passed", "retry_count", "evidence_ref",
}
_FORBIDDEN = {
    "raw_prompt", "raw_private_chat", "secret", "secrets", "credentials",
    "api_key", "private_key", "authentication_token", "hidden_reasoning",
    "chain_of_thought", "private_tool_payload", "raw_private_tool_payload",
}

_ID = re.compile(r"^@?[A-Za-z0-9][A-Za-z0-9_.:/+-]{0,127}$")
_ROLE = re.compile(r"^[A-Z][A-Z0-9_]*_BRANCH$")
_CLASS = re.compile(r"^[a-z0-9][a-z0-9_.-]{0,63}$")
_TIME = re.compile(r"^[0-9]{4}-[0-9]{2}-[0-9]{2}T[0-9]{2}:[0-9]{2}:[0-9]{2}(?:[.][0-9]{1,9})?(?:Z|[+-][0-9]{2}:[0-9]{2})$")
_REF = re.compile(r"^(?:[a-z][a-z0-9+.-]{1,31}://\S{3,223}|[A-Za-z0-9][A-Za-z0-9._/-]*/[A-Za-z0-9][A-Za-z0-9._-]*[.][A-Za-z0-9]{1,16})$")

_AUTHORITY_FLAGS = {
    "routing_authority": False,
    "reasoning_authority": False,
    "model_selection_authority": False,
    "admission_authority": False,
    "scheduling_authority": False,
    "evidence_authority": False,
    "stable_write_authority": False,
    "merge_authority": False,
    "trading_authority": False,
}


def _identifier(name: str, value: Any) -> str:
    if not isinstance(value, str) or not _ID.fullmatch(value):
        raise ValueError(f"invalid_{name}")
    return value


def _class_token(name: str, value: Any, *, allow_none: bool = False):
    if value is None and allow_none:
        return None
    if not isinstance(value, str) or not _CLASS.fullmatch(value):
        raise ValueError(f"invalid_{name}")
    return value


def _id_list(name: str, value: Any, *, max_items: int) -> list[str]:
    if not isinstance(value, list) or not value or len(value) > max_items:
        raise ValueError(f"invalid_{name}")
    rows = [_identifier(name, item) for item in value]
    if len(rows) != len(set(rows)):
        raise ValueError(f"duplicate_{name}")
    return rows


def normalize_experience(row: dict) -> dict:
    if not isinstance(row, dict):
        raise ValueError("experience_must_be_object")
    keys = set(row)
    forbidden = sorted(keys & _FORBIDDEN)
    if forbidden:
        raise ValueError("forbidden_experience_fields:" + ",".join(forbidden))
    unknown = sorted(keys - _ALLOWED)
    if unknown:
        raise ValueError("unknown_experience_fields:" + ",".join(unknown))
    missing = sorted(_REQUIRED - keys)
    if missing:
        raise ValueError("missing_experience_fields:" + ",".join(missing))

    out: dict[str, Any] = {
        "experience_id": _identifier("experience_id", row["experience_id"]),
        "timestamp": row["timestamp"],
        "request_class": _class_token("request_class", row["request_class"]),
        "role_id": row["role_id"],
        "skill_ids": _id_list("skill_ids", row["skill_ids"], max_items=32),
        "model_id": _identifier("model_id", row["model_id"]),
        "success": row["success"],
        "verifier_passed": row["verifier_passed"],
        "retry_count": row["retry_count"],
        "evidence_ref": row["evidence_ref"],
    }
    if not isinstance(out["timestamp"], str) or not _TIME.fullmatch(out["timestamp"]):
        raise ValueError("invalid_timestamp")
    if not isinstance(out["role_id"], str) or not _ROLE.fullmatch(out["role_id"]):
        raise ValueError("invalid_role_id")
    if out["success"] is not True and out["success"] is not False:
        raise ValueError("success_must_be_boolean")
    if out["verifier_passed"] not in (True, False, "unknown"):
        raise ValueError("invalid_verifier_passed")
    if not isinstance(out["retry_count"], int) or isinstance(out["retry_count"], bool) or out["retry_count"] < 0:
        raise ValueError("invalid_retry_count")
    if not isinstance(out["evidence_ref"], str) or len(out["evidence_ref"]) > 256 or not _REF.fullmatch(out["evidence_ref"]):
        raise ValueError("invalid_evidence_ref")

    for key in ("provider_id", "worker_id"):
        if key in row and row[key] is not None:
            out[key] = _identifier(key, row[key])
    if "latency_ms" in row:
        if not isinstance(row["latency_ms"], (int, float)) or isinstance(row["latency_ms"], bool) or row["latency_ms"] < 0:
            raise ValueError("invalid_latency_ms")
        out["latency_ms"] = row["latency_ms"]
    if "failure_class" in row:
        out["failure_class"] = _class_token("failure_class", row["failure_class"], allow_none=True)
    for key in ("resource_observation", "quota_impact"):
        if key in row:
            out[key] = _class_token(key, row[key])
    if "user_feedback_signal" in row:
        if row["user_feedback_signal"] not in {"none", "accepted", "rejected", "corrected", "preference_stated"}:
            raise ValueError("invalid_user_feedback_signal")
        out["user_feedback_signal"] = row["user_feedback_signal"]
    for key in ("escalation_path", "fallback_path"):
        if key in row:
            out[key] = _id_list(key, row[key], max_items=16)

    return {key: out[key] for key in sorted(out)}


def merge_experiences(ledger: dict, rows: list[dict]) -> dict:
    if not isinstance(ledger, dict) or not isinstance(rows, list):
        raise ValueError("ledger_and_rows_required")
    existing = ledger.get("experiences")
    if not isinstance(existing, list):
        raise ValueError("ledger_experiences_required")

    by_id: dict[str, dict] = {}
    for raw in existing:
        normalized = normalize_experience(raw)
        by_id[normalized["experience_id"]] = normalized

    for raw in rows:
        normalized = normalize_experience(raw)
        key = normalized["experience_id"]
        if key in by_id and by_id[key] != normalized:
            raise ValueError(f"experience_id_conflict:{key}")
        by_id[key] = normalized

    if len(by_id) > 10000:
        raise ValueError("experience_ledger_capacity_exceeded")

    return {
        "version": 1,
        "ledger_id": "EXPERIENCE_LEDGER",
        "purpose": "sanitized observable execution outcomes only",
        "authority": False,
        "stable_write": False,
        "authority_flags": dict(_AUTHORITY_FLAGS),
        "experiences": [by_id[key] for key in sorted(by_id)],
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", required=True)
    parser.add_argument("--ledger", required=True)
    parser.add_argument("--root", default=".")
    args = parser.parse_args()
    root = Path(args.root).resolve()
    input_path = (root / args.input).resolve(); input_path.relative_to(root)
    ledger_path = (root / args.ledger).resolve(); ledger_path.relative_to(root)

    payload = json.loads(input_path.read_text(encoding="utf-8"))
    rows = payload if isinstance(payload, list) else [payload]
    ledger = json.loads(ledger_path.read_text(encoding="utf-8"))
    merged = merge_experiences(ledger, rows)
    ledger_path.write_text(json.dumps(merged, indent=2, sort_keys=True, ensure_ascii=False) + "\n", encoding="utf-8")
    print(f"EXPERIENCE_INTAKE=PASS experiences={len(merged['experiences'])}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
