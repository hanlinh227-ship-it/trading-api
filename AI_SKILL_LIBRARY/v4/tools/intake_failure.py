from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

DEFAULT_LEDGER = "AI_SKILL_LIBRARY/v4/learning/failure_ledger.json"
_ALLOWED = {
    "failure_id",
    "domain",
    "failure_class",
    "observable_symptom",
    "expected_outcome",
    "evidence_ref",
    "timestamp",
    "release_id",
    "client_id",
    "skill_id",
}
_FORBIDDEN = {
    "raw_prompt",
    "raw_private_chat",
    "secret",
    "secrets",
    "credentials",
    "api_key",
    "api_keys",
    "private_key",
    "private_keys",
    "authentication_token",
    "authentication_tokens",
    "hidden_reasoning",
    "chain_of_thought",
    "private_tool_payload",
    "raw_private_tool_payload",
}
_REQUIRED = {
    "failure_id",
    "domain",
    "failure_class",
    "observable_symptom",
    "expected_outcome",
    "evidence_ref",
    "timestamp",
}


def _clean_text(value: Any, name: str, limit: int) -> str:
    if not isinstance(value, str):
        raise ValueError(f"invalid_{name}")
    text = value.strip()
    if not text or len(text) > limit:
        raise ValueError(f"invalid_{name}")
    return text


def normalize_failure(row: dict) -> dict:
    if not isinstance(row, dict):
        raise ValueError("failure_must_be_object")
    keys = set(row)
    if keys & _FORBIDDEN:
        raise ValueError("forbidden_failure_field")
    unknown = keys - _ALLOWED
    if unknown:
        raise ValueError("unknown_failure_field:" + ",".join(sorted(unknown)))
    missing = _REQUIRED - keys
    if missing:
        raise ValueError("missing_failure_field:" + ",".join(sorted(missing)))

    out = {
        "failure_id": _clean_text(row["failure_id"], "failure_id", 160),
        "domain": _clean_text(row["domain"], "domain", 80),
        "failure_class": _clean_text(row["failure_class"], "failure_class", 80),
        "observable_symptom": _clean_text(row["observable_symptom"], "observable_symptom", 1200),
        "expected_outcome": _clean_text(row["expected_outcome"], "expected_outcome", 1200),
        "evidence_ref": _clean_text(row["evidence_ref"], "evidence_ref", 500),
        "timestamp": _clean_text(row["timestamp"], "timestamp", 64),
        "authority": False,
        "stable_write": False,
    }
    for key in ("release_id", "client_id", "skill_id"):
        if row.get(key) is not None:
            out[key] = _clean_text(row[key], key, 160)
    return out


def merge_failures(ledger: dict, rows: list[dict]) -> dict:
    if not isinstance(ledger, dict):
        raise ValueError("ledger_must_be_object")
    existing = ledger.get("failures", [])
    if not isinstance(existing, list):
        raise ValueError("ledger_failures_must_be_list")
    by_id: dict[str, dict] = {}
    for row in existing:
        normalized = normalize_failure({k: v for k, v in row.items() if k in _ALLOWED})
        by_id[normalized["failure_id"]] = normalized
    for row in rows:
        normalized = normalize_failure(row)
        prior = by_id.get(normalized["failure_id"])
        if prior is not None and prior != normalized:
            raise ValueError("conflicting_failure_id")
        by_id[normalized["failure_id"]] = normalized
    return {
        "version": 1,
        "authority": False,
        "stable_write": False,
        "failures": [by_id[key] for key in sorted(by_id)],
    }


def _read_rows(path: Path) -> list[dict]:
    text = path.read_text(encoding="utf-8")
    stripped = text.strip()
    if not stripped:
        return []
    try:
        value = json.loads(stripped)
    except json.JSONDecodeError:
        rows = []
        for line in text.splitlines():
            if line.strip():
                rows.append(json.loads(line))
        return rows
    if isinstance(value, list):
        return value
    if isinstance(value, dict):
        return [value]
    raise ValueError("input_json_must_be_object_or_array")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", required=True)
    parser.add_argument("--ledger", default=DEFAULT_LEDGER)
    parser.add_argument("--root", default=".")
    args = parser.parse_args()
    root = Path(args.root).resolve()
    try:
        input_path = (root / args.input).resolve()
        input_path.relative_to(root)
        ledger_path = (root / args.ledger).resolve()
        ledger_path.relative_to(root)
        ledger = json.loads(ledger_path.read_text(encoding="utf-8")) if ledger_path.is_file() else {"version": 1, "failures": []}
        merged = merge_failures(ledger, _read_rows(input_path))
        ledger_path.parent.mkdir(parents=True, exist_ok=True)
        ledger_path.write_text(json.dumps(merged, indent=2, sort_keys=True, ensure_ascii=False) + "\n", encoding="utf-8")
        print(f"FAILURE_INTAKE=PASS failures={len(merged['failures'])}")
        return 0
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        print(f"[ERROR] {exc}")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
