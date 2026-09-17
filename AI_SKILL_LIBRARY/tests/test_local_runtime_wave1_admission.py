"""Wave 1 admission: the ways a model could be admitted without earning it.

The pipeline is generic so that one model's evidence can never become another's.
These tests are the specific routes by which that could happen anyway - a scan
result quoted from different bytes, a capability inherited, a quantization
misparsed so intake compares against the wrong thing, a "pass" from a scanner
that read nothing.
"""

import copy
import json
import unittest
from pathlib import Path

import yaml

from AI_SKILL_LIBRARY.v4.local_runtime.scanner import gguf_metadata
from AI_SKILL_LIBRARY.v4.tools.local_runtime_admit import build_record, quantization_of
from AI_SKILL_LIBRARY.v4.tools.local_runtime_record_capability import refusals
from AI_SKILL_LIBRARY.v4.tools.validate_open_model_universe import (
    _admission_refusals,
    _capability_refusals,
    _scan_reference_refusals,
)

ROOT = Path(__file__).resolve().parents[2]


def sha256_of(path: Path) -> str:
    """The digest of the bytes on disk, so a record is checked against its own artifact."""
    import hashlib
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1 << 22), b""):
            digest.update(block)
    return digest.hexdigest()
REGISTRY = ROOT / "AI_SKILL_LIBRARY/v4/open_model_universe/registry.yaml"
MANIFEST = ROOT / "AI_SKILL_LIBRARY/v4/open_model_universe/staging_manifest.json"


def registry():
    return yaml.safe_load(REGISTRY.read_text(encoding="utf-8"))


def entry(model_id="qwen3-1.7b-q8_0"):
    manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
    return next(e for e in manifest["entries"] if e["id"] == model_id)


def verified(digest="a" * 64, size=100):
    return {"sha256": digest, "size_bytes": size,
            "structural_scan": {"status": "pass", "gguf_version": 3,
                                "tensor_count": 310, "kv_count": 28}}


def scan(digest="a" * 64, status="pass"):
    return {"artifact_sha256": digest, "malware_scan_status": status,
            "engine": "ClamAV 1.5.3", "signature_database_version": "28126",
            "scanned_at": "2026-09-17T09:34:59+00:00", "scanned_by": "github-actions"}


class QuantizationParsingTests(unittest.TestCase):
    """A wrong quantization is not cosmetic - intake compares against it."""

    def test_multi_underscore_tags_are_read_whole(self):
        self.assertEqual(quantization_of("granite-3.3-2b-instruct-Q4_K_M.gguf"), "Q4_K_M")
        self.assertEqual(quantization_of("Qwen3-4B-Q4_K_M.gguf"), "Q4_K_M")

    def test_simple_tags_still_work(self):
        self.assertEqual(quantization_of("Qwen3-1.7B-Q8_0.gguf"), "Q8_0")
        self.assertEqual(quantization_of("model-F16.gguf"), "F16")

    def test_an_absent_tag_is_unknown_not_a_guess(self):
        self.assertEqual(quantization_of("model.gguf"), "unknown")


class AdmissionGateTests(unittest.TestCase):
    def test_a_model_with_complete_evidence_becomes_available(self):
        record = build_record(entry(), verified(), scan(), {"license_declared": "apache-2.0"})
        self.assertEqual(record["admission_gaps"], [])
        self.assertEqual(record["lifecycle_state"], "AVAILABLE")

    def test_a_scan_of_different_bytes_does_not_count(self):
        """The route by which one model's clearance becomes another's."""
        record = build_record(entry(), verified(digest="a" * 64),
                              scan(digest="b" * 64), {"license_declared": "apache-2.0"})
        self.assertIn("malware_scan_result_is_bound_to_different_bytes", record["admission_gaps"])
        self.assertEqual(record["lifecycle_state"], "QUARANTINED")

    def test_no_scan_leaves_the_model_quarantined(self):
        record = build_record(entry(), verified(), None, {"license_declared": "apache-2.0"})
        self.assertEqual(record["lifecycle_state"], "QUARANTINED")
        self.assertIn("malware_scan_status=not_run", record["admission_gaps"])

    def test_a_failed_scan_is_not_an_absent_scan(self):
        record = build_record(entry(), verified(), scan(status="fail"),
                              {"license_declared": "apache-2.0"})
        self.assertEqual(record["lifecycle_state"], "QUARANTINED")
        self.assertIn("malware_scan_status=fail", record["admission_gaps"])

    def test_an_undeclared_licence_is_never_inferred_from_the_family(self):
        record = build_record(entry(), verified(), scan(), {"license_declared": None})
        self.assertIn("license_undeclared_upstream", record["admission_gaps"])
        self.assertIsNone(record["license_declared"])

    def test_an_unverified_revision_blocks_admission(self):
        row = dict(entry())
        row["revision_status"] = "digest_differs_from_current_head"
        record = build_record(row, verified(), scan(), {"license_declared": "apache-2.0"})
        self.assertIn("immutable_revision_unverified", record["admission_gaps"])

    def test_a_failed_structural_scan_blocks_admission(self):
        broken = verified()
        broken["structural_scan"]["status"] = "fail"
        record = build_record(entry(), broken, scan(), {"license_declared": "apache-2.0"})
        self.assertIn("structural_scan_not_passed", record["admission_gaps"])

    def test_a_new_model_declares_no_capability(self):
        """It cannot inherit one; a score arrives only from its own run."""
        record = build_record(entry(), verified(), scan(), {"license_declared": "apache-2.0"})
        self.assertEqual(record["capabilities"], {"text_reasoning": 0.0})


class CapabilityWriteBackTests(unittest.TestCase):
    def evidence(self, **override):
        base = {
            "promotable": True,
            "artifact_identity": {"model_id": "m", "artifact_sha256": "c" * 64},
            "benchmark_run": {"capability": "text_reasoning", "score": 0.8, "errors": 0,
                              "run_status": "COMPLETE", "suite_id": "s", "suite_version": "1",
                              "suite_hash": "d" * 64, "attempted": 24, "passed": 19,
                              "started_at": "now", "backend_version": "llama-cpp-python/0.3.35"},
        }
        base.update(override)
        return base

    def test_a_measurement_for_a_digest_in_the_registry_is_accepted(self):
        text = "      sha256: " + "c" * 64
        self.assertEqual(refusals(self.evidence(), text)[0], [])

    def test_a_measurement_for_an_unknown_digest_is_refused(self):
        problems, _ = refusals(self.evidence(), "nothing here")
        self.assertTrue(any("no registry record" in p for p in problems))

    def test_a_degraded_run_is_refused(self):
        run = dict(self.evidence()["benchmark_run"], errors=2, run_status="DEGRADED")
        problems, _ = refusals(self.evidence(promotable=False, benchmark_run=run), "x")
        self.assertTrue(any("not promotable" in p for p in problems))
        self.assertTrue(any("partial run" in p for p in problems))


class LiveRegistryTests(unittest.TestCase):
    """Every admitted model must stand on its own evidence."""

    def setUp(self):
        self.models = registry()["models"]

    def test_every_model_satisfies_the_capability_rule(self):
        for index, model in enumerate(self.models):
            with self.subTest(model_id=model["model_id"]):
                self.assertEqual(_capability_refusals(model, index), [])

    def test_every_scan_reference_names_its_own_artifact(self):
        for index, model in enumerate(self.models):
            with self.subTest(model_id=model["model_id"]):
                self.assertEqual(_scan_reference_refusals(model, index), [])

    def test_no_two_models_share_a_capability_measurement(self):
        """A measurement is bound to one digest; two rows citing one run
        would mean a score was copied rather than earned."""
        seen = {}
        for model in self.models:
            evidence = (model.get("capability_evidence") or {}).get("text_reasoning")
            if not evidence:
                continue
            digest = evidence["artifact_sha256"]
            self.assertEqual(digest, model["artifact_identity"]["sha256"], model["model_id"])
            self.assertNotIn(digest, seen, f"{model['model_id']} reuses {seen.get(digest)}'s run")
            seen[digest] = model["model_id"]

    def test_an_acceptance_cannot_spread_beyond_the_bytes_it_was_granted_for(self):
        """An acceptance is bound to one artifact, wherever it appears.

        This used to assert that exactly one named row carried an acceptance,
        which broke the moment that row's gap was closed by a real scan and the
        acceptance was retired. The rule the assertion was reaching for is the
        binding, not the row: a decision to proceed without a scan applies to
        the digest it names and to nothing else, so it can never become a
        blanket permission by being copied onto a second model.
        """
        for model in self.models:
            acceptance = model.get("operator_risk_acceptance")
            if not acceptance:
                continue
            with self.subTest(model_id=model["model_id"]):
                self.assertEqual(acceptance["artifact_sha256"],
                                 model["artifact_identity"]["sha256"])
                self.assertEqual(acceptance["scope"], "single_artifact")
                self.assertEqual(acceptance["covers"], ["malware_scan_status"])
                self.assertIs(acceptance["is_a_scan_result"], False)

    def test_every_model_holds_a_real_scan_or_a_live_acceptance(self):
        """Never neither, and never two live claims at once.

        A row asserting that no scan ran beside the scan that did is a
        contradiction. A *superseded* acceptance is not: it records that a
        decision was taken before the scan existed, which is history rather
        than a competing claim, and the repository owner asked for it to be
        kept. So the rule is about live acceptances, not recorded ones.
        """
        for model in self.models:
            with self.subTest(model_id=model["model_id"]):
                status = model["admission_evidence"]["malware_scan_status"]
                acceptance = model.get("operator_risk_acceptance")
                if status == "pass":
                    if acceptance is not None:
                        self.assertTrue(str(acceptance.get("superseded_by") or "").strip(),
                                        "an acceptance kept beside a scan must be superseded")
                    reference = model["malware_scan_reference"]
                    self.assertEqual(reference["artifact_sha256"],
                                     model["artifact_identity"]["sha256"])
                    self.assertTrue(reference["signature_database_version"])
                else:
                    self.assertEqual(status, "not_run")
                    self.assertIsNotNone(acceptance)
                    self.assertFalse(str(acceptance.get("superseded_by") or "").strip())

    def test_an_acceptance_left_behind_by_a_real_scan_is_refused(self):
        """The gate that was missing while the registry contradicted itself.

        The acceptance rules were only consulted when malware_scan_status was
        not pass, so once a scan actually ran the acceptance beside it stopped
        being checked at all - and the row read "pass" under a record stating no
        scan was performed. Nothing refused that, which is why it survived.
        """
        model = copy.deepcopy(self.models[0])
        model["admission_evidence"]["malware_scan_status"] = "pass"
        model["operator_risk_acceptance"] = {
            "accepted_by": "operator",
            "accepted_at": "2026-09-17T05:00:00Z",
            "artifact_sha256": model["artifact_identity"]["sha256"],
            "basis": "no engine reachable",
            "missing_evidence": ["signature_based_malware_scan"],
            "covers": ["malware_scan_status"],
            "scope": "single_artifact",
            "is_a_scan_result": False,
        }
        refusals = _admission_refusals(model, 0)
        self.assertTrue(
            any("still live" in reason for reason in refusals),
            refusals,
        )

    def test_a_superseded_acceptance_may_be_kept_beside_the_scan(self):
        """Deleting the record would erase that a decision was ever made.

        The contradiction is two live claims, not a preserved one, so an
        acceptance marked superseded by the scan that closed its gap is
        accepted - which is what the repository owner asked for.
        """
        model = copy.deepcopy(self.models[0])
        digest = model["artifact_identity"]["sha256"]
        model["admission_evidence"]["malware_scan_status"] = "pass"
        model["operator_risk_acceptance"] = {
            "accepted_by": "operator",
            "accepted_at": "2026-09-17T05:00:00Z",
            "artifact_sha256": digest,
            "basis": "no engine reachable at the time",
            "missing_evidence": ["signature_based_malware_scan"],
            "covers": ["malware_scan_status"],
            "scope": "single_artifact",
            "is_a_scan_result": False,
            "superseded_by": f"malware_scan_reference against artifact_sha256 {digest}",
            "superseded_at": "2026-09-17T11:19:31Z",
        }
        self.assertEqual(_admission_refusals(model, 0), [])

    def test_an_acceptance_is_still_allowed_where_no_scan_ran(self):
        """The new gate must not make acceptances unusable.

        An acceptance is the documented route for an environment with no
        reachable engine. Refusing it outright would close that route, which is
        a different change than the one intended here.
        """
        model = copy.deepcopy(self.models[0])
        model["admission_evidence"]["malware_scan_status"] = "not_run"
        model.pop("malware_scan_reference", None)
        model["operator_risk_acceptance"] = {
            "accepted_by": "operator",
            "accepted_at": "2026-09-17T05:00:00Z",
            "artifact_sha256": model["artifact_identity"]["sha256"],
            "basis": "no engine reachable",
            "missing_evidence": ["signature_based_malware_scan"],
            "covers": ["malware_scan_status"],
            "scope": "single_artifact",
            "is_a_scan_result": False,
        }
        self.assertEqual(_admission_refusals(model, 0), [])

    def test_context_windows_came_from_the_artifacts(self):
        """Read from the GGUF header, not from a model card."""
        cache = ROOT / ".model-cache"
        if not cache.is_dir():
            self.skipTest("no local cache")
        for model in self.models:
            declared = model.get("context_window")
            if not declared:
                continue
            # Match this model's OWN artifact, by digest. Accepting any cached
            # artifact that happened to declare the same number let one model's
            # window vouch for another's, and failed as soon as the cache held a
            # different subset of models than the registry.
            digest = str(model["artifact_identity"]["sha256"]).lower()
            artifact = None
            for path in cache.rglob("*.gguf"):
                if sha256_of(path) == digest:
                    artifact = path
                    break
            if artifact is None:
                # Not cached here. Absence of the bytes is not evidence against
                # the record, so there is nothing this check can say.
                continue
            metadata = gguf_metadata(artifact)
            architecture = metadata.get("general.architecture")
            observed = metadata.get(f"{architecture}.context_length") if architecture else None
            self.assertEqual(
                observed, declared,
                f"{model['model_id']} declares context_window {declared} but its own "
                f"artifact declares {observed}")


if __name__ == "__main__":
    unittest.main()


class ResidencyProfileEvidenceTests(unittest.TestCase):
    """Latency evidence must be measured under stated conditions, or it is noise."""

    def setUp(self):
        path = ROOT / "CHECKPOINTS/evidence/RESIDENCY_LATENCY_PROFILE.json"
        if not path.is_file():
            self.skipTest("no residency profile committed")
        self.profile = json.loads(path.read_text(encoding="utf-8"))

    def test_cold_loads_were_measured_against_a_cold_page_cache(self):
        """Without this the first load measures whatever was read last.

        It is recorded as a flag rather than assumed, because a profile taken
        without the privilege to drop caches is still useful and must not claim
        to be a cold-load measurement.
        """
        self.assertTrue(self.profile["cold_loads_are_page_cache_cold"])
        for model in self.profile["models"]:
            if model.get("measured"):
                self.assertTrue(model["page_cache_dropped_before_load"], model["model_id"])

    def test_every_admitted_model_was_profiled_on_the_same_prompt(self):
        """A latency comparison across different prompts compares the prompts."""
        self.assertTrue(self.profile["prompt"])
        self.assertTrue(all(m.get("measured") for m in self.profile["models"]))

    def test_residency_saving_is_derived_from_the_measured_parts(self):
        for model in self.profile["models"]:
            with self.subTest(model_id=model["model_id"]):
                expected = (model["cold_load_ms"] + model["cold_inference_ms"]
                            - model["warm_inference_ms"])
                self.assertAlmostEqual(model["residency_saving_ms"], expected, places=2)

    def test_the_models_cannot_all_be_resident_at_once(self):
        """The constraint behind a HOT tier of one or two, not four."""
        total = sum(m["peak_ram_mb"] for m in self.profile["models"] if m.get("measured"))
        self.assertGreater(total, self.profile["host_ram_total_mb"] * 0.8)

    def test_capability_and_latency_do_not_move_together(self):
        """The trade the routing utility has to price.

        The most capable model is also the slowest, so a selection weighted on
        capability alone systematically picks the slowest worker.
        """
        measured = [m for m in self.profile["models"] if m.get("measured_capability")]
        strongest = max(measured, key=lambda m: m["measured_capability"])
        fastest = min(measured, key=lambda m: m["warm_inference_ms"])
        self.assertNotEqual(strongest["model_id"], fastest["model_id"])


class RuntimeLoadGateTests(unittest.TestCase):
    """Licence, scan, digest and format can all pass on a model that cannot run.

    Two did. BitNet's GGUF carries tensor type 36, removed from this llama.cpp
    build, and Ministral-3 declares architecture `mistral3` with a vocabulary
    the loader rejects. Both were briefly AVAILABLE while nothing could execute
    them, which is the gap this gate closes.
    """

    def report(self, digest, loadable):
        return {"results": [{"artifact_sha256": digest, "loadable": loadable}]}

    def test_a_model_the_runtime_cannot_load_is_quarantined(self):
        digest = "a" * 64
        record = build_record(entry(), verified(digest=digest), scan(digest=digest),
                              {"license_declared": "apache-2.0"},
                              self.report(digest, False))
        self.assertIn("runtime_cannot_load", record["admission_gaps"])
        self.assertEqual(record["lifecycle_state"], "QUARANTINED")

    def test_a_loadable_model_is_unaffected(self):
        digest = "a" * 64
        record = build_record(entry(), verified(digest=digest), scan(digest=digest),
                              {"license_declared": "apache-2.0"},
                              self.report(digest, True))
        self.assertEqual(record["admission_gaps"], [])

    def test_absent_verification_is_not_a_gap(self):
        """The load can only be attempted after the artifact is cached, which
        happens after the first admission. Requiring it up front would deadlock."""
        digest = "a" * 64
        record = build_record(entry(), verified(digest=digest), scan(digest=digest),
                              {"license_declared": "apache-2.0"}, None)
        self.assertEqual(record["admission_gaps"], [])

    def test_a_verification_for_other_bytes_does_not_apply(self):
        digest = "a" * 64
        record = build_record(entry(), verified(digest=digest), scan(digest=digest),
                              {"license_declared": "apache-2.0"},
                              self.report("b" * 64, False))
        self.assertNotIn("runtime_cannot_load", record["admission_gaps"])

    def test_the_live_registry_quarantines_exactly_the_unloadable_models(self):
        path = ROOT / "CHECKPOINTS/evidence/RUNTIME_LOAD_VERIFICATION.json"
        if not path.is_file():
            self.skipTest("no load verification committed")
        report = json.loads(path.read_text(encoding="utf-8"))
        unloadable = {r["model_id"] for r in report["results"] if r.get("loadable") is False}
        by_id = {m["model_id"]: m for m in registry()["models"]}
        for model_id in unloadable:
            with self.subTest(model_id=model_id):
                record = by_id[model_id]
                self.assertEqual(record["lifecycle_state"], "QUARANTINED")
                self.assertFalse(record["model_mesh_local_candidate_eligible"])
                # The artifact is fine; the pairing is not, and the record says so.
                self.assertTrue(record["runtime_compatibility"]["artifact_is_intact"])
                self.assertFalse(record["runtime_compatibility"]["loadable"])

    def test_every_mesh_eligible_model_actually_loads(self):
        """The property that matters: nothing selectable is unrunnable."""
        path = ROOT / "CHECKPOINTS/evidence/RUNTIME_LOAD_VERIFICATION.json"
        if not path.is_file():
            self.skipTest("no load verification committed")
        report = json.loads(path.read_text(encoding="utf-8"))
        loadable = {r["model_id"] for r in report["results"] if r.get("loadable") is True}
        for record in registry()["models"]:
            if record.get("model_mesh_local_candidate_eligible"):
                with self.subTest(model_id=record["model_id"]):
                    self.assertIn(record["model_id"], loadable)
