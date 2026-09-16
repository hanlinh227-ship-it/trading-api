from __future__ import annotations

import argparse
import json
from pathlib import Path

import yaml

from AI_SKILL_LIBRARY.v4.tools.skill_forge import triage_gap
from AI_SKILL_LIBRARY.v4.tools.upstream_watch import capability_diff, normalize_source

DEFAULT_SOURCES = "AI_SKILL_LIBRARY/v4/learning/upstream_sources.yaml"
DEFAULT_OUTPUT = "AI_SKILL_LIBRARY/v4/learning/upstream_ledger.json"


def _load_yaml(path: Path) -> dict:
    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError(f"mapping_required:{path}")
    return data


def _active_skills(root: Path) -> tuple[dict[str, dict], list[dict]]:
    catalog = _load_yaml(root / "AI_SKILL_LIBRARY/skills/catalog.yaml")
    rows = catalog.get("skills")
    if not isinstance(rows, list):
        raise ValueError("skill_catalog_rows_required")
    capabilities: dict[str, dict] = {}
    existing: list[dict] = []
    for row in rows:
        if not isinstance(row, dict) or row.get("alias_of"):
            continue
        skill_id = str(row.get("id") or "").strip()
        domain = str(row.get("domain") or "core").strip()
        if not skill_id:
            continue
        capabilities[skill_id] = {"skill_id": skill_id, "domain": domain}
        existing.append({"id": skill_id, "domain": domain, "capabilities": [skill_id]})
    existing.sort(key=lambda row: row["id"])
    return capabilities, existing


def build_ledger(root: Path, source_doc: dict | None = None) -> dict:
    root = Path(root).resolve()
    source_doc = source_doc or _load_yaml(root / DEFAULT_SOURCES)
    raw_sources = source_doc.get("sources")
    if not isinstance(raw_sources, list):
        raise ValueError("upstream_sources_rows_required")
    active_caps, existing_skills = _active_skills(root)
    source_rows: list[dict] = []
    candidate_actions: list[dict] = []

    for raw in sorted(raw_sources, key=lambda row: str(row.get("source_id") or "") if isinstance(row, dict) else ""):
        normalized = normalize_source(raw)
        domain = str(raw.get("domain") or "core").strip()
        diffs = capability_diff({"capabilities": active_caps}, raw)
        capability_rows: list[dict] = []
        for capability in sorted(diffs):
            status = diffs[capability]
            row = {
                "capability": capability,
                "status": status,
                "routing_authority": False,
                "reasoning_authority": False,
                "stable_write": False,
            }
            if normalized["state"] in {"active", "candidate"} and status in {"strengthen_existing", "distinct_candidate"}:
                gap = {
                    "gap_id": f"upstream:{normalized['source_id']}:{capability}",
                    "domain": domain,
                    "recommended_capability": capability,
                    "distinct_contract": status == "distinct_candidate",
                    "risk_class": str(raw.get("risk_class") or "A"),
                    "requires_tool_adapter": raw.get("requires_tool_adapter") is True,
                    "changes_kernel_or_router": raw.get("changes_kernel_or_router") is True,
                    "changes_security_authority": raw.get("changes_security_authority") is True,
                }
                triage = triage_gap(gap, existing_skills)
                row["triage"] = triage
                candidate_actions.append(
                    {
                        "gap_id": gap["gap_id"],
                        "source_id": normalized["source_id"],
                        "domain": domain,
                        "capability": capability,
                        "status": status,
                        "action": triage["action"],
                        "target_skill_id": triage.get("target_skill_id"),
                        "promotion_class": triage["promotion_class"],
                        "stable_write": False,
                        "routing_authority": False,
                        "reasoning_authority": False,
                    }
                )
            capability_rows.append(row)
        source_rows.append({**normalized, "domain": domain, "capability_results": capability_rows})

    candidate_actions.sort(key=lambda row: row["gap_id"])
    return {
        "version": 1,
        "authority": False,
        "routing_authority": False,
        "reasoning_authority": False,
        "stable_direct_write": False,
        "source_registry": DEFAULT_SOURCES,
        "sources": source_rows,
        "candidate_actions": candidate_actions,
    }


def _canonical_json(value: dict) -> str:
    return json.dumps(value, indent=2, sort_keys=True, ensure_ascii=False) + "\n"


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", default=".")
    parser.add_argument("--sources", default=DEFAULT_SOURCES)
    parser.add_argument("--output", default=DEFAULT_OUTPUT)
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    root = Path(args.root).resolve()
    try:
        source_path = (root / args.sources).resolve()
        source_path.relative_to(root)
        output_path = (root / args.output).resolve()
        output_path.relative_to(root)
        ledger = build_ledger(root, _load_yaml(source_path))
        text = _canonical_json(ledger)
        if args.check:
            if not output_path.is_file() or output_path.read_text(encoding="utf-8") != text:
                print("[ERROR] upstream ledger is stale; regenerate with run_upstream_watch.py")
                return 1
            print(f"UPSTREAM_WATCH=FRESH sources={len(ledger['sources'])} candidate_actions={len(ledger['candidate_actions'])}")
            return 0
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(text, encoding="utf-8")
        print(f"UPSTREAM_WATCH=WRITTEN sources={len(ledger['sources'])} candidate_actions={len(ledger['candidate_actions'])}")
        return 0
    except (OSError, ValueError, yaml.YAMLError) as exc:
        print(f"[ERROR] {exc}")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
