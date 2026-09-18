"""One truthful terminal state per Wave 3 candidate, from the evidence produced.

    python AI_SKILL_LIBRARY/v4/tools/wave3_candidate_states.py --evidence /tmp/w3.json

Wave 3's exit gate requires every processed candidate to end in exactly one
state, with no ambiguous pending rows. This reads what the earlier steps
recorded - the resource preflight, the upstream discovery run, the measured
capability gap map and the Open Model Universe registry - and resolves each
candidate to one state, naming every finding that contributed.

States, in the order they are decided:

  HUMAN_LICENSE_GATE_REQUIRED  terms a person must accept. First, because no
                               other finding could make it acquirable anyway.
  RESOURCE_INFEASIBLE          measured host resources cannot hold or run it.
  AVAILABLE                    admitted, in the registry, with evidence.
  QUARANTINED_WITH_ACTIONABLE_GAP  not admitted, and what is missing is named.
                               This covers a candidate whose own author
                               publishes no ungated loadable artifact: the gap
                               is real and it is actionable - establish the
                               conversion provenance of a community build, or
                               wait for an author one - so it is a quarantine
                               rather than a new state of its own.
  RESOLVED_INCOMPATIBLE        the runtime tried and the format is refused.
  ROLE_REDUNDANT               feasible and acquirable, but every role it was
                               hypothesised for is already covered by a measured
                               run that is neither thin nor saturated.

Ordering is the substance here. A candidate can be several of these at once -
Qwen3-Coder-30B has no author-published GGUF *and* needs 18.6 GB on a host with
15.9 GB free - and reporting whichever was checked last would make the record
depend on the order of the code. The most fundamental blocker is reported as the
state; every other finding is kept beside it.

`ROLE_REDUNDANT` is deliberately last of the blocking states and requires
non-thin, non-saturated coverage. A capability where five models tie at 1.000
is not evidence that a sixth adds nothing; it is evidence that the suite cannot
tell, which is a different claim and not one that should stop an acquisition.

This tool decides nothing about admission. It reports what the gates decided.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any, Sequence

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))

import yaml  # noqa: E402

EVIDENCE = "CHECKPOINTS/evidence"
MANIFEST_REL = "AI_SKILL_LIBRARY/v4/open_model_universe/wave3_knowledge_candidates.yaml"
REGISTRY_REL = "AI_SKILL_LIBRARY/v4/open_model_universe/registry.yaml"

TERMINAL_STATES = (
    "AVAILABLE",
    "QUARANTINED_WITH_ACTIONABLE_GAP",
    "RESOLVED_INCOMPATIBLE",
    "RESOURCE_INFEASIBLE",
    "ROLE_REDUNDANT",
    "HUMAN_LICENSE_GATE_REQUIRED",
)


def _load(root: Path, name: str) -> Any:
    try:
        return json.loads((root / EVIDENCE / name).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None


def build(root: Path) -> dict[str, Any]:
    manifest = yaml.safe_load((root / MANIFEST_REL).read_text(encoding="utf-8")) or {}
    registry = yaml.safe_load((root / REGISTRY_REL).read_text(encoding="utf-8")) or {}
    by_upstream = {
        str(model.get("model_id")): model
        for model in (registry.get("models") or [])
        if isinstance(model, dict)
    }

    preflight = _load(root, "WAVE3_RESOURCE_PREFLIGHT.json") or {}
    preflight_rows = {row["candidate_id"]: row for row in preflight.get("candidates", [])}
    discovery = _load(root, "WAVE3_DISCOVERY.json") or {}
    discovery_rows = {row["candidate_id"]: row for row in discovery.get("findings", [])}
    gap_map = _load(root, "WAVE3_CAPABILITY_GAP_MAP.json") or {}
    capabilities = gap_map.get("capabilities") or {}

    rows: list[dict[str, Any]] = []
    for candidate in manifest.get("candidates", []):
        candidate_id = str(candidate.get("id"))
        upstream = str(candidate.get("upstream"))
        pre = preflight_rows.get(candidate_id) or {}
        found = discovery_rows.get(candidate_id) or {}
        record = by_upstream.get(upstream) or by_upstream.get(
            str((found.get("selected") or {}).get("repo_id"))
        )

        findings: list[str] = []
        state = None
        # Per candidate, not leaked from the previous loop iteration.
        actionable: str | None = None

        if pre.get("state") == "HUMAN_LICENSE_GATE_REQUIRED" or candidate.get(
                "state") == "HUMAN_LICENSE_GATE_REQUIRED":
            state = "HUMAN_LICENSE_GATE_REQUIRED"
            findings.extend(pre.get("reasons") or [])
        elif pre.get("state") == "RESOURCE_INFEASIBLE":
            state = "RESOURCE_INFEASIBLE"
            findings.extend(pre.get("reasons") or [])

        # Recorded whatever the state, because "we could not have run it anyway"
        # and "nobody publishes a loadable build of it" are different facts and
        # a later reader needs both.
        if found and not found.get("selected") and not found.get("skipped"):
            findings.append(found.get("conclusion") or "no loadable upstream artifact found")
            if state is None:
                state = "QUARANTINED_WITH_ACTIONABLE_GAP"
                actionable = (
                    "establish the conversion provenance of a community GGUF build "
                    "(converter, source revision, digest), or wait for the model's "
                    "own author to publish one"
                )

        if state is None and record is not None:
            lifecycle = str(record.get("lifecycle_state") or "")
            if lifecycle == "AVAILABLE":
                state = "AVAILABLE"
                findings.append("admitted with digest-bound evidence in the registry")
            elif lifecycle == "QUARANTINED":
                state = "QUARANTINED_WITH_ACTIONABLE_GAP"
                findings.append("staged and quarantined; see the registry row for what is missing")

        if state is None and pre.get("state") == "ROLE_REDUNDANT":
            # Re-checked here against the current gap map rather than trusting
            # the preflight's snapshot: a deeper suite may since have shown the
            # role was never really covered.
            still_redundant = True
            for role in pre.get("roles_hypothesised") or []:
                row = capabilities.get(role) or {}
                if (row.get("state") != "COVERED_MEASURED"
                        or row.get("thin_evidence") or row.get("saturated")):
                    still_redundant = False
                    findings.append(
                        f"{role} is {row.get('state', 'unknown')}"
                        + (" and saturated" if row.get("saturated") else "")
                        + (" on thin evidence" if row.get("thin_evidence") else "")
                        + ", so redundancy is not established"
                    )
            if still_redundant:
                state = "ROLE_REDUNDANT"
                findings.extend(pre.get("reasons") or [])

        if state is None:
            if found.get("selected"):
                state = "SELECTED_FOR_STAGING"
                selected = found["selected"]
                findings.append(
                    f"author-published artifact {selected['repo_id']}/{selected['filename']} "
                    f"at revision {str(selected['immutable_revision'])[:12]}, "
                    f"{selected['size_gb']} GB, licence {selected.get('license_declared')}"
                )
            else:
                state = "UNRESOLVED"
                findings.append("no evidence resolves this candidate; it must not stay here")

        rows.append({
            "candidate_id": candidate_id,
            "actionable_gap": actionable,
            "upstream": upstream,
            "state": state,
            "terminal": state in TERMINAL_STATES,
            "findings": findings,
            "resource_state": pre.get("state"),
            "estimated_artifact_mb": pre.get("estimated_artifact_mb"),
            "estimated_runtime_ram_mb": pre.get("estimated_runtime_ram_mb"),
            "upstream_artifact": found.get("selected"),
            "roles_hypothesised": pre.get("roles_hypothesised") or candidate.get("candidate_roles"),
            "deferred_to_wave": pre.get("deferred_to_wave"),
        })

    by_state: dict[str, list[str]] = {}
    for row in rows:
        by_state.setdefault(row["state"], []).append(row["candidate_id"])

    unresolved = [row["candidate_id"] for row in rows if not row["terminal"]]
    return {
        "tool": "wave3_candidate_states",
        "candidates": rows,
        "by_state": {state: sorted(names) for state, names in sorted(by_state.items())},
        "non_terminal": sorted(unresolved),
        "all_terminal": not unresolved,
        "sources": {
            "preflight": bool(preflight),
            "discovery": bool(discovery),
            "gap_map": bool(gap_map),
        },
        "admits_nothing": True,
        "accepts_no_licence": True,
    }


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--root", default=".")
    parser.add_argument("--evidence", default=None)
    args = parser.parse_args(argv)

    result = build(Path(args.root).resolve())
    if args.evidence:
        Path(args.evidence).write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")

    print(f"WAVE3_CANDIDATE_STATES all_terminal={result['all_terminal']} "
          f"non_terminal={result['non_terminal']}")
    for row in result["candidates"]:
        print(f"  {row['state']:<32} {row['candidate_id']}")
        for finding in row["findings"]:
            print(f"      {finding}")
    return 0 if result["all_terminal"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
