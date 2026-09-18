"""Does every admitted, active local model actually have a role?

    python AI_SKILL_LIBRARY/v4/tools/local_model_role_closure.py

`NO_UNMAPPED_ACTIVE_MODEL` has been asserted more than once without being
computed. This computes it, from the two canonical documents that already
exist, and from nothing else:

* ``AI_SKILL_LIBRARY/v4/open_model_universe/registry.yaml`` - which local models
  were admitted, and what lifecycle state each one is in;
* ``CHECKPOINTS/evidence/ROLE_CAPABILITY_MATRIX.json`` - which models a role
  branch actually names, in which slot.

There is deliberately **no override table**. A model's state here is a function
of what the registry says about it and whether a role branch names it; there is
nowhere to type an answer in. A test asserts the module defines no such
mapping, because the one thing that would make this flag meaningless is a place
to write the flag.

Role assignment is never inferred from parameter count or from a model's name.
This module does not assign roles at all - it reads the assignments the role
matrix already derived from recorded runs, and reports which admitted models
those assignments leave out.

**This tool decides nothing.** It admits no model, maps no role, routes nothing
and promotes nothing. GITHUB_BRAIN_V4 remains the only Brain, ``task_router``
the only routing authority, and Model Mesh the only model-selection authority.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any, Sequence

import yaml

REGISTRY = "AI_SKILL_LIBRARY/v4/open_model_universe/registry.yaml"
ROLE_MATRIX = "CHECKPOINTS/evidence/ROLE_CAPABILITY_MATRIX.json"

AUTHORITY = False
ROUTING_AUTHORITY = False
MODEL_SELECTION_AUTHORITY = False
ADMISSION_AUTHORITY = False

#: The five states a model may end in, each with the condition that produces it.
#: The tuple is derived from the table, so a state cannot be added to one and
#: forgotten in the other.
ROLE_STATES: dict[str, str] = {
    "PRIMARY": "a role branch names it in its primary slot",
    "SECONDARY": "a role branch names it in its secondary slot, and none names it primary",
    "FALLBACK": "a role branch names it only in a fallback or emergency_fallback slot",
    "STANDBY": "admitted and eligible, and no role branch names it in any slot",
    "QUARANTINED": "the registry's own lifecycle_state is QUARANTINED",
}
ROLE_STATE_VALUES = tuple(ROLE_STATES)

#: Slot to state, in precedence order. A model named primary somewhere is
#: PRIMARY even if another branch names it as a fallback.
#: `reserve` holds the ranked candidates no named slot takes - the matrix used
#: to discard them, which is why a measured model could read as unmapped. A
#: reserve entry is a fallback path in the plain sense: the branch reaches it
#: when everything above it is gone.
SLOT_PRECEDENCE = (("primary", "PRIMARY"),
                   ("secondary", "SECONDARY"),
                   ("fallback", "FALLBACK"),
                   ("emergency_fallback", "FALLBACK"),
                   ("reserve", "FALLBACK"))
SLOTS = tuple(slot for slot, _ in SLOT_PRECEDENCE)

#: A model counts as ACTIVE only if the registry says both. `lifecycle_state`
#: alone is not enough: a row can read AVAILABLE while the mesh has ruled it
#: ineligible, and an ineligible model is not one the federation is failing to
#: use.
ACTIVE_LIFECYCLE = "AVAILABLE"
QUARANTINED_LIFECYCLE = "QUARANTINED"


def _load_registry(root: Path) -> list[dict[str, Any]]:
    document = yaml.safe_load((root / REGISTRY).read_text(encoding="utf-8"))
    rows = document.get("models") if isinstance(document, dict) else None
    return [r for r in (rows or []) if isinstance(r, dict) and r.get("model_id")]


def _load_matrix(root: Path) -> Any:
    return json.loads((root / ROLE_MATRIX).read_text(encoding="utf-8"))


def mapped_slots(matrix: Any) -> dict[str, list[dict[str, str]]]:
    """model_id -> the (branch, slot) pairs naming it. Read, never invented."""
    out: dict[str, list[dict[str, str]]] = {}
    rows = matrix.get("ROLE_CAPABILITY_MATRIX") if isinstance(matrix, dict) else None
    for row in rows or []:
        if not isinstance(row, dict):
            continue
        # `role_id` is what the matrix actually calls it. Reading `branch` or
        # `role` first meant every entry came back UNNAMED_BRANCH, which left
        # the flag correct (it counts membership, not names) and the provenance
        # useless - you could not see WHICH branch was keeping a model mapped.
        branch = str(row.get("role_id") or row.get("branch")
                     or row.get("role") or "UNNAMED_BRANCH")
        for slot in SLOTS:
            candidate = row.get(slot)
            # `reserve` is a list; the four named slots hold one candidate each.
            entries = candidate if isinstance(candidate, list) else [candidate]
            for entry in entries:
                model_id = None
                if isinstance(entry, dict):
                    model_id = entry.get("model_id")
                elif isinstance(entry, str) and entry:
                    model_id = entry
                if model_id:
                    out.setdefault(str(model_id), []).append(
                        {"branch": branch, "slot": slot})
    return out


def classify(row: dict[str, Any], slots: list[dict[str, str]]) -> str:
    """One of ROLE_STATES, from the registry row and the slots naming it."""
    if row.get("lifecycle_state") == QUARANTINED_LIFECYCLE:
        return "QUARANTINED"
    held = {entry["slot"] for entry in slots}
    for slot, state in SLOT_PRECEDENCE:
        if slot in held:
            return state
    return "STANDBY"


def is_active(row: dict[str, Any]) -> bool:
    return (row.get("lifecycle_state") == ACTIVE_LIFECYCLE
            and row.get("model_mesh_local_candidate_eligible") is True)


def has_measured_capability(row: dict[str, Any]) -> bool:
    """Did any benchmark record a non-zero score for this model?

    A model with nothing measured can honestly sit in STANDBY. A model with a
    measured capability and no role is the thing this flag is about.
    """
    capabilities = row.get("capabilities")
    if not isinstance(capabilities, dict):
        return False
    return any(isinstance(v, (int, float)) and v > 0 for v in capabilities.values())


def build(root: Path) -> dict[str, Any]:
    registry = _load_registry(root)
    matrix = _load_matrix(root)
    slots_by_model = mapped_slots(matrix)

    models: list[dict[str, Any]] = []
    unmapped_active: list[dict[str, Any]] = []
    for row in registry:
        model_id = str(row["model_id"])
        slots = slots_by_model.get(model_id, [])
        state = classify(row, slots)
        active = is_active(row)
        measured = has_measured_capability(row)
        record = {
            "model_id": model_id,
            "role_state": state,
            "lifecycle_state": row.get("lifecycle_state"),
            "mesh_eligible": row.get("model_mesh_local_candidate_eligible") is True,
            "active": active,
            "has_measured_capability": measured,
            "capabilities": {k: v for k, v in (row.get("capabilities") or {}).items()
                             if isinstance(v, (int, float))},
            "role_slots": slots,
        }
        models.append(record)
        if active and state == "STANDBY":
            unmapped_active.append({
                "model_id": model_id,
                "why": ("admitted, mesh-eligible and named by no role branch in any "
                        "slot" + (", with a measured capability" if measured
                                  else ", and nothing measured on it")),
                "capabilities": record["capabilities"],
            })

    return {
        "tool": "local_model_role_closure",
        "role_states": ROLE_STATES,
        "models_in_registry": len(models),
        "active_models": sum(1 for m in models if m["active"]),
        "quarantined_models": sum(1 for m in models
                                  if m["role_state"] == "QUARANTINED"),
        "NO_UNMAPPED_ACTIVE_MODEL": not unmapped_active,
        "ALL_LOCAL_MODELS_ACCOUNTED_FOR": all(
            m["role_state"] in ROLE_STATES for m in models),
        "ALL_ACTIVE_LOCAL_MODELS_ROLE_MAPPED": not unmapped_active,
        "unmapped_active_models": unmapped_active,
        "models": models,
        "note": ("Roles are read from the role matrix, which derives them from "
                 "recorded runs. Nothing here assigns a role, and nothing here "
                 "infers one from a model's size or name."),
        "authority": AUTHORITY,
        "routing_authority": ROUTING_AUTHORITY,
        "model_selection_authority": MODEL_SELECTION_AUTHORITY,
        "admission_authority": ADMISSION_AUTHORITY,
        "changes_nothing": True,
    }


def main(argv: Sequence[str] | None = None) -> int:
    repo_root = Path(__file__).resolve().parents[3]
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--root", type=Path, default=repo_root)
    parser.add_argument("--evidence", type=Path, default=None)
    args = parser.parse_args(list(argv) if argv is not None else None)

    report = build(args.root)
    if args.evidence:
        args.evidence.parent.mkdir(parents=True, exist_ok=True)
        args.evidence.write_text(
            json.dumps(report, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")

    for row in report["models"]:
        print("  %-46s %-12s active=%-5s measured=%s"
              % (row["model_id"], row["role_state"], row["active"],
                 row["has_measured_capability"]))
    for row in report["unmapped_active_models"]:
        print("  UNMAPPED_ACTIVE %s: %s" % (row["model_id"], row["why"]))
    print("ALL_LOCAL_MODELS_ACCOUNTED_FOR=%s" % report["ALL_LOCAL_MODELS_ACCOUNTED_FOR"])
    print("ALL_ACTIVE_LOCAL_MODELS_ROLE_MAPPED=%s"
          % report["ALL_ACTIVE_LOCAL_MODELS_ROLE_MAPPED"])
    print("NO_UNMAPPED_ACTIVE_MODEL=%s" % report["NO_UNMAPPED_ACTIVE_MODEL"])
    return 0 if report["NO_UNMAPPED_ACTIVE_MODEL"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
