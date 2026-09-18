#!/usr/bin/env python3
"""Survival Plane proof tool (Task 6, non-shared-file portion).

Deterministic, offline, fail-closed. Consumes existing Survival Plane modules
created by Tasks 1-5; creates no parallel authority.
"""
from __future__ import annotations

import importlib
import json
import os
import sys
from typing import Any, Dict, List, Optional, Tuple

_HERE = os.path.dirname(os.path.abspath(__file__))
_V4 = os.path.dirname(_HERE)
if _V4 not in sys.path:
    sys.path.insert(0, _V4)

PASS = "PASS"
FAIL = "FAIL"


def _load(name: str) -> Optional[Any]:
    try:
        return importlib.import_module(name)
    except Exception:
        return None


def _first_attr(mod: Any, names: List[str]) -> Optional[Any]:
    if mod is None:
        return None
    for n in names:
        if hasattr(mod, n):
            return getattr(mod, n)
    return None


def _policy_evidence() -> Tuple[bool, List[str]]:
    notes: List[str] = []
    mod = _load("survival_plane.policy_adapter")
    if mod is None:
        mod = _load("v4.survival_plane.policy_adapter")
    if mod is None:
        notes.append("policy_adapter module missing")
        return False, notes
    adapter_cls = _first_attr(mod, ["PolicyAdapter", "CanonicalPolicyAdapter"])
    if adapter_cls is None:
        notes.append("canonical policy adapter contract missing")
        return False, notes
    try:
        adapter = adapter_cls()
    except Exception:
        notes.append("policy adapter not constructible")
        return False, notes
    decide = _first_attr(adapter, ["decide", "evaluate", "check"])
    if decide is None:
        notes.append("policy adapter decision entrypoint missing")
        return False, notes
    try:
        result = decide({"action": "__proof_unknown__", "authority": "none"})
    except Exception:
        notes.append("policy adapter raised on unknown action (fail-closed)")
        return True, notes
    allowed = None
    if isinstance(result, dict):
        allowed = result.get("allowed")
    elif isinstance(result, bool):
        allowed = result
    if allowed is False:
        notes.append("policy adapter denies unknown action")
        return True, notes
    notes.append("policy adapter did not evidence fail-closed denial")
    return False, notes


def _secret_evidence() -> Tuple[bool, List[str]]:
    notes: List[str] = []
    mod = _load("survival_plane.secret_ref")
    if mod is None:
        mod = _load("v4.survival_plane.secret_ref")
    if mod is None:
        notes.append("secret_ref module missing")
        return False, notes
    ref_cls = _first_attr(mod, ["SecretRef", "ReferenceOnlySecret"])
    if ref_cls is None:
        notes.append("SecretRef contract missing")
        return False, notes
    try:
        ref = ref_cls("proof/ref/name")
    except Exception:
        notes.append("SecretRef not constructible")
        return False, notes
    for attr in ("value", "secret", "raw", "plaintext"):
        if hasattr(ref, attr):
            try:
                v = getattr(ref, attr)
            except Exception:
                continue
            if v not in (None, ""):
                notes.append("SecretRef exposes secret value")
                return False, notes
    resolve = _first_attr(ref, ["resolve", "get_value", "reveal"])
    if resolve is not None:
        try:
            out = resolve()
        except Exception:
            out = None
        if out not in (None, ""):
            notes.append("SecretRef resolution exposes secret value")
            return False, notes
    notes.append("SecretRef reference-only behavior evidenced")
    return True, notes


def _artifact_evidence() -> Tuple[bool, List[str]]:
    notes: List[str] = []
    scan = _load("survival_plane.artifact_scan")
    if scan is None:
        scan = _load("v4.survival_plane.artifact_scan")
    prov = _load("survival_plane.provenance")
    if prov is None:
        prov = _load("v4.survival_plane.provenance")
    if scan is None or prov is None:
        notes.append("artifact scan or provenance contract missing")
        return False, notes
    scan_fn = _first_attr(scan, ["scan_artifact", "scan", "verify_artifact"])
    prov_fn = _first_attr(prov, ["verify_provenance", "check_provenance", "verify"])
    if scan_fn is None or prov_fn is None:
        notes.append("artifact trust entrypoints missing")
        return False, notes
    cases = [
        ({}, "missing trust evidence"),
        ({"digest": "sha256:deadbeef", "provenance": {"signer": "x", "digest": "sha256:cafebabe"}}, "mismatched trust evidence"),
        ({"digest": "sha256:deadbeef", "provenance": {"signer": "x", "digest": "sha256:deadbeef", "verified": False}}, "unverified trust evidence"),
    ]
    for payload, label in cases:
        try:
            r1 = scan_fn(payload)
        except Exception:
            r1 = False
        try:
            r2 = prov_fn(payload)
        except Exception:
            r2 = False
        if r1 is True or r2 is True:
            notes.append("artifact trust accepted " + label)
            return False, notes
    notes.append("artifact trust rejects missing/mismatched/unverified evidence")
    return True, notes


def _restore_drill_evidence(evidence_path: Optional[str]) -> Tuple[bool, List[str]]:
    notes: List[str] = []
    if not evidence_path:
        notes.append("no restore-drill evidence supplied")
        return False, notes
    if not os.path.isfile(evidence_path):
        notes.append("restore-drill evidence file not found")
        return False, notes
    try:
        with open(evidence_path, "r", encoding="utf-8") as fh:
            data = json.load(fh)
    except Exception:
        notes.append("restore-drill evidence unreadable")
        return False, notes
    if not isinstance(data, dict):
        notes.append("restore-drill evidence malformed")
        return False, notes
    required = {
        "isolated": True,
        "faithful": True,
        "restore_verified": True,
        "source": "restore_drill",
    }
    for key, want in required.items():
        if data.get(key) != want:
            notes.append("restore-drill evidence missing/invalid: " + key)
            return False, notes
    notes.append("explicit faithful isolated restore-drill evidence validated")
    return True, notes


def evaluate(evidence_path: Optional[str] = None) -> Dict[str, str]:
    policy_ok, _ = _policy_evidence()
    secret_ok, _ = _secret_evidence()
    artifact_ok, _ = _artifact_evidence()
    drill_ok, _ = _restore_drill_evidence(evidence_path)
    dr_ok = drill_ok
    survival_ok = policy_ok and secret_ok and artifact_ok
    return {
        "SURVIVAL_PLANE_READY": PASS if survival_ok else FAIL,
        "DISASTER_RECOVERY_READY": PASS if dr_ok else FAIL,
        "POLICY_ENFORCEMENT": PASS if policy_ok else FAIL,
        "SECRET_REFERENCE_ONLY": PASS if secret_ok else FAIL,
        "ARTIFACT_TRUST": PASS if artifact_ok else FAIL,
        "RESTORE_DRILL": PASS if drill_ok else FAIL,
    }


def main(argv: Optional[List[str]] = None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    evidence_path = None
    if "--restore-drill-evidence" in argv:
        idx = argv.index("--restore-drill-evidence")
        if idx + 1 < len(argv):
            evidence_path = argv[idx + 1]
    results = evaluate(evidence_path)
    for key in (
        "SURVIVAL_PLANE_READY",
        "DISASTER_RECOVERY_READY",
        "POLICY_ENFORCEMENT",
        "SECRET_REFERENCE_ONLY",
        "ARTIFACT_TRUST",
        "RESTORE_DRILL",
    ):
        print(key + "=" + results[key])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
