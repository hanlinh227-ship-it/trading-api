"""Validate the authority-free Open Model Universe governance/admission registry."""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import re
from urllib.parse import parse_qsl, urlsplit

from jsonschema import Draft202012Validator, FormatChecker
import yaml


RUNTIME_ONLY_STATES = {
    "COLD", "ACQUIRING", "DOWNLOADING", "LOADING", "CACHED", "READY", "WARM",
    "RUNNING", "SLEEPING", "DEGRADED", "BROKEN", "EVICTED",
}
FORBIDDEN_KEYS = {
    "api_key", "apikey", "access_token", "auth_token", "bearer_token", "password",
    "private_key", "wallet_seed", "credential", "authorization", "secret", "secret_value",
    "enabled",
}
CREDENTIAL_VALUE = re.compile(
    r"(?:sk-[A-Za-z0-9_-]{8,}|AIza[A-Za-z0-9_-]{12,}|hf_[A-Za-z0-9_-]{8,}|gh[pousr]_[A-Za-z0-9]{20,}|xox[baprs]-[A-Za-z0-9-]{10,}|AKIA[A-Z0-9]{16}|Bearer\s+\S+|-----BEGIN [A-Z ]*PRIVATE KEY-----)",
    re.IGNORECASE,
)
SENSITIVE_QUERY_KEYS = {"access_token", "api_key", "apikey", "auth", "authorization", "password", "secret", "token"}
URL_FIELDS = ("official_upstream", "weights_source", "license_url")
IDENTITY_FIELDS = ("model_id", "family", "variant", "quantization")


def _schema_path() -> Path:
    return Path(__file__).resolve().parents[1] / "schemas/open_model_universe.schema.json"


def _forbidden_paths(value: object, path: str = "$") -> list[str]:
    found: list[str] = []
    if isinstance(value, dict):
        for key, nested in value.items():
            child = f"{path}.{key}"
            if str(key).strip().lower() in FORBIDDEN_KEYS:
                found.append(child)
            found.extend(_forbidden_paths(nested, child))
    elif isinstance(value, list):
        for index, nested in enumerate(value):
            found.extend(_forbidden_paths(nested, f"{path}[{index}]"))
    elif isinstance(value, str) and CREDENTIAL_VALUE.search(value):
        found.append(path)
    return found


def _unsafe_https_url(value: object) -> bool:
    if not isinstance(value, str):
        return True
    try:
        parsed = urlsplit(value)
    except ValueError:
        return True
    if parsed.scheme != "https" or not parsed.hostname or parsed.username is not None or parsed.password is not None:
        return True
    return any(key.lower() in SENSITIVE_QUERY_KEYS for key, _ in parse_qsl(parsed.query, keep_blank_values=True))


#: Gates an operator acceptance may stand in for. Nothing else, ever - licence,
#: provenance, format safety, pickle safety and remote-code restrictions are
#: either obtainable anywhere or are the reason the artifact is safe to open.
_ACCEPTABLE_GAPS = frozenset({"malware_scan_status"})

_ACCEPTANCE_REQUIRED_FIELDS = (
    "accepted_by", "accepted_at", "artifact_sha256", "basis", "missing_evidence", "scope",
)


def _risk_acceptance_refusals(model: dict, index: int) -> list[str]:
    """Why this row's operator acceptance does not stand in for a malware scan."""
    acceptance = model.get("operator_risk_acceptance")
    if not isinstance(acceptance, dict):
        return [
            f"admission blocks local candidate: malware_scan_status must be pass, or a valid "
            f"operator_risk_acceptance must be recorded, at models[{index}]"
        ]

    # An acceptance covers a known *absence* of evidence, never an adverse or
    # ambiguous result. "not_run" is a thing an operator can knowingly accept;
    # "fail" and "unknown" are not - the first is a finding and the second means
    # something happened that nobody has explained.
    status = (model.get("admission_evidence") or {}).get("malware_scan_status")
    if status != "not_run":
        return [
            f"admission blocks local candidate: malware_scan_status is {status!r}; an operator "
            f"acceptance may only cover 'not_run', at models[{index}]"
        ]

    errors: list[str] = []
    for field in _ACCEPTANCE_REQUIRED_FIELDS:
        value = acceptance.get(field)
        if not (value if isinstance(value, (list, tuple)) else str(value or "").strip()):
            errors.append(f"operator_risk_acceptance.{field} is required at models[{index}]")

    if acceptance.get("scope") not in (None, "single_artifact"):
        errors.append(
            f"operator_risk_acceptance.scope must be single_artifact at models[{index}]; "
            f"a blanket acceptance is refused"
        )

    # Bound to the exact bytes it was granted for, so it cannot be recycled.
    declared = str(acceptance.get("artifact_sha256") or "").strip().lower()
    actual = str((model.get("artifact_identity") or {}).get("sha256") or "").strip().lower()
    if declared and actual and declared != actual:
        errors.append(
            f"operator_risk_acceptance.artifact_sha256 does not match artifact_identity.sha256 "
            f"at models[{index}]"
        )

    covers = set(acceptance.get("covers") or [])
    forbidden = sorted(covers - _ACCEPTABLE_GAPS)
    if forbidden:
        errors.append(
            f"operator_risk_acceptance may not cover {forbidden} at models[{index}]"
        )
    if "malware_scan_status" not in covers:
        errors.append(
            f"operator_risk_acceptance does not cover malware_scan_status at models[{index}]"
        )

    # The decision must not be dressed up as a finding.
    if acceptance.get("is_a_scan_result") is not False:
        errors.append(
            f"operator_risk_acceptance must record is_a_scan_result: false at models[{index}]"
        )
    admission = model.get("admission_evidence") or {}
    if admission.get("malware_scan_status") == "pass":
        errors.append(
            f"malware_scan_status must not be reported as pass when it was accepted rather "
            f"than scanned, at models[{index}]"
        )
    return errors


def _capability_refusals(model: dict, index: int) -> list[str]:
    """A capability score above zero must be backed by a measurement.

    This is the rule that makes a capability score mean anything. The Model
    Mesh admits or refuses a worker by comparing this number against a floor,
    so a number nobody measured is not an optimistic estimate - it is the whole
    gate, bypassed. Declaring `text_reasoning: 0.9` is otherwise a one-line
    edit that promotes a model past every filter the mesh has.

    Four things are checked, and each closes a different way of getting a
    number without earning it:

    * a non-zero score needs an entry in `capability_evidence` at all;
    * the entry's score must equal the declared one, so the registry cannot
      quote a measurement and then round it up;
    * the evidence must be bound to *this* artifact's digest, so a score
      measured on one set of weights cannot be inherited by another;
    * the run must have completed without errors, because a score computed
      over the items that did not crash is not a score.

    A score of exactly 0.0 needs nothing. Declaring no capability is always
    honest, and requiring evidence for it would mean a newly discovered model
    could not be registered at all.
    """
    errors: list[str] = []
    capabilities = model.get("capabilities")
    if not isinstance(capabilities, dict):
        return errors
    evidence = model.get("capability_evidence")
    evidence = evidence if isinstance(evidence, dict) else {}
    declared_digest = (model.get("artifact_identity") or {}).get("sha256")

    for name, raw in sorted(capabilities.items()):
        if not isinstance(raw, (int, float)) or isinstance(raw, bool) or float(raw) <= 0.0:
            continue
        score = float(raw)
        row = evidence.get(name)
        if not isinstance(row, dict):
            errors.append(
                f"capability {name}={score} is declared without measurement evidence at models[{index}]"
            )
            continue
        measured = row.get("score")
        if not isinstance(measured, (int, float)) or isinstance(measured, bool) or float(measured) != score:
            errors.append(
                f"capability {name} declares {score} but its evidence measured {measured} at models[{index}]"
            )
        if row.get("errors") != 0:
            errors.append(
                f"capability {name} was measured by a run with errors; a partial run is not a score at models[{index}]"
            )
        if declared_digest and row.get("artifact_sha256") != declared_digest:
            errors.append(
                f"capability {name} evidence is bound to different artifact bytes at models[{index}]"
            )
    return errors


def _admission_refusals(model: dict, index: int) -> list[str]:
    errors: list[str] = []
    if not model.get("model_mesh_local_candidate_eligible"):
        return errors

    if model.get("lifecycle_state") != "AVAILABLE":
        errors.append(f"model mesh local candidate requires governance state AVAILABLE at models[{index}]")

    admission = model.get("admission_evidence") if isinstance(model.get("admission_evidence"), dict) else {}
    required_true = ("license_verified", "provenance_verified", "safe_format_verified")
    for field in required_true:
        if admission.get(field) is not True:
            errors.append(f"admission blocks local candidate: {field} must be true at models[{index}]")
    if admission.get("pickle_safe") is not True:
        errors.append(f"admission blocks local candidate: pickle_safe must be true at models[{index}]")
    if admission.get("trust_remote_code_required") is not False:
        errors.append(f"admission blocks local candidate: trust_remote_code_required must be false at models[{index}]")
    if admission.get("custom_code_required") is not False:
        errors.append(f"admission blocks local candidate: custom_code_required must be false at models[{index}]")
    if admission.get("malware_scan_status") != "pass":
        # A named, digest-bound operator acceptance may stand in for a scan that
        # cannot be run in the deploying environment. It is a recorded decision,
        # never a substituted finding: malware_scan_status must still read its
        # true value, and the acceptance has to be complete enough to audit.
        errors.extend(_risk_acceptance_refusals(model, index))
    if admission.get("quarantine_status") != "clear":
        errors.append(f"admission blocks local candidate: quarantine_status must be clear at models[{index}]")
    if model.get("artifact_identity", {}).get("format") == "other":
        errors.append(f"admission blocks local candidate: safe artifact format is not established at models[{index}]")
    return errors


def validate_document(document: object, schema: dict | None = None) -> list[str]:
    errors: list[str] = []
    if schema is None:
        schema = json.loads(_schema_path().read_text(encoding="utf-8"))
    try:
        Draft202012Validator.check_schema(schema)
    except Exception as exc:
        return [f"invalid Open Model Universe schema: {exc}"]
    validator = Draft202012Validator(schema, format_checker=FormatChecker())
    for error in sorted(validator.iter_errors(document), key=lambda item: list(item.path)):
        location = ".".join(str(part) for part in error.path) or "$"
        errors.append(f"schema {location}: {error.message}")
    if not isinstance(document, dict):
        return errors or ["registry root must be an object"]

    policy = document.get("policy") if isinstance(document.get("policy"), dict) else {}
    if policy.get("cost_policy") != "OPEN_MODEL_ZERO_TOKEN_FIRST":
        errors.append("cost policy must be OPEN_MODEL_ZERO_TOKEN_FIRST")
    if policy.get("paid_fallback") != "NO_PAID_FALLBACK":
        errors.append("paid fallback must remain NO_PAID_FALLBACK")
    if policy.get("registry_implies_activation") is not False or policy.get("auto_download") is not False:
        errors.append("registry metadata must never imply activation or automatic download")

    authority = document.get("authority") if isinstance(document.get("authority"), dict) else {}
    if authority and any(value is not False for value in authority.values()):
        errors.append("Open Model Universe must have zero authority")

    integration = document.get("integration") if isinstance(document.get("integration"), dict) else {}
    runtime_contract = integration.get("runtime_residency_contract") if isinstance(integration.get("runtime_residency_contract"), dict) else {}
    if integration.get("registry_membership_is_activation") is not False:
        errors.append("Open Model Universe registry membership must not activate a runtime")
    if integration.get("ingress_hardcodes_model") is not False:
        errors.append("ingress must not hardcode a model")
    if runtime_contract.get("owner") not in (None, "claude_local_runtime"):
        errors.append("runtime residency ownership must remain Claude-owned")
    if runtime_contract.get("open_model_universe_has_runtime_residency_authority") not in (None, False):
        errors.append("Open Model Universe must not hold runtime residency authority")

    identities: set[tuple[str, ...]] = set()
    model_ids: set[str] = set()
    models = document.get("models") if isinstance(document.get("models"), list) else []
    for index, model in enumerate(models):
        if not isinstance(model, dict):
            continue
        artifact = model.get("artifact_identity") if isinstance(model.get("artifact_identity"), dict) else {}
        identity = tuple(str(artifact.get(field) or "") for field in ("model_id", "family", "variant", "immutable_revision", "sha256", "format", "quantization"))
        if identity in identities:
            errors.append(f"duplicate model identity at models[{index}]: {identity}")
        identities.add(identity)
        model_id = str(model.get("model_id") or "")
        if model_id in model_ids:
            errors.append(f"duplicate model_id at models[{index}]: {model_id}")
        model_ids.add(model_id)

        if model.get("authority") is not False:
            errors.append(f"model authority must remain false at models[{index}]")
        if model.get("paid_token_required") is True:
            errors.append(f"paid-token model cannot enter zero-token registry at models[{index}]")
        if model.get("lifecycle_state") in RUNTIME_ONLY_STATES:
            errors.append(f"runtime state is forbidden as Open Model Universe governance state at models[{index}]")

        for field in IDENTITY_FIELDS:
            if str(model.get(field) or "") != str(artifact.get(field) or ""):
                errors.append(f"artifact identity drift for {field} at models[{index}]")
        if str(model.get("upstream_revision") or "") != str(artifact.get("immutable_revision") or ""):
            errors.append(f"artifact identity drift for immutable_revision at models[{index}]")
        if artifact.get("immutable_revision") and artifact.get("immutable_revision") not in str(model.get("weights_source") or ""):
            errors.append(f"weights_source must pin artifact identity immutable_revision at models[{index}]")
        if model.get("license_verified") is not (model.get("admission_evidence") or {}).get("license_verified"):
            errors.append(f"license verification must agree with admission evidence at models[{index}]")

        errors.extend(_admission_refusals(model, index))
        # Applies to every row, not only mesh-eligible ones: a fabricated
        # capability score is a defect the moment it is written down, not
        # the moment the model becomes selectable.
        errors.extend(_capability_refusals(model, index))

        for field in URL_FIELDS:
            if _unsafe_https_url(model.get(field)):
                errors.append(f"unsafe or invalid provenance URL at models[{index}].{field}")
        for evidence_index, evidence in enumerate(model.get("source_evidence") or []):
            if _unsafe_https_url(evidence):
                errors.append(f"unsafe or invalid provenance URL at models[{index}].source_evidence[{evidence_index}]")

    forbidden = _forbidden_paths(document)
    if forbidden:
        errors.append(f"registry contains forbidden credential/secret or hardcoded enable data: {', '.join(forbidden[:8])}")
    return errors


def validate_open_model_universe(root: Path) -> list[str]:
    root = Path(root).resolve()
    schema_path = root / "AI_SKILL_LIBRARY/v4/schemas/open_model_universe.schema.json"
    registry_path = root / "AI_SKILL_LIBRARY/v4/open_model_universe/registry.yaml"
    admission_path = root / "AI_SKILL_LIBRARY/v4/open_model_universe/admission_policy.yaml"
    errors: list[str] = []
    for path, label in ((schema_path, "schema"), (registry_path, "registry"), (admission_path, "admission policy")):
        if not path.is_file():
            errors.append(f"missing Open Model Universe {label}: {path.relative_to(root)}")
    if errors:
        return errors
    try:
        schema = json.loads(schema_path.read_text(encoding="utf-8"))
        registry = yaml.safe_load(registry_path.read_text(encoding="utf-8"))
        admission = yaml.safe_load(admission_path.read_text(encoding="utf-8"))
    except (OSError, ValueError, json.JSONDecodeError, yaml.YAMLError) as exc:
        return [f"cannot load Open Model Universe contract: {exc}"]
    errors.extend(validate_document(registry, schema))
    expected_flow = ["open_model_universe", "admission_gate", "model_mesh_local_candidate", "claude_runtime_projection"]
    if admission.get("flow") != expected_flow:
        errors.append("admission boundary flow must remain registry -> admission -> Model Mesh -> Claude runtime")
    if admission.get("registry_membership_implies_activation") is not False:
        errors.append("admission policy must not make registry membership activation")
    if admission.get("ingress_hardcodes_model") is not False:
        errors.append("admission policy must forbid ingress model hardcoding")
    return errors


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Validate Open Model Universe contracts")
    parser.add_argument("--root", default=".")
    args = parser.parse_args(argv)
    errors = validate_open_model_universe(Path(args.root))
    for error in errors:
        print(f"[ERROR] {error}")
    print(f"OPEN_MODEL_UNIVERSE_VALIDATE={'PASS' if not errors else 'FAIL'} errors={len(errors)}")
    return 1 if errors else 0


if __name__ == "__main__":
    raise SystemExit(main())
