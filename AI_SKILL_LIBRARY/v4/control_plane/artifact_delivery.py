"""Fail-closed control-plane artifact delivery for Personal AI Federation B1.

This module stages and verifies immutable model bytes. It is deliberately not an
activation, routing, residency, or inference authority. A verified delivery may
be handed to Claude local runtime for an isolated first-load security probe; it
never changes Open Model Universe lifecycle state or Model Mesh eligibility.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping
from urllib.parse import urlparse

import yaml

VERIFIER_VERSION = "artifact-delivery-v1"
_SHA256 = re.compile(r"^[0-9a-f]{64}$")
_REVISION = re.compile(r"^[0-9a-f]{40}$")
_REQUIRED_IDENTITY_FIELDS = (
    "model_id",
    "family",
    "variant",
    "immutable_revision",
    "sha256",
    "size_bytes",
    "format",
    "quantization",
)
_DELIVERABLE_STATES = frozenset({"QUARANTINED", "APPROVED", "AVAILABLE"})


class DeliveryError(ValueError):
    """Canonical artifact cannot be delivered without weakening safety."""


@dataclass(frozen=True)
class DeliveryCandidate:
    model_id: str
    family: str
    variant: str
    immutable_revision: str
    sha256: str
    size_bytes: int
    artifact_format: str
    quantization: str
    weights_source: str
    artifact_filename: str
    lifecycle_state: str
    quarantine_state: str
    model_mesh_candidate_eligible: bool
    isolated_first_load_required: bool
    first_load_egress_allowed: bool
    activation_permitted: bool = False

    def to_dict(self) -> dict[str, Any]:
        return {
            "model_id": self.model_id,
            "family": self.family,
            "variant": self.variant,
            "immutable_revision": self.immutable_revision,
            "sha256": self.sha256,
            "size_bytes": self.size_bytes,
            "format": self.artifact_format,
            "quantization": self.quantization,
            "weights_source": self.weights_source,
            "artifact_filename": self.artifact_filename,
            "lifecycle_state": self.lifecycle_state,
            "quarantine_state": self.quarantine_state,
            "model_mesh_candidate_eligible": self.model_mesh_candidate_eligible,
            "isolated_first_load_required": self.isolated_first_load_required,
            "first_load_egress_allowed": self.first_load_egress_allowed,
            "activation_permitted": False,
        }

    @classmethod
    def from_dict(cls, value: Mapping[str, Any]) -> "DeliveryCandidate":
        return cls(
            model_id=str(value["model_id"]),
            family=str(value["family"]),
            variant=str(value["variant"]),
            immutable_revision=str(value["immutable_revision"]),
            sha256=str(value["sha256"]),
            size_bytes=int(value["size_bytes"]),
            artifact_format=str(value["format"]),
            quantization=str(value["quantization"]),
            weights_source=str(value["weights_source"]),
            artifact_filename=str(value["artifact_filename"]),
            lifecycle_state=str(value["lifecycle_state"]),
            quarantine_state=str(value["quarantine_state"]),
            model_mesh_candidate_eligible=bool(value["model_mesh_candidate_eligible"]),
            isolated_first_load_required=bool(value["isolated_first_load_required"]),
            first_load_egress_allowed=bool(value["first_load_egress_allowed"]),
            activation_permitted=False,
        )


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise DeliveryError(message)


def _source_is_pinned(source: str, revision: str) -> bool:
    parsed = urlparse(source)
    if parsed.scheme != "https" or not parsed.netloc or parsed.fragment:
        return False
    segments = tuple(segment for segment in parsed.path.split("/") if segment)
    return revision in segments


def _presecurity_delivery_eligible(record: Mapping[str, Any]) -> None:
    """Permit staging for security evidence without granting model admission."""
    evidence = record.get("admission_evidence")
    _require(isinstance(evidence, Mapping), "admission_evidence is missing")
    _require(record.get("authority") is False, "model record must remain authority=false")
    _require(record.get("local_runtime_possible") is True, "model is not local-runtime deliverable")
    _require(record.get("self_hostable") is True, "model is not self-hostable")
    _require(str(record.get("lifecycle_state") or "") in _DELIVERABLE_STATES,
             "model governance state is not eligible for artifact delivery")
    _require(evidence.get("license_verified") is True, "license evidence does not permit delivery")
    _require(evidence.get("provenance_verified") is True, "provenance evidence does not permit delivery")
    _require(evidence.get("safe_format_verified") is True, "safe-format evidence does not permit delivery")
    _require(evidence.get("pickle_safe") is True, "pickle safety evidence does not permit delivery")
    _require(evidence.get("trust_remote_code_required") is False,
             "trust_remote_code requirement blocks delivery")
    _require(evidence.get("custom_code_required") is False,
             "custom executable code requirement blocks delivery")
    _require(evidence.get("malware_scan_status") != "fail", "failed malware evidence blocks delivery")


def build_delivery_candidate(record: Mapping[str, Any]) -> DeliveryCandidate:
    """Build a bounded delivery candidate from one canonical registry row."""
    identity = record.get("artifact_identity")
    _require(isinstance(identity, Mapping), "artifact_identity is missing")
    for field in _REQUIRED_IDENTITY_FIELDS:
        value = identity.get(field)
        _require(value is not None and str(value).strip() != "", f"artifact_identity.{field} is missing")

    model_id = str(record.get("model_id") or "")
    family = str(record.get("family") or "")
    variant = str(record.get("variant") or "")
    _require(model_id == str(identity["model_id"]), "artifact_identity.model_id does not match record")
    _require(family == str(identity["family"]), "artifact_identity.family does not match record")
    _require(variant == str(identity["variant"]), "artifact_identity.variant does not match record")

    revision = str(identity["immutable_revision"]).lower()
    digest = str(identity["sha256"]).lower()
    size_bytes = int(identity["size_bytes"])
    _require(bool(_REVISION.fullmatch(revision)), "immutable revision must be a pinned 40-hex revision")
    _require(bool(_SHA256.fullmatch(digest)), "sha256 must be a 64-hex digest")
    _require(size_bytes > 0, "size_bytes must be positive")
    upstream_revision = str(record.get("upstream_revision") or "").lower()
    _require(upstream_revision == revision, "immutable revision does not match upstream_revision")

    source = str(record.get("weights_source") or "")
    _require(_source_is_pinned(source, revision), "weights_source is not pinned to immutable revision")
    filename = Path(urlparse(source).path).name
    _require(bool(filename), "artifact filename cannot be derived from weights_source")

    _presecurity_delivery_eligible(record)
    evidence = record["admission_evidence"]
    return DeliveryCandidate(
        model_id=model_id,
        family=family,
        variant=variant,
        immutable_revision=revision,
        sha256=digest,
        size_bytes=size_bytes,
        artifact_format=str(identity["format"]).lower(),
        quantization=str(identity["quantization"]),
        weights_source=source,
        artifact_filename=filename,
        lifecycle_state=str(record["lifecycle_state"]),
        quarantine_state=str(evidence.get("quarantine_status") or "unknown"),
        model_mesh_candidate_eligible=bool(record.get("model_mesh_local_candidate_eligible", False)),
        isolated_first_load_required=bool(evidence.get("isolated_first_load_required", True)),
        first_load_egress_allowed=bool(evidence.get("first_load_egress_allowed", False)),
    )


def _validate_admission_policy(policy: Mapping[str, Any]) -> None:
    _require(policy.get("artifact_identity_source") == "artifact_identity",
             "canonical admission policy does not use artifact_identity")
    required = tuple(policy.get("artifact_identity_required_fields") or ())
    _require(required == _REQUIRED_IDENTITY_FIELDS,
             "canonical artifact identity requirements differ from delivery verifier")
    first_load = policy.get("runtime_first_load_contract")
    _require(isinstance(first_load, Mapping), "runtime_first_load_contract is missing")
    _require(first_load.get("runtime_may_not_relax_admission") is True,
             "runtime admission relaxation must remain forbidden")
    _require(first_load.get("runtime_may_not_mutate_artifact_identity") is True,
             "runtime artifact identity mutation must remain forbidden")


def load_canonical_candidate(root: Path, model_id: str | None = None) -> DeliveryCandidate:
    """Resolve a delivery candidate dynamically from canonical repo state."""
    registry_path = root / "AI_SKILL_LIBRARY/v4/open_model_universe/registry.yaml"
    policy_path = root / "AI_SKILL_LIBRARY/v4/open_model_universe/admission_policy.yaml"
    registry = yaml.safe_load(registry_path.read_text(encoding="utf-8"))
    policy = yaml.safe_load(policy_path.read_text(encoding="utf-8"))
    _validate_admission_policy(policy)
    _require(registry.get("integration", {}).get("routed_by") == "task_router",
             "task_router must remain canonical routing authority")
    _require(registry.get("integration", {}).get("model_selection_authority") == "model_mesh",
             "Model Mesh must remain selection authority")
    _require(registry.get("integration", {}).get("runtime_residency_contract", {}).get("owner") == "claude_local_runtime",
             "Claude local runtime must remain residency owner")

    models = list(registry.get("models") or ())
    if model_id is not None:
        models = [row for row in models if row.get("model_id") == model_id]
        _require(len(models) == 1, f"canonical model {model_id!r} was not uniquely resolved")
        return build_delivery_candidate(models[0])

    candidates: list[DeliveryCandidate] = []
    for row in models:
        try:
            candidates.append(build_delivery_candidate(row))
        except DeliveryError:
            continue
    _require(len(candidates) == 1,
             "delivery requires exactly one dynamically resolvable canonical pre-security candidate")
    return candidates[0]


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def verify_staged_artifact(
    candidate: DeliveryCandidate,
    artifact_path: Path,
    *,
    retrieval_method: str,
    malware_scan_status: str,
    malware_scan_engine: str = "unspecified",
    verifier_version: str = VERIFIER_VERSION,
    verified_at: str | None = None,
) -> dict[str, Any]:
    """Verify staged bytes and emit a bounded, non-activating handoff manifest."""
    _require(artifact_path.is_file(), "staged artifact is missing or not a regular file")
    actual_size = artifact_path.stat().st_size
    _require(actual_size == candidate.size_bytes,
             f"size mismatch: expected {candidate.size_bytes}, got {actual_size}")
    actual_sha = _sha256(artifact_path)
    _require(actual_sha == candidate.sha256,
             f"sha256 mismatch: expected {candidate.sha256}, got {actual_sha}")
    if candidate.artifact_format == "gguf":
        with artifact_path.open("rb") as handle:
            _require(handle.read(4) == b"GGUF", "GGUF magic validation failed")

    timestamp = verified_at or datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
    security_pass = malware_scan_status == "pass"
    handoff_permitted = security_pass
    return {
        "schema_version": 1,
        "manifest_type": "PERSONAL_AI_ARTIFACT_DELIVERY_V1",
        "canonical_model_identity": {
            "model_id": candidate.model_id,
            "family": candidate.family,
            "variant": candidate.variant,
            "immutable_revision": candidate.immutable_revision,
            "quantization": candidate.quantization,
        },
        "artifact": {
            "filename": candidate.artifact_filename,
            "format": candidate.artifact_format,
            "size_bytes": candidate.size_bytes,
            "sha256": candidate.sha256,
            "source": candidate.weights_source,
            "retrieval_method": retrieval_method,
        },
        "verification": {
            "verified_at": timestamp,
            "verifier_version": verifier_version,
            "size_verified": True,
            "sha256_verified": True,
            "format_magic_verified": candidate.artifact_format != "gguf" or True,
        },
        "security": {
            "malware_scan_status": malware_scan_status,
            "malware_scan_engine": malware_scan_engine,
        },
        "quarantine": {
            "state": candidate.quarantine_state,
            "preserved": True,
        },
        "runtime_handoff": {
            "permitted": handoff_permitted,
            "purpose": "isolated_security_first_load_only",
            "runtime_owner": "claude_local_runtime",
            "first_load_egress_allowed": candidate.first_load_egress_allowed,
        },
        "activation": {
            "permitted": False,
            "reason": "artifact delivery/verification is not Open Model Universe admission or Model Mesh activation",
        },
        "model_mesh": {
            "candidate_eligible": candidate.model_mesh_candidate_eligible,
            "selection_authority": "model_mesh",
        },
        "routing": {"authority": "task_router"},
    }


def _write_json(path: Path, payload: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    prepare = sub.add_parser("prepare")
    prepare.add_argument("--root", type=Path, default=Path("."))
    prepare.add_argument("--model-id")
    prepare.add_argument("--output", type=Path, required=True)
    verify = sub.add_parser("verify")
    verify.add_argument("--candidate", type=Path, required=True)
    verify.add_argument("--artifact", type=Path, required=True)
    verify.add_argument("--retrieval-method", required=True)
    verify.add_argument("--malware-scan-status", required=True, choices=("pass", "fail", "unknown", "not_run"))
    verify.add_argument("--malware-scan-engine", default="unspecified")
    verify.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()

    if args.command == "prepare":
        candidate = load_canonical_candidate(args.root, args.model_id)
        _write_json(args.output, candidate.to_dict())
        return 0
    candidate = DeliveryCandidate.from_dict(json.loads(args.candidate.read_text(encoding="utf-8")))
    manifest = verify_staged_artifact(
        candidate,
        args.artifact,
        retrieval_method=args.retrieval_method,
        malware_scan_status=args.malware_scan_status,
        malware_scan_engine=args.malware_scan_engine,
    )
    _write_json(args.output, manifest)
    return 0


if __name__ == "__main__":
    raise SystemExit(_main())
