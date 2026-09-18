"""Can this host actually run a Wave 3 candidate, before a byte is downloaded.

    python AI_SKILL_LIBRARY/v4/tools/wave3_resource_preflight.py --evidence /tmp/pre.json

Downloading first and discovering infeasibility afterwards costs the disk twice:
once to hold an artifact that cannot be loaded, and again because the space is
gone while something feasible is waiting. This host currently reports a
CRITICAL disk watermark, so that is not hypothetical.

Every candidate is classified against measured host resources from
`detect_resources()` - never against a guess about the machine:

  RESOURCE_FEASIBLE      fits disk and RAM with headroom, on a supported backend
  RESOURCE_BORDERLINE    fits only by consuming the headroom; needs a decision
  RESOURCE_INFEASIBLE    does not fit; do not download
  BACKEND_INCOMPATIBLE   no supported local backend can load the artifact format
  ROLE_REDUNDANT         the measured fleet already covers the role
  HUMAN_LICENSE_GATE     terms a person must accept; never accepted here
  UNKNOWN                something needed is not established

**Sizes here are estimates and are labelled as such.** An artifact's real size
and digest are only known once the staging lane downloads it and reports them;
that is the number admission binds to. An estimate is enough to refuse something
that cannot possibly fit, which is all this step is for. It is never enough to
admit anything, and nothing here admits.

The RAM figure is the one that decides feasibility, not the file size: llama.cpp
maps the weights and then needs the KV cache and a compute buffer on top, so a
5 GB artifact does not run in 5 GB. The overhead is stated per candidate rather
than folded invisibly into one number.

Role redundancy is read from the measured gap map, so "we already have this"
is a claim backed by a run rather than an impression.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any, Sequence

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))

import yaml  # noqa: E402

from AI_SKILL_LIBRARY.v4.local_runtime.resources import detect_resources  # noqa: E402
from AI_SKILL_LIBRARY.v4.tools import capability_gap_map  # noqa: E402

MANIFEST_REL = "AI_SKILL_LIBRARY/v4/open_model_universe/wave3_knowledge_candidates.yaml"

#: Formats a local backend on this host can load. llama-cpp-python reads GGUF
#: and nothing else, so a safetensors upstream needs a GGUF conversion whose
#: provenance is established before it can be considered at all.
LOADABLE_FORMATS = {"gguf"}

#: Free disk that must remain after staging an artifact. Filling the disk to the
#: last byte breaks the next thing that needs to write, which on this host has
#: already happened once.
DISK_HEADROOM_MB = 3000

#: Runtime memory beyond the weights: KV cache plus compute buffer. Measured on
#: this fleet - Qwen3-4B is a 2382 MB artifact and peaked at 4722 MB - so the
#: multiplier is derived from runs on this host rather than assumed.
RUNTIME_RAM_MULTIPLIER = 2.0

#: RAM that must stay free for everything else on the host.
RAM_HEADROOM_MB = 2000

#: What each candidate would cost, and what role it is hypothesised to fill.
#: `artifact_mb` is an estimate for the quantization named; the staging lane
#: reports the real size and digest, and admission binds to those.
CANDIDATES: dict[str, dict[str, Any]] = {
    "qwen3-8b-gguf": {
        "upstream": "Qwen/Qwen3-8B-GGUF",
        "upstream_format": "gguf",
        "target_quantization": "Q4_K_M",
        "artifact_mb": 5030,
        "artifact_mb_basis": "8.2B parameters at ~4.9 bits per weight, the ratio "
                             "observed on the admitted Qwen3-4B Q4_K_M artifact",
        "roles": ["deep_reasoning", "vietnamese_reasoning", "synthesis_generalist"],
        "conversion_required": False,
    },
    "qwen3-coder-30b-a3b-instruct": {
        "upstream": "Qwen/Qwen3-Coder-30B-A3B-Instruct",
        "upstream_format": "safetensors",
        "target_quantization": "Q4_K_M",
        "artifact_mb": 18600,
        "artifact_mb_basis": "30.5B total parameters; MoE stores every expert on "
                             "disk and in memory even though only 3B are active "
                             "per token, so the sparse compute does not reduce "
                             "what has to be resident",
        "roles": ["coding", "software_engineering", "debugging", "code_review"],
        "conversion_required": True,
    },
    "gpt-oss-20b": {
        "upstream": "openai/gpt-oss-20b",
        "upstream_format": "safetensors_mxfp4",
        "target_quantization": "MXFP4",
        "artifact_mb": 12800,
        "artifact_mb_basis": "21B parameters natively quantized to MXFP4 by the "
                             "publisher; requantizing below it is not an "
                             "upstream-supported artifact",
        "roles": ["deep_reasoning", "verifier_checker", "synthesis_generalist"],
        "conversion_required": True,
    },
    "phi-4-mini-instruct": {
        "upstream": "microsoft/Phi-4-mini-instruct",
        "upstream_format": "safetensors",
        "target_quantization": "Q4",
        "artifact_mb": 2500,
        "artifact_mb_basis": "3.8B parameters at ~5 bits per weight, the ratio "
                             "observed on the admitted Phi-3-mini Q4 artifact",
        "roles": ["verifier_checker", "fast_low_resource_worker",
                  "multilingual_reasoning"],
        "conversion_required": True,
    },
    "deepseek-r1-distill-qwen-7b": {
        "upstream": "deepseek-ai/DeepSeek-R1-Distill-Qwen-7B",
        "upstream_format": "safetensors",
        "target_quantization": "Q4_K_M",
        "artifact_mb": 4680,
        "artifact_mb_basis": "7.6B parameters at ~4.9 bits per weight, the ratio "
                             "observed on the admitted Qwen3-4B Q4_K_M artifact",
        "roles": ["deep_reasoning", "verifier_checker"],
        "conversion_required": True,
    },
    "gemma-3-4b-it": {
        "upstream": "google/gemma-3-4b-it",
        "upstream_format": "safetensors_multimodal",
        "target_quantization": "Q4_K_M",
        "artifact_mb": 2600,
        "artifact_mb_basis": "4.3B parameters at ~4.9 bits per weight",
        "roles": ["multilingual_reasoning", "vision"],
        "conversion_required": True,
        "human_license_gate": "Hugging Face access requires a person to review and "
                              "accept Google's Gemma usage licence. Accepting terms "
                              "on the operator's behalf is not something this tool "
                              "may do, so the candidate stops here whatever its "
                              "resource profile.",
        "deferred_to_wave": 4,
        "deferral_reason": "Wave 3 is reasoning, coding and verification. Vision and "
                           "multimodal are Wave 4, so this candidate is out of scope "
                           "for Wave 3 independently of its licence gate.",
    },
}


def classify(candidate_id: str, spec: dict[str, Any], host: dict[str, Any],
             covered_roles: dict[str, Any]) -> dict[str, Any]:
    """One candidate's verdict, with the numbers it was decided on."""
    artifact_mb = int(spec["artifact_mb"])
    runtime_ram_mb = int(artifact_mb * RUNTIME_RAM_MULTIPLIER)
    disk_free = int(host["disk_free_mb"])
    ram_available = int(host["ram_available_mb"])

    reasons: list[str] = []
    fits_disk = artifact_mb + DISK_HEADROOM_MB <= disk_free
    fits_ram = runtime_ram_mb + RAM_HEADROOM_MB <= ram_available
    tight_disk = artifact_mb <= disk_free and not fits_disk
    tight_ram = runtime_ram_mb <= ram_available and not fits_ram

    if spec.get("human_license_gate"):
        state = "HUMAN_LICENSE_GATE_REQUIRED"
        reasons.append(spec["human_license_gate"])
        if spec.get("deferral_reason"):
            reasons.append(spec["deferral_reason"])
    elif spec["upstream_format"] not in LOADABLE_FORMATS and not spec.get("conversion_required"):
        state = "BACKEND_INCOMPATIBLE"
        reasons.append(f"{spec['upstream_format']} cannot be loaded by any backend on this host")
    elif not fits_disk and not tight_disk:
        state = "RESOURCE_INFEASIBLE"
        reasons.append(
            f"needs ~{artifact_mb} MB on disk and {disk_free} MB is free; downloading it "
            f"would fill the disk before the file finished"
        )
    elif not fits_ram and not tight_ram:
        state = "RESOURCE_INFEASIBLE"
        reasons.append(
            f"needs ~{runtime_ram_mb} MB resident (weights plus KV cache and compute "
            f"buffer) and {ram_available} MB is available"
        )
    elif tight_disk or tight_ram:
        state = "RESOURCE_BORDERLINE"
        if tight_disk:
            reasons.append(
                f"fits on disk ({artifact_mb} MB of {disk_free} MB free) only by "
                f"consuming the {DISK_HEADROOM_MB} MB headroom"
            )
        if tight_ram:
            reasons.append(
                f"fits in RAM ({runtime_ram_mb} MB of {ram_available} MB) only by "
                f"consuming the {RAM_HEADROOM_MB} MB headroom"
            )
    else:
        state = "RESOURCE_FEASIBLE"

    # Redundancy is only worth reporting for a candidate that could otherwise
    # proceed, and it is read from measurements rather than asserted.
    redundancy = []
    for role in spec["roles"]:
        row = covered_roles.get(role) or {}
        if row.get("state") == "COVERED_MEASURED" and not row.get("thin_evidence"):
            redundancy.append({
                "role": role,
                "covered_by": row.get("current_best_model"),
                "measured_score": row.get("measured_score"),
                "measurement_depth": row.get("measurement_depth"),
            })
    uncovered = [
        role for role in spec["roles"]
        if (covered_roles.get(role) or {}).get("state") != "COVERED_MEASURED"
        or (covered_roles.get(role) or {}).get("thin_evidence")
    ]
    if state == "RESOURCE_FEASIBLE" and not uncovered and redundancy:
        state = "ROLE_REDUNDANT"
        reasons.append(
            "every hypothesised role is already covered by a measured run with "
            "non-thin evidence: " + ", ".join(
                f"{row['role']} by {row['covered_by']} at {row['measured_score']}"
                for row in redundancy
            )
        )

    return {
        "candidate_id": candidate_id,
        "upstream": spec["upstream"],
        "state": state,
        "reasons": reasons,
        "roles_hypothesised": spec["roles"],
        "roles_not_yet_covered_or_thin": uncovered,
        "roles_already_covered": redundancy,
        "estimated_artifact_mb": artifact_mb,
        "estimate_basis": spec["artifact_mb_basis"],
        "estimated_runtime_ram_mb": runtime_ram_mb,
        "target_quantization": spec["target_quantization"],
        "upstream_format": spec["upstream_format"],
        "conversion_required": bool(spec.get("conversion_required")),
        "backend": "llama.cpp via llama-cpp-python" if spec["upstream_format"] in LOADABLE_FORMATS
                   or spec.get("conversion_required") else None,
        "deferred_to_wave": spec.get("deferred_to_wave"),
        # Stated on every row so no reader mistakes the estimate for the record.
        "sizes_are_estimates": True,
        "admission_binds_to": "the size and digest the staging lane reports, not these numbers",
    }


def build(root: Path) -> dict[str, Any]:
    resources = detect_resources()
    host = resources if isinstance(resources, dict) else resources.to_dict()
    gap_map = capability_gap_map.build(root)
    covered = gap_map["capabilities"]

    manifest = yaml.safe_load((root / MANIFEST_REL).read_text(encoding="utf-8")) or {}
    declared = {str(row.get("id")) for row in (manifest.get("candidates") or [])}
    unknown = sorted(set(CANDIDATES) - declared)
    missing = sorted(declared - set(CANDIDATES))

    rows = [classify(name, spec, host, covered) for name, spec in sorted(CANDIDATES.items())]
    by_state: dict[str, list[str]] = {}
    for row in rows:
        by_state.setdefault(row["state"], []).append(row["candidate_id"])

    return {
        "tool": "wave3_resource_preflight",
        "host": {
            "ram_total_mb": host["ram_total_mb"],
            "ram_available_mb": host["ram_available_mb"],
            "disk_free_mb": host["disk_free_mb"],
            "disk_watermark": host["disk_watermark"],
            "gpus": host["gpus"],
            "total_vram_available_mb": host["total_vram_available_mb"],
            "cpu_logical": host["cpu_logical"],
            "detected_at": host["detected_at"],
        },
        "policy": {
            "disk_headroom_mb": DISK_HEADROOM_MB,
            "ram_headroom_mb": RAM_HEADROOM_MB,
            "runtime_ram_multiplier": RUNTIME_RAM_MULTIPLIER,
            "loadable_formats": sorted(LOADABLE_FORMATS),
        },
        "candidates_not_in_manifest": unknown,
        "manifest_candidates_not_classified": missing,
        "by_state": {state: sorted(names) for state, names in sorted(by_state.items())},
        "candidates": rows,
        "acquires_nothing": True,
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

    host = result["host"]
    print(f"WAVE3_PREFLIGHT disk_free={host['disk_free_mb']}MB "
          f"({host['disk_watermark']}) ram_available={host['ram_available_mb']}MB "
          f"gpus={len(host['gpus'])}")
    for row in result["candidates"]:
        print(f"  {row['state']:<28} {row['candidate_id']:<32} "
              f"~{row['estimated_artifact_mb']}MB disk / ~{row['estimated_runtime_ram_mb']}MB RAM")
        for reason in row["reasons"]:
            print(f"      {reason}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
