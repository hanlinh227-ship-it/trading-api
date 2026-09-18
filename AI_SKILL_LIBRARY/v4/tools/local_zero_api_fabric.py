"""Can this fleet run with no API key, no subscription, and no provider at all?

    python AI_SKILL_LIBRARY/v4/tools/local_zero_api_fabric.py

Computed from the registry, never asserted. Every field this reads already
exists on all ten admitted local models, and the tool refuses a model whose row
does not carry them rather than defaulting them to the convenient answer.

The distinction the brief insists on, and the one this tool is built around:

  a runtime and a set of pinned open weights can run indefinitely with no
  recurring fee. That is a property of the software and the artifact.

  a download URL continuing to exist is a property of somebody else's server.

Those are not the same claim, and the second is not this repository's to make.
So `LOCAL_ZERO_API_PATH_AVAILABLE` is about artifacts, licences and runtimes -
things the architecture controls - while `ARTIFACT_SOURCE_PERMANENCE_CLAIMED` is
hard-coded False, with a test that says it must stay that way. Durability comes
from pinned identity plus verified copies, not from a vendor's goodwill.

Equally: being allowed to run offline is not the same as having run offline.
`LOCAL_OFFLINE_EXECUTION_VERIFIED` is false until a run with egress denied
produces evidence, and no amount of clean licence metadata moves it.

**This tool decides nothing.** GITHUB_BRAIN_V4 remains the only Brain,
task_router the only routing authority, Model Mesh the only model-selection
authority.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any, Sequence

import yaml

REGISTRY = "AI_SKILL_LIBRARY/v4/open_model_universe/registry.yaml"
EVIDENCE = "CHECKPOINTS/evidence"
LIVENESS_FILE = "WORKER_EXECUTION_LIVENESS.json"

AUTHORITY = False
ROUTING_AUTHORITY = False
MODEL_SELECTION_AUTHORITY = False

#: Never true from metadata. A vendor's current terms are not a guarantee, and
#: this repository cannot make one on their behalf.
ARTIFACT_SOURCE_PERMANENCE_CLAIMED = False

#: Licence states, and the condition for each. Derived tuple, as everywhere.
LICENSE_STATES: dict[str, str] = {
    "LICENSE_ACCEPTED": "the row records a verified permissive licence that allows "
                        "the intended local use and redistribution of the artifact",
    "LICENSE_REVIEW_REQUIRED": "the row carries a licence that is unverified, "
                               "non-permissive, or silent on something this use needs",
    "LICENSE_BLOCKED": "the row records a licence that forbids this use, or one "
                       "requiring a payment that would make it not zero-cost",
}
LICENSE_STATE_VALUES = tuple(LICENSE_STATES)

#: The separate properties the brief asks not to be conflated. Each is read from
#: its own field; none is inferred from another.
ARTIFACT_PROPERTIES: dict[str, str] = {
    "OPEN_WEIGHTS": "open_weight is true: the parameters themselves are published",
    "OPEN_SOURCE_RUNTIME": "every runtime in runtime_support is an open-source engine",
    "FREE_DOWNLOAD": "paid_token_required is false",
    "PERMISSIVE_LICENSE": "license_class is permissive and license_verified is true",
    "RESTRICTED_LICENSE": "license_class is not permissive",
    "ACCOUNT_GATED_DOWNLOAD": "api_required is true for the download itself",
}
ARTIFACT_PROPERTY_VALUES = tuple(ARTIFACT_PROPERTIES)

#: Engines whose core execution needs no paid cloud service. A runtime absent
#: from this set is not thereby paid - it is unclassified, and says so.
OPEN_SOURCE_RUNTIMES = ("llama_cpp", "llama.cpp", "transformers", "pytorch",
                        "onnxruntime", "whisper_cpp", "ollama")

#: Fields that must be present. A row missing one is reported, never defaulted:
#: defaulting an absent field is how "no evidence" becomes "no problem".
REQUIRED_FIELDS = ("model_id", "api_required", "paid_token_required",
                   "offline_eligible", "license_verified", "license_class",
                   "open_weight", "local_runtime_possible", "redistribution",
                   "runtime_support", "lifecycle_state", "artifact_identity")


def license_state(row: dict[str, Any]) -> str:
    if row.get("paid_token_required") is True:
        return "LICENSE_BLOCKED"
    if row.get("license_verified") is not True:
        return "LICENSE_REVIEW_REQUIRED"
    if row.get("license_class") != "permissive":
        return "LICENSE_REVIEW_REQUIRED"
    if row.get("redistribution") not in ("allowed", "allowed_with_attribution"):
        return "LICENSE_REVIEW_REQUIRED"
    return "LICENSE_ACCEPTED"


def artifact_properties(row: dict[str, Any]) -> dict[str, bool]:
    runtimes = row.get("runtime_support") or []
    return {
        "OPEN_WEIGHTS": row.get("open_weight") is True,
        "OPEN_SOURCE_RUNTIME": bool(runtimes) and all(
            str(r) in OPEN_SOURCE_RUNTIMES for r in runtimes),
        "FREE_DOWNLOAD": row.get("paid_token_required") is False,
        "PERMISSIVE_LICENSE": (row.get("license_class") == "permissive"
                               and row.get("license_verified") is True),
        "RESTRICTED_LICENSE": row.get("license_class") != "permissive",
        "ACCOUNT_GATED_DOWNLOAD": row.get("api_required") is True,
    }


def digest_bound(row: dict[str, Any]) -> bool:
    identity = row.get("artifact_identity") or {}
    return (len(str(identity.get("sha256") or "")) == 64
            and bool(identity.get("immutable_revision"))
            and isinstance(identity.get("size_bytes"), int))


def build(root: Path) -> dict[str, Any]:
    document = yaml.safe_load((root / REGISTRY).read_text(encoding="utf-8"))
    rows = [r for r in (document.get("models") or []) if isinstance(r, dict)]

    models: list[dict[str, Any]] = []
    incomplete: list[dict[str, Any]] = []
    for row in rows:
        missing = [f for f in REQUIRED_FIELDS if f not in row]
        if missing:
            incomplete.append({"model_id": row.get("model_id"), "missing": missing})
            continue
        state = license_state(row)
        properties = artifact_properties(row)
        active = (row.get("lifecycle_state") == "AVAILABLE"
                  and row.get("model_mesh_local_candidate_eligible") is True)
        models.append({
            "model_id": row["model_id"],
            "lifecycle_state": row["lifecycle_state"],
            "active": active,
            "license_name": row.get("license_name"),
            "license_state": state,
            "artifact_properties": properties,
            "api_required": row["api_required"] is True,
            "paid_token_required": row["paid_token_required"] is True,
            "offline_eligible": row["offline_eligible"] is True,
            "local_runtime_possible": row["local_runtime_possible"] is True,
            "runtime_support": list(row.get("runtime_support") or []),
            "digest_bound": digest_bound(row),
            "immutable_revision": (row.get("artifact_identity") or {}).get(
                "immutable_revision"),
            "source_repository": row.get("official_upstream"),
        })

    # A model that can be executed with no key, no subscription and no provider.
    def zero_api(record: dict[str, Any]) -> bool:
        return (record["active"]
                and not record["api_required"]
                and not record["paid_token_required"]
                and record["offline_eligible"]
                and record["local_runtime_possible"]
                and record["license_state"] == "LICENSE_ACCEPTED"
                and record["digest_bound"]
                and record["artifact_properties"]["OPEN_SOURCE_RUNTIME"])

    usable = [m for m in models if zero_api(m)]

    # Whether this HOST can execute is a separate question from whether the
    # fleet is free of providers, and the two must not be run together.
    liveness_path = root / EVIDENCE / LIVENESS_FILE
    engine_state = None
    if liveness_path.is_file():
        try:
            engine_state = json.loads(
                liveness_path.read_text(encoding="utf-8")).get("execution_liveness")
        except ValueError:
            engine_state = None

    return {
        "tool": "local_zero_api_fabric",
        "license_states": LICENSE_STATES,
        "artifact_properties_vocabulary": ARTIFACT_PROPERTIES,
        "models_in_registry": len(rows),
        "models_read": len(models),
        "rows_with_missing_fields": incomplete,
        "zero_api_usable_models": [m["model_id"] for m in usable],

        # An API key, a subscription or a provider is needed by NO admitted
        # model. These are three separate reads, not one restated three times.
        "LOCAL_API_KEY_REQUIRED": any(m["api_required"] for m in models),
        "LOCAL_SUBSCRIPTION_REQUIRED": any(m["paid_token_required"] for m in models),
        "LOCAL_PROVIDER_DEPENDENCY": not all(
            m["offline_eligible"] and m["local_runtime_possible"] for m in models),

        "LOCAL_ZERO_API_PATH_AVAILABLE": bool(usable) and not incomplete,
        "LOCAL_ARTIFACTS_DIGEST_BOUND": bool(models) and all(
            m["digest_bound"] for m in models),
        "LOCAL_LICENSES_VALIDATED": bool(models) and all(
            m["license_state"] == "LICENSE_ACCEPTED" for m in models),
        "ALL_ADMITTED_LOCAL_MODELS_ACCOUNTED_FOR": not incomplete,

        # Permission is not performance. This stays false until a run with
        # egress denied produces evidence on a host whose engine executes.
        "LOCAL_OFFLINE_EXECUTION_VERIFIED": False,
        "offline_execution_blocker": (
            "no offline run has been recorded; the engine on the last observed "
            "host reports %s" % (engine_state or "no reading")),
        "observed_engine_state": engine_state,

        # Section 40, stated rather than left to be inferred from the rest.
        "ARTIFACT_SOURCE_PERMANENCE_CLAIMED": ARTIFACT_SOURCE_PERMANENCE_CLAIMED,
        "permanence_note": (
            "A runtime and pinned open weights can run indefinitely with no "
            "recurring fee; a download URL continuing to exist is somebody "
            "else's server. This tool claims the first and never the second. "
            "Durability comes from pinned identity, verified Storage Mesh "
            "copies and provider-independent model identity."),

        "authority": AUTHORITY,
        "routing_authority": ROUTING_AUTHORITY,
        "model_selection_authority": MODEL_SELECTION_AUTHORITY,
        "changes_nothing": True,
        "models": models,
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
        print("  %-46s %-24s active=%-5s digest_bound=%s"
              % (row["model_id"], row["license_state"], row["active"],
                 row["digest_bound"]))
    for flag in ("LOCAL_ZERO_API_PATH_AVAILABLE", "LOCAL_API_KEY_REQUIRED",
                 "LOCAL_SUBSCRIPTION_REQUIRED", "LOCAL_PROVIDER_DEPENDENCY",
                 "LOCAL_ARTIFACTS_DIGEST_BOUND", "LOCAL_LICENSES_VALIDATED",
                 "ALL_ADMITTED_LOCAL_MODELS_ACCOUNTED_FOR",
                 "LOCAL_OFFLINE_EXECUTION_VERIFIED",
                 "ARTIFACT_SOURCE_PERMANENCE_CLAIMED"):
        print("%s=%s" % (flag, report[flag]))
    return 0 if report["LOCAL_ZERO_API_PATH_AVAILABLE"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
