"""B1 runner stage tests.

The runner refuses today because the canonical model is quarantined and no
artifact exists. That is correct - but "it refuses" is a weak claim on its own,
because a runner broken in some later stage would refuse identically. These
tests walk each precondition in turn with real components, so a defect further
down the path is found now rather than after the artifact finally arrives.

The only stage that cannot be exercised here is real generation, which needs
real weights. Everything before it is.
"""

import copy
import os
import tempfile
import unittest
from pathlib import Path

import yaml

from AI_SKILL_LIBRARY.v4.local_runtime.backends.llama_cpp_python import detect_llama_cpp_python
from AI_SKILL_LIBRARY.v4.local_runtime.staging import intake_staged_artifact
from AI_SKILL_LIBRARY.v4.tools.local_runtime_b1 import deny_egress, run

ROOT = Path(__file__).resolve().parents[2]
CANONICAL = ROOT / "AI_SKILL_LIBRARY/v4/open_model_universe/registry.yaml"
REAL_GGUF = Path("/tmp/probe.gguf")   # a real GGUF if this host still has one


def canonical_registry():
    return yaml.safe_load(CANONICAL.read_text(encoding="utf-8"))


def cleared_registry(**overrides):
    """The canonical registry with governance cleared - a hypothetical future.

    Written only into a temporary directory. The real registry is never
    modified, and nothing here clears quarantine anywhere it would persist.
    """
    registry = copy.deepcopy(canonical_registry())
    record = registry["models"][0]
    record["lifecycle_state"] = "AVAILABLE"
    record["privacy_class"] = "local_only"
    record["model_mesh_local_candidate_eligible"] = True
    record["admission_evidence"].update(malware_scan_status="pass", quarantine_status="clear")
    record.update(overrides)
    return registry


def write_registry(root: Path, registry) -> None:
    target = root / "AI_SKILL_LIBRARY/v4/open_model_universe"
    target.mkdir(parents=True, exist_ok=True)
    (target / "registry.yaml").write_text(yaml.safe_dump(registry), encoding="utf-8")
    policy_src = ROOT / "AI_SKILL_LIBRARY/v4/open_model_universe/admission_policy.yaml"
    (target / "admission_policy.yaml").write_text(policy_src.read_text(encoding="utf-8"), encoding="utf-8")


class Stage1GovernanceTests(unittest.TestCase):
    def test_the_real_canonical_registry_refuses_at_governance(self):
        with tempfile.TemporaryDirectory() as tmp:
            result = run(ROOT, Path(tmp), "hello", 8, None)
        self.assertEqual(result["b1_status"], "REFUSED")
        self.assertEqual(result["refused_at"], "governance_admission")
        self.assertFalse(result["real_generation"])
        self.assertEqual(result["governance"]["lifecycle_state"], "QUARANTINED")

    def test_the_refusal_names_every_governance_reason(self):
        with tempfile.TemporaryDirectory() as tmp:
            result = run(ROOT, Path(tmp), "hello", 8, None)
        reasons = " ".join(result["governance"]["exclusion_reasons"])
        for expected in ("QUARANTINED", "malware_scan_status", "quarantine_status"):
            self.assertIn(expected, reasons)

    def test_identity_is_still_read_losslessly_while_refusing(self):
        with tempfile.TemporaryDirectory() as tmp:
            result = run(ROOT, Path(tmp), "hello", 8, None)
        identity = result["artifact_identity"]
        self.assertEqual(identity["immutable_revision"], "1eaf4d9657fe65ad10a51eab76a8db5b363bddaa")
        self.assertEqual(
            identity["artifact_sha256"],
            "9465e63a22add5354d9bb4b99e90117043c7124007664907259bd16d043bb031",
        )
        self.assertEqual(identity["quantization"], "Q8_0")

    def test_an_unknown_model_id_is_refused_at_the_registry(self):
        with tempfile.TemporaryDirectory() as tmp:
            result = run(ROOT, Path(tmp), "hello", 8, "no-such-model")
        self.assertEqual(result["refused_at"], "registry")


class Stage2ArtifactTests(unittest.TestCase):
    """With governance cleared, the next refusal must be the missing artifact."""

    def test_a_cleared_record_advances_to_the_artifact_stage(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "repo"
            write_registry(root, cleared_registry())
            result = run(root, Path(tmp) / "cache", "hello", 8, None)
        self.assertEqual(result["b1_status"], "REFUSED")
        self.assertEqual(result["refused_at"], "artifact")
        self.assertIn("stage one", result["reason"])

    def test_governance_is_checked_before_the_artifact(self):
        # Order matters: a missing artifact must never mask a quarantine.
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "repo"
            write_registry(root, canonical_registry())
            result = run(root, Path(tmp) / "cache", "hello", 8, None)
        self.assertEqual(result["refused_at"], "governance_admission")

    @unittest.skipUnless(REAL_GGUF.is_file(), "no real GGUF on this host")
    def test_a_verified_artifact_advances_past_the_artifact_stage(self):
        """Uses a real GGUF whose digest is written into a temporary record.

        This is a pipeline test, not a model test: the file is llama.cpp's
        vocab-only fixture and is never presented as the canonical artifact.
        """
        import hashlib

        blob = REAL_GGUF.read_bytes()
        registry = cleared_registry()
        registry["models"][0]["artifact_identity"] = {
            **registry["models"][0]["artifact_identity"],
            "sha256": hashlib.sha256(blob).hexdigest(),
            "size_bytes": len(blob),
        }
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "repo"
            cache = Path(tmp) / "cache"
            write_registry(root, registry)
            intake = intake_staged_artifact(REAL_GGUF, registry["models"][0], root=cache)
            self.assertTrue(intake.verified, intake.reason)

            result = run(root, cache, "hello", 8, None)

        if detect_llama_cpp_python() is None:
            self.assertEqual(result["refused_at"], "backend")
            return

        # Backend present: the runner reached a real llama.cpp load, which
        # fails on a tensorless file. Reaching a real load failure is the
        # evidence wanted here - every stage before generation worked.
        self.assertEqual(result["b1_status"], "FAILED")
        self.assertFalse(result["real_generation"])
        self.assertIn("load", result["reason"].lower())
        body = result["execution_evidence"]
        self.assertEqual(body["model_revision"], "1eaf4d9657fe65ad10a51eab76a8db5b363bddaa")
        self.assertEqual(body["actual_quantization"], "Q8_0")
        self.assertIsNotNone(body["backend_version"])
        self.assertNotEqual(body["failure"]["kind"], "NONE")


class EgressDenialTests(unittest.TestCase):
    def test_proxy_variables_are_stripped_and_reported(self):
        saved = {k: os.environ.get(k) for k in ("HTTPS_PROXY", "HTTP_PROXY", "NO_PROXY")}
        try:
            os.environ["HTTPS_PROXY"] = "http://127.0.0.1:9"
            os.environ["HTTP_PROXY"] = "http://127.0.0.1:9"
            removed = deny_egress()
            self.assertIn("HTTPS_PROXY", removed)
            self.assertIn("HTTP_PROXY", removed)
            self.assertNotIn("HTTPS_PROXY", os.environ)
            self.assertEqual(os.environ.get("NO_PROXY"), "*")
        finally:
            for key, value in saved.items():
                if value is None:
                    os.environ.pop(key, None)
                else:
                    os.environ[key] = value

    def test_denying_egress_twice_is_safe(self):
        saved = os.environ.get("NO_PROXY")
        try:
            deny_egress()
            self.assertEqual(deny_egress(), {})
        finally:
            if saved is None:
                os.environ.pop("NO_PROXY", None)
            else:
                os.environ["NO_PROXY"] = saved


class NoFabricationTests(unittest.TestCase):
    def test_the_runner_never_reports_generation_it_did_not_do(self):
        with tempfile.TemporaryDirectory() as tmp:
            result = run(ROOT, Path(tmp), "hello", 8, None)
        self.assertFalse(result["real_generation"])
        for key in ("cold_generation", "warm_generation"):
            self.assertNotIn(key, result)

    def test_the_real_registry_is_never_modified_by_a_run(self):
        before = CANONICAL.read_bytes()
        with tempfile.TemporaryDirectory() as tmp:
            run(ROOT, Path(tmp), "hello", 8, None)
        self.assertEqual(CANONICAL.read_bytes(), before)

    def test_there_is_no_flag_to_skip_governance(self):
        import inspect
        source = inspect.getsource(run)
        self.assertIn("projected.placeable", source)
        for bypass in ("force", "skip_governance", "ignore_quarantine", "allow_quarantined"):
            self.assertNotIn(bypass, source)


if __name__ == "__main__":
    unittest.main()
