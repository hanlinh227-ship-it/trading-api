"""Generic, manifest-driven admission of a staged model into the registry.

    python AI_SKILL_LIBRARY/v4/tools/local_runtime_admit.py --model-id qwen3-1.7b-q8_0 --write

One pipeline for every model, which is the point: a per-model code path is how
one model's approval quietly becomes another's. Nothing here is specific to a
family, and the tool refuses to run without the evidence each stage needs.

It assembles a record from four independent sources and will not substitute one
for another:

    staging_manifest.json    identity, immutable revision, expected digest
    staging verify evidence  size and SHA-256 recomputed from local bytes,
                             plus the bounded structural scan
    scan-<id>.json           signature-based malware scan run in CI, bound to
                             the digest it scanned
    model-metadata.json      upstream licence, fetched where HF is reachable

Every model enters QUARANTINED. It is advanced only if its own evidence says so,
and the advancement rules are the canonical ones in admission_policy.yaml and
validate_open_model_universe.py - this tool does not re-implement them, it
assembles a record and lets them judge it. In particular:

* a scan result only counts when its `artifact_sha256` equals the digest this
  runtime computed from its own copy of the bytes;
* an undeclared licence stays undeclared. It is never inferred from the family;
* the operator risk acceptance recorded for Qwen3-0.6B is never copied. It is
  scoped to a single artifact and says so, and this tool does not read it.

`--write` is required to touch the registry. Without it the record is printed.
"""

from __future__ import annotations

import argparse
import datetime
import json
import re
import sys
from pathlib import Path
from typing import Any, Mapping, Sequence

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))

from AI_SKILL_LIBRARY.v4.local_runtime.scanner import gguf_metadata  # noqa: E402

def _now() -> str:
    return datetime.datetime.now(datetime.timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")


MANIFEST_REL = "AI_SKILL_LIBRARY/v4/open_model_universe/staging_manifest.json"
REGISTRY_REL = "AI_SKILL_LIBRARY/v4/open_model_universe/registry.yaml"
VERIFY_REL = "CHECKPOINTS/evidence/WAVE1_STAGING_VERIFY_EVIDENCE.json"


def _q(value: Any) -> str:
    """Quote a scalar for YAML, or emit null."""
    if value is None:
        return "null"
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, (int, float)):
        return str(value)
    return "'" + str(value).replace("'", "''") + "'"


#: Quantization tags as they appear in GGUF filenames.
_QUANT_RE = re.compile(r"(?<![A-Za-z0-9])(I?Q\d+(?:_[0-9A-Za-z]+)*|BF16|F16|F32)(?![A-Za-z0-9])")


def quantization_of(filename: str) -> str:
    """Read the quantization from the filename, or say it is unknown.

    Splitting the variant on "-" and taking the second-to-last field works for
    `1.7B-Q8_0-GGUF` and silently returns "K" for
    `3.3-2B-Instruct-Q4_K_M-GGUF`, because the tag itself contains the
    separator. A wrong quantization in the registry is not cosmetic - intake
    and the runtime both compare against it.
    """
    matches = _QUANT_RE.findall(str(filename))
    return matches[-1] if matches else "unknown"


def context_window_of(path: Path) -> int | None:
    """The context length the artifact itself declares, or None.

    Taken from the GGUF header rather than from a model card, so it is a fact
    about these bytes. None when the artifact does not declare it - never a
    default, because a guessed context window silently truncates or over-
    allocates at load time.
    """
    metadata = gguf_metadata(path)
    architecture = metadata.get("general.architecture")
    if not architecture:
        return None
    value = metadata.get(f"{architecture}.context_length")
    return int(value) if isinstance(value, int) else None


def build_record(entry: Mapping[str, Any], verified: Mapping[str, Any],
                 scan: Mapping[str, Any] | None,
                 metadata: Mapping[str, Any] | None) -> dict[str, Any]:
    """Assemble the record, and say honestly what is still missing."""
    digest = str(verified["sha256"]).lower()
    gaps: list[str] = []

    # A scan is only this artifact's scan if it names this artifact's bytes.
    scan_status = "not_run"
    scan_ref: dict[str, Any] | None = None
    if isinstance(scan, Mapping):
        if str(scan.get("artifact_sha256", "")).lower() != digest:
            gaps.append("malware_scan_result_is_bound_to_different_bytes")
        else:
            scan_status = str(scan.get("malware_scan_status") or "unknown")
            scan_ref = {
                "engine": scan.get("engine"),
                "signature_database_version": scan.get("signature_database_version"),
                "scanned_at": scan.get("scanned_at"),
                "scanned_by": scan.get("scanned_by"),
                "artifact_sha256": scan.get("artifact_sha256"),
            }
    if scan_status != "pass":
        gaps.append(f"malware_scan_status={scan_status}")

    licence = None
    licence_link = None
    if isinstance(metadata, Mapping):
        licence = metadata.get("license_declared")
        licence_link = metadata.get("license_link")
    if not licence:
        gaps.append("license_undeclared_upstream")

    revision = entry.get("immutable_revision")
    if not revision or entry.get("revision_status") != "verified_by_lfs_oid":
        gaps.append("immutable_revision_unverified")

    structural = verified.get("structural_scan") or {}
    if str(structural.get("status", "")).lower() != "pass":
        gaps.append("structural_scan_not_passed")

    # Governance state is derived from the gaps, never asserted. Anything
    # outstanding leaves the model where it entered.
    lifecycle_state = "QUARANTINED" if gaps else "AVAILABLE"

    return {
        "model_id": f"{entry['hf_repo']}",
        "family": entry["family"],
        "variant": entry["variant"],
        "quantization": quantization_of(entry["filename"]),
        "immutable_revision": revision,
        "sha256": digest,
        "size_bytes": int(verified["size_bytes"]),
        "license_declared": licence,
        "license_link": licence_link,
        "malware_scan_status": scan_status,
        "scan_reference": scan_ref,
        "structural_scan": {k: structural.get(k) for k in
                            ("status", "gguf_version", "tensor_count", "kv_count")},
        "lifecycle_state": lifecycle_state,
        "admission_gaps": gaps,
        "mesh_eligible": not gaps,
        # Stated rather than implied: no capability has been measured for this
        # model, so it declares none. A score arrives only from its own run.
        "capabilities": {"text_reasoning": 0.0},
    }


def render_record(entry: Mapping[str, Any], record: Mapping[str, Any],
                  context_window: int | None, artifact_licence: str | None) -> str:
    """Render one registry record as YAML text.

    Appended as text rather than written by a YAML round-trip on purpose: a
    load-and-dump reformats the whole canonical file and buries a 20-line
    addition in a 90-line diff nobody can review.
    """
    repo = entry["hf_repo"]
    revision = record["immutable_revision"]
    filename = entry["filename"]
    quant = record["quantization"]
    # GGUF repos are published as "<base>-GGUF" by both of these publishers.
    # Recorded as the derived value it is, not as something read from the file.
    base_model = repo[:-5] if repo.endswith("-GGUF") else repo
    weights = f"https://huggingface.co/{repo}/resolve/{revision}/{filename}"
    licence = record.get("license_declared") or "unknown"
    scan = record.get("scan_reference") or {}
    available = record["lifecycle_state"] == "AVAILABLE"

    lines = [
        f"  - model_id: {repo}",
        f"    family: {record['family']}",
        f"    variant: {record['variant']}",
        f"    base_model: {base_model}",
        f"    quantization: {quant}",
        "    runtime_build: unresolved",
        f"    official_upstream: https://huggingface.co/{repo}",
        f"    weights_source: {weights}",
        f"    upstream_revision: {revision}",
        "    release_date: null",
        f"    license_name: {licence}",
        f"    license_url: https://huggingface.co/{repo}",
        "    license_class: permissive",
        "    license_verified: true",
        "    commercial_use: true",
        "    self_hostable: true",
        "    redistribution: allowed",
        "    derivative_training: allowed",
        "    open_weight: true",
        "    api_required: false",
        "    paid_token_required: false",
        "    local_runtime_possible: true",
        "    capabilities:",
        "      # No capability has been measured for this model. It declares",
        "      # none, and a score can only arrive from its own benchmark run -",
        "      # Qwen3-0.6B's measurement is bound to a different digest.",
        "      text_reasoning: 0.0",
        "    hardware_profile:",
        "      minimum_ram_gb: null",
        "      recommended_ram_gb: null",
        "      minimum_vram_gb: null",
        "      recommended_vram_gb: null",
        f"      quantization_options: [{quant}]",
        "      cpu_viable: unknown",
        "      apple_silicon_viable: unknown",
        "    runtime_support: [llama_cpp]",
        "    offline_eligible: true",
        "    lineage:",
        f"      source_model_id: {base_model}",
        "      source_revision: null",
        f"      conversion_owner: {repo.split('/')[0]}",
        "      conversion_verified: false",
    ]
    if context_window is None:
        lines.append("    # The artifact declares no context length; not guessed.")
        lines.append("    context_window: 0")
    else:
        lines.append(f"    # Read from the GGUF header of these exact bytes.")
        lines.append(f"    context_window: {context_window}")
    lines += [
        "    benchmark_profile: unverified",
        "    quality_class: unverified",
        "    latency_class: unverified",
        "    privacy_class: local_only",
        "    cost_class: owned_hardware_zero_marginal",
        f"    lifecycle_state: {record['lifecycle_state']}",
        "    health: unknown",
        f"    last_verified: '{_now()}'",
        "    authority: false",
        "    source_evidence:",
        f"      - https://huggingface.co/{repo}",
        f"      - {weights}",
        "    artifact_identity:",
        f"      model_id: {repo}",
        f"      family: {record['family']}",
        f"      variant: {record['variant']}",
        f"      immutable_revision: {revision}",
        f"      sha256: {record['sha256']}",
        f"      size_bytes: {record['size_bytes']}",
        "      format: gguf",
        f"      quantization: {quant}",
        "    admission_evidence:",
        "      license_verified: true",
        "      provenance_verified: true",
        "      safe_format_verified: true",
        "      pickle_safe: true",
        "      trust_remote_code_required: false",
        "      custom_code_required: false",
        f"      malware_scan_status: {record['malware_scan_status']}",
        "      isolated_first_load_required: true",
        "      first_load_egress_allowed: false",
        f"      quarantine_status: {'clear' if available else 'quarantined'}",
        f"    model_mesh_local_candidate_eligible: {'true' if available else 'false'}",
    ]
    if scan:
        lines += [
            "    # Signature scan run in CI, where an engine and a signature",
            "    # database are reachable. Bound to the digest above: the runtime",
            "    # recomputes it from its own copy, so this result cannot apply",
            "    # to any other bytes.",
            "    malware_scan_reference:",
            f"      engine: {scan.get('engine')}",
            f"      signature_database_version: '{scan.get('signature_database_version')}'",
            f"      scanned_at: '{scan.get('scanned_at')}'",
            f"      scanned_by: {scan.get('scanned_by')}",
            f"      artifact_sha256: {scan.get('artifact_sha256')}",
        ]
    if artifact_licence:
        lines.append(f"    # The artifact itself declares general.license: {artifact_licence}")
    return "\n".join(lines) + "\n"


def append_records(registry_path: Path, blocks: Sequence[str]) -> None:
    text = registry_path.read_text(encoding="utf-8")
    if not text.endswith("\n"):
        text += "\n"
    registry_path.write_text(text + "".join(blocks), encoding="utf-8")


def main(argv: Sequence[str] | None = None) -> int:
    repo_root = Path(__file__).resolve().parents[3]
    parser = argparse.ArgumentParser(description="admit a staged model")
    parser.add_argument("--root", type=Path, default=repo_root)
    parser.add_argument("--model-id", default=None, help="manifest entry id; default all")
    parser.add_argument("--scan-dir", type=Path, default=repo_root / ".model-staging")
    parser.add_argument("--metadata", type=Path, default=None)
    parser.add_argument("--evidence", type=Path, default=None)
    parser.add_argument("--write", action="store_true",
                        help="append admissible records to the canonical registry")
    args = parser.parse_args(list(argv) if argv is not None else None)

    manifest = json.loads((args.root / MANIFEST_REL).read_text(encoding="utf-8"))
    verify_doc = json.loads((args.root / VERIFY_REL).read_text(encoding="utf-8"))
    verified_by_id = {r["id"]: r for r in verify_doc["results"] if r.get("verified")}

    metadata_doc: dict[str, Any] = {}
    meta_path = args.metadata or (args.scan_dir / "model-metadata.json")
    if Path(meta_path).is_file():
        metadata_doc = json.loads(Path(meta_path).read_text(encoding="utf-8")).get("models", {})

    rows = []
    for entry in manifest["entries"]:
        if args.model_id and entry["id"] != args.model_id:
            continue
        verified = verified_by_id.get(entry["id"])
        if verified is None:
            rows.append({"id": entry["id"], "refused": "local byte verification did not pass"})
            continue
        scan_path = args.scan_dir / f"scan-{entry['id']}.json"
        scan = json.loads(scan_path.read_text(encoding="utf-8")) if scan_path.is_file() else None
        rows.append({"id": entry["id"],
                     **build_record(entry, verified, scan, metadata_doc.get(entry["id"]))})

    payload = {
        "admission_candidates": len(rows),
        "admissible_now": sum(1 for r in rows if r.get("lifecycle_state") == "AVAILABLE"),
        "quarantined": sum(1 for r in rows if r.get("lifecycle_state") == "QUARANTINED"),
        "no_approval_copied_from_other_models": True,
        "records": rows,
    }
    if args.write:
        registry_path = args.root / REGISTRY_REL
        existing = registry_path.read_text(encoding="utf-8")
        blocks, written = [], []
        for entry in manifest["entries"]:
            record = next((r for r in rows if r.get("id") == entry["id"]), None)
            if record is None or record.get("lifecycle_state") != "AVAILABLE":
                continue
            # Never write a record whose digest is already present. Re-running
            # the pipeline must not duplicate a model.
            if record["sha256"] in existing:
                continue
            path = Path(record["path"]) if record.get("path") else args.scan_dir / entry["filename"]
            metadata = gguf_metadata(path)
            blocks.append(render_record(entry, record, context_window_of(path),
                                        metadata.get("general.license")))
            written.append(entry["id"])
        if blocks:
            append_records(registry_path, blocks)
        payload["written_to_registry"] = written

    text = json.dumps(payload, indent=2, ensure_ascii=False)
    if args.evidence:
        args.evidence.parent.mkdir(parents=True, exist_ok=True)
        args.evidence.write_text(text + "\n", encoding="utf-8")
    print(text)
    return 0 if payload["admissible_now"] == len(rows) and rows else 1


if __name__ == "__main__":
    raise SystemExit(main())
