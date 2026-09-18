"""The mesh capability ledger, and the rule that it only ever quotes evidence.

The ledger is what makes a capability score comparable at routing time, so the
one thing that must never happen is a row nothing measured. These tests are
about the ways such a row could get in: an unbacked score, a score copied from a
different artifact, a score that disagrees with the governance plane, and a
score whose only source is a documentation URL.
"""

import copy
import json
import shutil
import tempfile
import unittest
from pathlib import Path

import yaml

from AI_SKILL_LIBRARY.v4.tools.capability_evidence import load_capability_ledger
from AI_SKILL_LIBRARY.v4.tools.compile_capability_ledger import (
    LedgerRefused,
    build,
    collect_rows,
)

ROOT = Path(__file__).resolve().parents[2]
LEDGER = ROOT / "AI_SKILL_LIBRARY/v4/model_mesh/capability_evidence.json"
REGISTRY_REL = "AI_SKILL_LIBRARY/v4/open_model_universe/registry.yaml"
EVIDENCE_REL = "CHECKPOINTS/evidence"


def _sandbox(tmp: Path) -> Path:
    (tmp / EVIDENCE_REL).mkdir(parents=True, exist_ok=True)
    for path in (ROOT / EVIDENCE_REL).glob("WAVE0_CAPABILITY_*.json"):
        shutil.copy2(path, tmp / EVIDENCE_REL / path.name)
    (tmp / REGISTRY_REL).parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(ROOT / REGISTRY_REL, tmp / REGISTRY_REL)
    return tmp


def _edit_evidence(tmp: Path, name: str, mutate) -> None:
    path = tmp / EVIDENCE_REL / name
    document = json.loads(path.read_text(encoding="utf-8"))
    mutate(document)
    path.write_text(json.dumps(document), encoding="utf-8")


class CommittedLedgerTests(unittest.TestCase):
    """What the ledger in the repository must say to be worth consuming."""

    @classmethod
    def setUpClass(cls):
        cls.ledger = json.loads(LEDGER.read_text(encoding="utf-8"))
        cls.registry = yaml.safe_load((ROOT / REGISTRY_REL).read_text(encoding="utf-8"))
        cls.by_id = {m["model_id"]: m for m in cls.registry["models"]}

    def test_the_ledger_is_not_empty(self):
        """An empty ledger is why the active index reported verified=0."""
        self.assertTrue(self.ledger["records"])

    def test_it_validates_against_the_canonical_schema(self):
        load_capability_ledger(ROOT, Path("AI_SKILL_LIBRARY/v4/model_mesh/capability_evidence.json"))

    def test_it_claims_no_authority(self):
        self.assertIs(self.ledger["routing_authority"], False)
        self.assertIs(self.ledger["reasoning_authority"], False)

    def test_every_row_agrees_with_the_governance_plane(self):
        """Two places recording one measurement must record the same number."""
        for row in self.ledger["records"]:
            with self.subTest(model_id=row["model_id"]):
                record = self.by_id[row["model_id"]]
                evidence = record["capability_evidence"][row["capability"]]
                self.assertEqual(float(evidence["score"]), float(row["score"]))
                self.assertEqual(
                    evidence["artifact_sha256"], record["artifact_identity"]["sha256"]
                )

    def test_every_row_names_the_digest_it_was_measured_on(self):
        for row in self.ledger["records"]:
            with self.subTest(model_id=row["model_id"]):
                digest = self.by_id[row["model_id"]]["artifact_identity"]["sha256"]
                self.assertIn(digest[:12], row["evidence_id"])

    def test_no_two_rows_share_an_evidence_id(self):
        ids = [row["evidence_id"] for row in self.ledger["records"]]
        self.assertEqual(len(ids), len(set(ids)))

    def test_every_row_traces_to_its_own_evidence_file(self):
        """The reference was hardcoded to one model's file for every row, which
        made each row untraceable to the run that produced it."""
        for row in self.ledger["records"]:
            with self.subTest(model_id=row["model_id"]):
                reference = ROOT / row["provenance"]["reference"]
                self.assertTrue(reference.is_file(), row["provenance"]["reference"])
                document = json.loads(reference.read_text(encoding="utf-8"))
                self.assertEqual(document["ledger_record"]["model_id"], row["model_id"])

    def test_every_row_came_from_a_real_benchmark_run(self):
        """Not a provider claim, and not a documentation URL."""
        for row in self.ledger["records"]:
            with self.subTest(model_id=row["model_id"]):
                self.assertEqual(row["provenance"]["kind"], "local_benchmark_run")
                self.assertEqual(row["environment"]["protocol"], "local_inprocess")
                self.assertTrue(row["environment"]["runtime"].startswith("llama-cpp-python/"))
                self.assertNotIn("http", json.dumps(row))

    def test_the_models_the_runtime_refused_have_no_row(self):
        """BitNet and Ministral load nowhere, so there is nothing to record.

        A quarantined model appearing here would mean a score existed for an
        artifact no runtime has ever executed.
        """
        recorded = {row["model_id"] for row in self.ledger["records"]}
        for model in self.registry["models"]:
            if model["lifecycle_state"] == "QUARANTINED":
                with self.subTest(model_id=model["model_id"]):
                    self.assertNotIn(model["model_id"], recorded)

    def test_it_matches_what_the_evidence_compiles_to(self):
        """The committed file must be exactly what the evidence produces."""
        self.assertEqual(build(ROOT), self.ledger)


class TheCompilerRefusesTests(unittest.TestCase):
    """One deliberate break per rule. A refusal that cannot fire is not a rule."""

    def _refuses(self, damage, fragment: str) -> None:
        with tempfile.TemporaryDirectory() as raw:
            tmp = _sandbox(Path(raw))
            damage(tmp)
            with self.assertRaises(LedgerRefused) as caught:
                collect_rows(tmp)
            self.assertIn(fragment, str(caught.exception))

    def test_a_score_measured_on_other_bytes_is_refused(self):
        """The whole reason a ledger binds to a digest."""
        self._refuses(
            lambda tmp: _edit_evidence(
                tmp, "WAVE0_CAPABILITY_PHI3_MINI.json",
                lambda d: d["artifact_identity"].__setitem__("artifact_sha256", "f" * 64)),
            "can never be inherited",
        )

    def test_a_row_for_a_model_nothing_admitted_is_refused(self):
        self._refuses(
            lambda tmp: _edit_evidence(
                tmp, "WAVE0_CAPABILITY_PHI3_MINI.json",
                lambda d: d["ledger_record"].__setitem__("model_id", "nobody/unadmitted")),
            "not a registry row",
        )

    def test_a_score_disagreeing_with_the_registry_is_refused(self):
        """Two records of one measurement drifting apart is a fabrication in
        whichever of the two is wrong, and nothing says which."""
        self._refuses(
            lambda tmp: _edit_evidence(
                tmp, "WAVE0_CAPABILITY_PHI3_MINI.json",
                lambda d: d["ledger_record"].__setitem__("score", 0.99)),
            "disagrees with the registry",
        )

    def test_an_untraceable_row_is_refused(self):
        self._refuses(
            lambda tmp: _edit_evidence(
                tmp, "WAVE0_CAPABILITY_PHI3_MINI.json",
                lambda d: d["ledger_record"].__setitem__("benchmark_id", "")),
            "not traceable",
        )

    def test_an_evidence_id_naming_a_different_digest_is_refused(self):
        self._refuses(
            lambda tmp: _edit_evidence(
                tmp, "WAVE0_CAPABILITY_PHI3_MINI.json",
                lambda d: d["ledger_record"].__setitem__(
                    "evidence_id", "local_core_reasoning-000000000000-f0a0ae922cf3")),
            "does not name the digest",
        )

    def test_a_registry_row_whose_own_evidence_is_unbound_is_refused(self):
        def damage(tmp):
            path = tmp / REGISTRY_REL
            registry = yaml.safe_load(path.read_text(encoding="utf-8"))
            for model in registry["models"]:
                if model["model_id"] == "microsoft/Phi-3-mini-4k-instruct-gguf":
                    model["capability_evidence"]["text_reasoning"]["artifact_sha256"] = "a" * 64
            path.write_text(yaml.safe_dump(registry), encoding="utf-8")

        self._refuses(damage, "not bound to that row's artifact digest")

    def test_a_refused_measurement_contributes_nothing_and_is_not_an_error(self):
        """BitNet's run was REFUSED; that is a state, not a failure to compile."""
        with tempfile.TemporaryDirectory() as raw:
            tmp = _sandbox(Path(raw))
            rows = collect_rows(tmp)
            self.assertTrue(rows)
            self.assertNotIn(
                "microsoft/bitnet-b1.58-2B-4T-gguf",
                {row["model_id"] for row in rows},
            )

    def test_a_documentation_url_cannot_become_a_row(self):
        """There is no path from a provider's self-report into this ledger.

        The compiler reads benchmark evidence files and nothing else, so a
        capability declared with only a source URL - which is what every remote
        candidate in active.json carries - produces no row at all.
        """
        with tempfile.TemporaryDirectory() as raw:
            tmp = _sandbox(Path(raw))
            (tmp / EVIDENCE_REL / "WAVE0_CAPABILITY_FAKE.json").write_text(
                json.dumps({
                    "measured": True,
                    "artifact_identity": {"artifact_sha256": "d" * 64},
                    "ledger_record": {
                        "evidence_id": f"doc-{'d' * 12}-x",
                        "provider_id": "groq",
                        "model_id": "openai/gpt-oss-120b",
                        "model_family": "gpt-oss-120b",
                        "capability": "text_reasoning",
                        "benchmark_id": "vendor_docs",
                        "benchmark_version": "1",
                        "score": 0.85,
                        "threshold": 0.35,
                        "passed": True,
                        "measured_at": "2026-09-15T09:40:00+00:00",
                        "source_sha": "0" * 40,
                        "environment": {"protocol": "documentation"},
                        "provenance": {"kind": "documentation",
                                       "reference": "https://console.groq.com/docs/models"},
                    },
                }), encoding="utf-8")
            with self.assertRaises(LedgerRefused) as caught:
                collect_rows(tmp)
            self.assertIn("not a registry row", str(caught.exception))


if __name__ == "__main__":
    unittest.main()
