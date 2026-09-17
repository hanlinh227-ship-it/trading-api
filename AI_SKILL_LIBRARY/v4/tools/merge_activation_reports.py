#!/usr/bin/env python3
"""Merge Brain Expansion activation reports produced by different interpreters.

Some adapters can only prove themselves where their dependencies live. The
evaluation and typed-contract lanes run in the validator interpreter; Browser
Use needs a dedicated virtualenv that owns Playwright and a Chromium build. Each
runtime writes its own report, and this tool joins them into one activation
record without ever inventing a verdict.

The merge is deliberately suspicious of its inputs. A row may only carry
`enabled: true` into the merged report if that row proves it: every required
condition PASS, real evidence attached, and no authority claim. Anything else is
an error, not a downgrade, because a report that claims an unproven activation
is a broken producer and should stop the pipeline.

Usage:
    python AI_SKILL_LIBRARY/v4/tools/merge_activation_reports.py \
        --output merged.json --require langfuse ragas deepeval baml browser_use \
        validator.json browser.json
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any, Iterable, Sequence

AUTHORITY_CLAIMS = (
    "routing_authority",
    "reasoning_authority",
    "memory_authority",
    "model_selection_authority",
)

#: Authority fields that must agree across every report being merged.
AUTHORITY_FIELDS = (
    "router_authority",
    "execution_authority",
    "model_authority",
    "memory_authority",
)


def _rows(report: dict) -> dict:
    adapters = report.get("adapters")
    return adapters if isinstance(adapters, dict) else {}


def _runtime_label(report: dict, index: int) -> str:
    return str(report.get("runtime") or f"report_{index}")


def validate_row(adapter_id: str, row: dict, *, runtime: str) -> None:
    """Refuse a row that claims more than it proved."""
    for claim in AUTHORITY_CLAIMS:
        if row.get(claim):
            raise ValueError(f"{runtime}: {adapter_id} claims {claim}")
    if not row.get("enabled"):
        return
    if not row.get("evidence"):
        raise ValueError(f"{runtime}: {adapter_id} is enabled without evidence")
    conditions = row.get("conditions") if isinstance(row.get("conditions"), dict) else {}
    required = list(row.get("required") or [])
    if not required:
        raise ValueError(f"{runtime}: {adapter_id} is enabled with no required conditions recorded")
    unmet = [name for name in required if conditions.get(name) != "PASS"]
    if unmet:
        raise ValueError(f"{runtime}: {adapter_id} is enabled with unmet conditions {unmet}")


def merge_reports(reports: Sequence[dict]) -> dict:
    """Join activation reports from several runtimes into one.

    An adapter is enabled in the merge when some runtime proved it, and the row
    that proved it is the one that is kept, tagged with the runtime that ran it.
    """
    reports = [r for r in reports if isinstance(r, dict)]
    if not reports:
        raise ValueError("no activation reports to merge")

    authority: dict[str, Any] = {}
    for index, report in enumerate(reports):
        runtime = _runtime_label(report, index)
        for field in AUTHORITY_FIELDS:
            value = report.get(field)
            if value is None:
                continue
            if field in authority and authority[field] != value:
                raise ValueError(
                    f"{runtime}: {field} is {value!r} but another report says {authority[field]!r}"
                )
            authority[field] = value

    merged: dict[str, dict] = {}
    for index, report in enumerate(reports):
        runtime = _runtime_label(report, index)
        for adapter_id, row in _rows(report).items():
            row = dict(row) if isinstance(row, dict) else {}
            validate_row(adapter_id, row, runtime=runtime)
            row["runtime"] = runtime
            incumbent = merged.get(adapter_id)
            if incumbent is None or (row.get("enabled") and not incumbent.get("enabled")):
                merged[adapter_id] = row

    return {
        "schema_version": 1,
        "kind": "brain_expansion_activation_merged",
        "runtimes": [_runtime_label(report, index) for index, report in enumerate(reports)],
        "adapters": merged,
        "enabled": sorted(cid for cid, row in merged.items() if row.get("enabled")),
        "states": {cid: str(row.get("state") or "unknown") for cid, row in merged.items()},
        "stable_path_ok": all(bool(report.get("stable_path_ok")) for report in reports),
        **authority,
    }


def missing(merged: dict, required: Iterable[str]) -> list[str]:
    """Which required adapters did not end up enabled."""
    rows = _rows(merged)
    return sorted(name for name in required if not rows.get(name, {}).get("enabled"))


def load_reports(paths: Sequence[str | Path]) -> list[dict]:
    reports = []
    for path in paths:
        text = Path(path).read_text(encoding="utf-8")
        reports.append(json.loads(text))
    return reports


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Merge Brain Expansion activation reports")
    parser.add_argument("reports", nargs="+", help="activation report JSON files")
    parser.add_argument("--output", default="")
    parser.add_argument("--require", nargs="*", default=[], help="adapter ids that must be enabled somewhere")
    args = parser.parse_args(argv)

    try:
        merged = merge_reports(load_reports(args.reports))
    except ValueError as exc:
        print(f"[ERROR] {exc}")
        return 1

    if args.output:
        out = Path(args.output)
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(json.dumps(merged, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        print(f"merged report written to {out}")

    for adapter_id in sorted(merged["adapters"]):
        row = merged["adapters"][adapter_id]
        print(f"{adapter_id:<12} {row.get('state')} enabled={row.get('enabled')} runtime={row.get('runtime')}")
    print(f"BRAIN_EXPANSION_LIVE={merged['enabled'] or 'none'}")

    unmet = missing(merged, args.require)
    if unmet:
        print(f"[ERROR] required adapters not enabled: {unmet}")
        return 1
    if not merged["stable_path_ok"]:
        print("[ERROR] stable path not ok")
        return 1
    print("BRAIN_EXPANSION_MERGE=PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
