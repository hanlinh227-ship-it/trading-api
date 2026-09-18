"""Security regression over what this lane actually writes.

Memory Continuity refuses sensitive *key names* in its own state. Nothing
covered the rest of what this lane produces, and it produces a lot: nine
registry records, a transport manifest, and two dozen evidence files carrying
runtime output, engine diagnostics and scan results. Any of those is a place a
credential could end up by accident.

So this checks values as well as key names, across every artifact the lane
writes, plus the standing invariants that are easy to erode one convenience at
a time - egress denied at load, first load isolated, permission ceilings not
widened, no paid fallback.
"""

import json
import re
import unittest
from pathlib import Path

import yaml

from AI_SKILL_LIBRARY.v4.tools.memory_continuity import SENSITIVE_KEYS

ROOT = Path(__file__).resolve().parents[2]
EVIDENCE = ROOT / "CHECKPOINTS/evidence"
REGISTRY = ROOT / "AI_SKILL_LIBRARY/v4/open_model_universe/registry.yaml"
MANIFEST = ROOT / "AI_SKILL_LIBRARY/v4/open_model_universe/staging_manifest.json"

#: Shapes of real credential material. Deliberately about *values*, because a
#: leaked token rarely arrives under a key helpfully named "secret".
CREDENTIAL_PATTERNS = [
    ("private key block", re.compile(r"-----BEGIN [A-Z ]*PRIVATE KEY-----")),
    ("AWS access key id", re.compile(r"\bAKIA[0-9A-Z]{16}\b")),
    ("GitHub token", re.compile(r"\bgh[pousr]_[A-Za-z0-9]{20,}\b")),
    ("Slack token", re.compile(r"\bxox[abprs]-[A-Za-z0-9-]{10,}\b")),
    ("OpenAI-style key", re.compile(r"\bsk-[A-Za-z0-9]{32,}\b")),
    ("bearer header", re.compile(r"\bBearer\s+[A-Za-z0-9._~+/-]{20,}=*")),
    ("JWT", re.compile(r"\beyJ[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{10,}\b")),
    ("basic-auth URL", re.compile(r"https?://[^/\s:@]+:[^/\s@]+@")),
]


def lane_artifacts():
    """Everything this lane writes that a reader might reasonably trust."""
    paths = [REGISTRY, MANIFEST]
    if EVIDENCE.is_dir():
        paths.extend(sorted(EVIDENCE.rglob("*.json")))
    return [p for p in paths if p.is_file()]


def sensitive_key_paths(value, trail=""):
    found = []
    if isinstance(value, dict):
        for key, nested in value.items():
            here = f"{trail}.{key}" if trail else str(key)
            if str(key).strip().lower() in SENSITIVE_KEYS:
                found.append(here)
            found.extend(sensitive_key_paths(nested, here))
    elif isinstance(value, (list, tuple)):
        for index, item in enumerate(value):
            found.extend(sensitive_key_paths(item, f"{trail}[{index}]"))
    return found


class NoCredentialMaterialTests(unittest.TestCase):
    def test_no_artifact_contains_credential_shaped_text(self):
        """Values, not key names: a leaked token rarely arrives labelled."""
        offenders = []
        for path in lane_artifacts():
            text = path.read_text(encoding="utf-8", errors="replace")
            for label, pattern in CREDENTIAL_PATTERNS:
                if pattern.search(text):
                    offenders.append(f"{path.relative_to(ROOT).as_posix()}: {label}")
        self.assertEqual(offenders, [])

    def test_no_artifact_carries_a_sensitive_key_name(self):
        offenders = []
        for path in lane_artifacts():
            if path.suffix != ".json":
                continue
            try:
                doc = json.loads(path.read_text(encoding="utf-8"))
            except json.JSONDecodeError:
                continue
            for trail in sensitive_key_paths(doc):
                offenders.append(f"{path.relative_to(ROOT).as_posix()}: {trail}")
        self.assertEqual(offenders, [])

    def test_the_patterns_actually_match_something(self):
        """A regression that can never fire is not a regression."""
        samples = {
            "private key block": "-----BEGIN RSA PRIVATE KEY-----",
            "GitHub token": "ghp_" + "A" * 36,
            "JWT": "eyJhbGciOiJIUzI1NiJ9.eyJzdWIiOiIxMjM0NTY3ODkwIn0.dBjftJeZ4CVPmB92K27u",
            "basic-auth URL": "https://user:hunter2@example.invalid/x",
        }
        by_label = dict(CREDENTIAL_PATTERNS)
        for label, sample in samples.items():
            with self.subTest(label=label):
                self.assertTrue(by_label[label].search(sample))

    def test_a_model_digest_is_not_mistaken_for_a_secret(self):
        """64 hex characters are everywhere here and none of them is a key."""
        digest = "9465e63a22add5354d9bb4b99e90117043c7124007664907259bd16d043bb031"
        for label, pattern in CREDENTIAL_PATTERNS:
            with self.subTest(label=label):
                self.assertIsNone(pattern.search(digest))


class EgressAndIsolationTests(unittest.TestCase):
    def setUp(self):
        self.registry = yaml.safe_load(REGISTRY.read_text(encoding="utf-8"))

    def test_every_model_requires_an_isolated_first_load(self):
        for model in self.registry["models"]:
            with self.subTest(model_id=model["model_id"]):
                self.assertTrue(model["admission_evidence"]["isolated_first_load_required"])

    def test_no_model_is_allowed_egress_on_first_load(self):
        for model in self.registry["models"]:
            with self.subTest(model_id=model["model_id"]):
                self.assertFalse(model["admission_evidence"]["first_load_egress_allowed"])

    def test_no_model_requires_remote_code(self):
        """trust_remote_code is arbitrary execution by another name."""
        for model in self.registry["models"]:
            with self.subTest(model_id=model["model_id"]):
                self.assertFalse(model["admission_evidence"]["trust_remote_code_required"])
                self.assertFalse(model["admission_evidence"]["custom_code_required"])

    def test_every_model_is_pickle_safe(self):
        for model in self.registry["models"]:
            with self.subTest(model_id=model["model_id"]):
                self.assertTrue(model["admission_evidence"]["pickle_safe"])

    def test_recorded_runs_denied_egress(self):
        for path in sorted(EVIDENCE.glob("*.json")) if EVIDENCE.is_dir() else []:
            try:
                doc = json.loads(path.read_text(encoding="utf-8"))
            except json.JSONDecodeError:
                continue
            if not isinstance(doc, dict):
                continue
            egress = doc.get("egress")
            if isinstance(egress, dict) and "denied" in egress:
                with self.subTest(evidence=path.name):
                    self.assertTrue(egress["denied"])


class PermissionCeilingTests(unittest.TestCase):
    def test_worker_authority_cannot_be_granted_by_a_caller(self):
        """Authority flags are class attributes; passing them is a TypeError.

        A worker that could be constructed with authority is a worker whose
        permission ceiling is whatever the caller asks for.
        """
        from AI_SKILL_LIBRARY.v4.local_runtime.workers import WorkerRegistry

        for flag in ("routing_authority", "permission_authority", "memory_authority"):
            with self.subTest(flag=flag):
                with self.assertRaises(TypeError):
                    WorkerRegistry(**{flag: True})

    def test_the_gap_observer_cannot_act(self):
        from AI_SKILL_LIBRARY.v4.local_runtime.gap_observer import observe

        capabilities = observe(ROOT)["capabilities"]
        self.assertFalse(capabilities["approves_anything"])
        self.assertFalse(capabilities["writes_code"])

    def test_self_development_cannot_self_approve(self):
        from AI_SKILL_LIBRARY.v4.local_runtime.selfdev import AutoDevState

        names = {state.name for state in AutoDevState}
        self.assertNotIn("MERGED", names)
        self.assertNotIn("SELF_APPROVED", names)


class NoPaidPathTests(unittest.TestCase):
    def test_no_admitted_model_needs_a_paid_token_or_an_api(self):
        registry = yaml.safe_load(REGISTRY.read_text(encoding="utf-8"))
        for model in registry["models"]:
            with self.subTest(model_id=model["model_id"]):
                self.assertFalse(model["paid_token_required"])
                self.assertFalse(model["api_required"])
                self.assertTrue(model["local_runtime_possible"])

    def test_no_evidence_records_a_fallback_having_been_used(self):
        for path in sorted(EVIDENCE.rglob("*.json")) if EVIDENCE.is_dir() else []:
            try:
                doc = json.loads(path.read_text(encoding="utf-8"))
            except json.JSONDecodeError:
                continue
            text = json.dumps(doc)
            if '"fallback_used"' in text:
                with self.subTest(evidence=path.name):
                    self.assertNotIn('"fallback_used": true', text)


if __name__ == "__main__":
    unittest.main()
