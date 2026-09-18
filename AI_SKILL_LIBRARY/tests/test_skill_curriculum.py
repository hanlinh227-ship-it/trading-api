"""Contract tests for the Continuous Skill Learning Fabric's canonical artifacts.

The Fabric is allowed to propose and required to prove. Everything it writes is
therefore a *data* surface: curriculum material, measured competency, sanitized
experience, bounded cycles, promotion evidence. None of it may become a second
Brain, router, scheduler, model authority or evidence authority.

Three properties are load-bearing enough that they are enforced structurally in
the schemas rather than described in prose, and asserted here:

1. authority is declared false on every artifact, by name, not by omission;
2. privacy is a closed field set - an experience row rejects any field it was
   not designed to hold, so "we forgot to strip it" cannot become "we stored it";
3. a competency row cannot reach PROFICIENT or PRIMARY without a measurement,
   an evidence reference and a timestamp for when it was taken.

Seeds are deliberately empty. A seeded score would be a fabricated measurement,
and the whole point of the matrix is that it only ever contains measured things.
"""
from __future__ import annotations

import json
import unittest
from pathlib import Path

import yaml
from jsonschema import Draft202012Validator

ROOT = Path(__file__).resolve().parents[2]
LEARNING = ROOT / "AI_SKILL_LIBRARY/v4/learning"
SCHEMAS = ROOT / "AI_SKILL_LIBRARY/v4/schemas"
ROLE_BRANCHES = ROOT / "AI_SKILL_LIBRARY/v4/model_mesh/role_branches.yaml"

#: The authority flags every Fabric artifact must deny by name. Denial by
#: omission is not denial; a reader of a file that never mentions routing has no
#: way to tell "does not route" from "nobody thought about routing yet".
REQUIRED_AUTHORITY_FLAGS = (
    "routing_authority",
    "model_selection_authority",
    "admission_authority",
    "scheduling_authority",
    "stable_write_authority",
    "merge_authority",
    "trading_authority",
)

#: Exactly the observable fields an execution may leave behind, from the design's
#: section 4.2. Anything not on this list is not "extra", it is rejected.
ALLOWED_EXPERIENCE_FIELDS = {
    "experience_id",
    "timestamp",
    "request_class",
    "role_id",
    "skill_ids",
    "model_id",
    "provider_id",
    "worker_id",
    "latency_ms",
    "success",
    "failure_class",
    "verifier_passed",
    "retry_count",
    "escalation_path",
    "fallback_path",
    "resource_observation",
    "quota_impact",
    "user_feedback_signal",
    "evidence_ref",
}

FORBIDDEN_EXPERIENCE_FIELDS = (
    "raw_prompt",
    "raw_private_chat",
    "hidden_reasoning",
    "chain_of_thought",
    "secret",
    "credentials",
)

COMPETENCY_STATES = [
    "NOT_TESTED",
    "ELIGIBLE",
    "LEARNING",
    "MEASURED",
    "PROFICIENT",
    "PRIMARY",
    "FALLBACK",
    "QUARANTINED",
]

MEASURED_ONLY_STATES = ("PROFICIENT", "PRIMARY")


def _yaml(path: Path):
    return yaml.safe_load(path.read_text(encoding="utf-8"))


def _json(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def _authority_flags(document) -> dict:
    """The named flags, wherever the artifact's own shape puts them.

    YAML surfaces carry an ``authority`` mapping; the JSON ledgers carry the
    canonical scalar ``authority: false`` and so hold the named flags beside it.
    """
    authority = document.get("authority")
    if isinstance(authority, dict):
        return authority
    return document.get("authority_flags") or {}


class SeedArtifactTests(unittest.TestCase):
    def test_seed_artifacts_are_non_authoritative(self):
        curriculum = _yaml(LEARNING / "skill_curriculum.yaml")
        matrix = _json(LEARNING / "skill_competency_matrix.json")
        ledger = _json(LEARNING / "experience_ledger.json")

        self.assertIs(curriculum["authority"]["routing_authority"], False)
        self.assertIs(curriculum["authority"]["model_selection_authority"], False)
        self.assertIs(matrix["authority"], False)
        self.assertIs(ledger["authority"], False)

    def test_every_artifact_denies_every_authority_by_name(self):
        documents = {
            "skill_curriculum.yaml": _yaml(LEARNING / "skill_curriculum.yaml"),
            "learning_cycles.yaml": _yaml(LEARNING / "learning_cycles.yaml"),
            "skill_competency_matrix.json": _json(LEARNING / "skill_competency_matrix.json"),
            "experience_ledger.json": _json(LEARNING / "experience_ledger.json"),
            "promotion_evidence.json": _json(LEARNING / "promotion_evidence.json"),
        }
        for name, document in documents.items():
            flags = _authority_flags(document)
            for flag in REQUIRED_AUTHORITY_FLAGS:
                self.assertIn(flag, flags, f"{name} does not declare {flag}")
                self.assertIs(flags[flag], False, f"{name}: {flag} must be false")

    def test_no_artifact_permits_a_direct_stable_write(self):
        for name in ("skill_curriculum.yaml", "learning_cycles.yaml"):
            self.assertIs(_yaml(LEARNING / name)["stable_write_allowed"], False, name)
        for name in ("skill_competency_matrix.json", "experience_ledger.json",
                     "promotion_evidence.json"):
            self.assertIs(_json(LEARNING / name)["stable_write"], False, name)

    def test_seeds_carry_structure_but_no_fabricated_measurements(self):
        self.assertEqual(_yaml(LEARNING / "skill_curriculum.yaml")["curricula"], [])
        self.assertEqual(_json(LEARNING / "skill_competency_matrix.json")["rows"], [])
        self.assertEqual(_json(LEARNING / "experience_ledger.json")["experiences"], [])
        self.assertEqual(_json(LEARNING / "promotion_evidence.json")["records"], [])

    def test_learning_cycles_are_bounded_and_replay_driven(self):
        cycles = _yaml(LEARNING / "learning_cycles.yaml")
        self.assertEqual(
            cycles["states"],
            ["OBSERVED", "REPLAY_FROZEN", "EVALUATED", "PROMOTION_CANDIDATE",
             "REJECTED", "HUMAN_GATE", "COMPLETE"],
        )
        requirements = cycles["requirements"]
        self.assertIs(requirements["frozen_replay"], True)
        self.assertIs(requirements["verifier_required"], True)
        self.assertEqual(requirements["protected_regressions_max"], 0)
        self.assertIs(requirements["stable_direct_write"], False)


class SchemaWellFormednessTests(unittest.TestCase):
    SCHEMA_FILES = (
        "skill_curriculum.schema.json",
        "skill_competency_matrix.schema.json",
        "experience_ledger.schema.json",
    )

    def test_schemas_are_valid_draft_2020_12(self):
        for name in self.SCHEMA_FILES:
            Draft202012Validator.check_schema(_json(SCHEMAS / name))

    def test_seeds_validate_against_their_schemas(self):
        pairs = (
            ("skill_curriculum.schema.json", _yaml(LEARNING / "skill_curriculum.yaml")),
            ("skill_competency_matrix.schema.json",
             _json(LEARNING / "skill_competency_matrix.json")),
            ("experience_ledger.schema.json", _json(LEARNING / "experience_ledger.json")),
        )
        for schema_name, document in pairs:
            validator = Draft202012Validator(_json(SCHEMAS / schema_name))
            errors = sorted(validator.iter_errors(document), key=str)
            self.assertEqual([e.message for e in errors], [], schema_name)


class ExperiencePrivacyTests(unittest.TestCase):
    def _row_schema(self):
        return _json(SCHEMAS / "experience_ledger.schema.json")["properties"]["experiences"]["items"]

    def test_experience_schema_has_no_raw_prompt_or_hidden_reasoning_fields(self):
        row_props = self._row_schema()["properties"]
        for forbidden in FORBIDDEN_EXPERIENCE_FIELDS:
            self.assertNotIn(forbidden, row_props)

    def test_experience_row_is_a_closed_field_set(self):
        row = self._row_schema()
        self.assertIs(row["additionalProperties"], False)
        self.assertEqual(set(row["properties"]), ALLOWED_EXPERIENCE_FIELDS)

    def test_unknown_experience_field_is_rejected_not_stored(self):
        validator = Draft202012Validator(_json(SCHEMAS / "experience_ledger.schema.json"))
        for forbidden in FORBIDDEN_EXPERIENCE_FIELDS + ("anything_at_all",):
            document = {
                "version": 1,
                "ledger_id": "EXPERIENCE_LEDGER",
                "authority": False,
                "stable_write": False,
                "authority_flags": {flag: False for flag in REQUIRED_AUTHORITY_FLAGS},
                "experiences": [
                    {
                        "experience_id": "exp-1",
                        "timestamp": "2026-09-18T00:00:00Z",
                        "request_class": "coding",
                        "role_id": "CODING_BRANCH",
                        "success": True,
                        "verifier_passed": True,
                        "evidence_ref": "CHECKPOINTS/evidence/example.json",
                        forbidden: "x",
                    }
                ],
            }
            self.assertTrue(
                list(validator.iter_errors(document)),
                f"experience row accepted an unknown field: {forbidden}",
            )


class CompetencyEvidenceTests(unittest.TestCase):
    def _schema(self):
        return _json(SCHEMAS / "skill_competency_matrix.schema.json")

    def _row_schema(self):
        return self._schema()["properties"]["rows"]["items"]

    def _document(self, row):
        return {
            "version": 1,
            "matrix_id": "SKILL_COMPETENCY_MATRIX",
            "authority": False,
            "stable_write": False,
            "authority_flags": {flag: False for flag in REQUIRED_AUTHORITY_FLAGS},
            "rows": [row],
        }

    def test_competency_primary_requires_evidence_shape(self):
        schema = self._schema()
        Draft202012Validator.check_schema(schema)
        self.assertIn("evidence_refs", schema["properties"]["rows"]["items"]["required"])

    def test_state_vocabulary_is_exactly_the_designed_states(self):
        self.assertEqual(self._row_schema()["properties"]["state"]["enum"], COMPETENCY_STATES)

    def test_row_identity_is_model_by_skill_by_role(self):
        required = self._row_schema()["required"]
        for key in ("model_id", "skill_id", "role_id", "state",
                    "evidence_refs", "protected_regression_status"):
            self.assertIn(key, required)

    def test_proficient_or_primary_without_measurement_is_rejected(self):
        validator = Draft202012Validator(self._schema())
        for state in MEASURED_ONLY_STATES:
            base = {
                "model_id": "some/model",
                "skill_id": "some_skill",
                "role_id": "CODING_BRANCH",
                "state": state,
                "evidence_refs": ["CHECKPOINTS/evidence/example.json"],
                "protected_regression_status": "PASS",
                "measured_score": 0.9,
                "verifier_pass_rate": 0.9,
                "last_measured_at": "2026-09-18T00:00:00Z",
            }
            self.assertEqual(
                [e.message for e in validator.iter_errors(self._document(base))], [], state
            )
            for missing in ("measured_score", "verifier_pass_rate", "last_measured_at"):
                row = dict(base)
                row.pop(missing)
                self.assertTrue(
                    list(validator.iter_errors(self._document(row))),
                    f"{state} accepted without {missing}",
                )
            empty_evidence = dict(base, evidence_refs=[])
            self.assertTrue(
                list(validator.iter_errors(self._document(empty_evidence))),
                f"{state} accepted with no evidence_refs",
            )

    def test_unmeasured_states_remain_representable(self):
        validator = Draft202012Validator(self._schema())
        row = {
            "model_id": "some/model",
            "skill_id": "some_skill",
            "role_id": "CODING_BRANCH",
            "state": "NOT_TESTED",
            "evidence_refs": [],
            "protected_regression_status": "NOT_RUN",
        }
        self.assertEqual([e.message for e in validator.iter_errors(self._document(row))], [])


class VocabularyReuseTests(unittest.TestCase):
    """Role IDs come from role_branches.yaml; nothing here invents a taxonomy."""

    def _role_ids(self):
        branches = _yaml(ROLE_BRANCHES)["branches"]
        return [branch["role_id"] for branch in branches]

    def test_no_schema_hardcodes_a_second_role_vocabulary(self):
        role_ids = set(self._role_ids())
        for name in ("skill_curriculum.schema.json", "skill_competency_matrix.schema.json",
                     "experience_ledger.schema.json"):
            text = (SCHEMAS / name).read_text(encoding="utf-8")
            for role_id in role_ids:
                self.assertNotIn(role_id, text,
                                 f"{name} copies the role vocabulary instead of referencing it")

    def test_role_pattern_accepts_every_canonical_role_id(self):
        import re

        schema = _json(SCHEMAS / "skill_competency_matrix.schema.json")
        pattern = re.compile(schema["properties"]["rows"]["items"]["properties"]["role_id"]["pattern"])
        for role_id in self._role_ids():
            self.assertTrue(pattern.match(role_id), role_id)

    def test_fabric_declares_no_second_control_plane(self):
        forbidden = ("router", "brain", "scheduler", "model_selection_source",
                     "admission_source")
        for name in ("skill_curriculum.yaml", "learning_cycles.yaml"):
            document = _yaml(LEARNING / name)
            for key in document:
                self.assertNotIn(key, forbidden, f"{name} declares {key}")


class LearningPolicyDeclarationTests(unittest.TestCase):
    def _policy(self):
        return _yaml(LEARNING / "policy.yaml")

    def test_policy_declares_the_new_surfaces(self):
        block = self._policy()["continuous_skill_learning"]
        expected = {
            "curriculum_path": "AI_SKILL_LIBRARY/v4/learning/skill_curriculum.yaml",
            "competency_matrix_path": "AI_SKILL_LIBRARY/v4/learning/skill_competency_matrix.json",
            "experience_ledger_path": "AI_SKILL_LIBRARY/v4/learning/experience_ledger.json",
            "learning_cycles_path": "AI_SKILL_LIBRARY/v4/learning/learning_cycles.yaml",
            "promotion_evidence_path": "AI_SKILL_LIBRARY/v4/learning/promotion_evidence.json",
        }
        for key, rel in expected.items():
            self.assertEqual(block[key], rel)
            self.assertTrue((ROOT / rel).is_file(), rel)

    def test_policy_reaffirms_non_authority(self):
        block = self._policy()["continuous_skill_learning"]
        self.assertIs(block["routing_authority"], False)
        self.assertIs(block["model_selection_authority"], False)
        self.assertIs(block["stable_write_allowed"], False)
        self.assertIs(block["weight_fine_tuning_required"], False)

    def test_existing_policy_invariants_survive(self):
        policy = self._policy()
        self.assertIs(policy["routing_authority"], False)
        self.assertEqual(policy["stable_direct_write"], "forbidden")
        self.assertEqual(policy["hidden_reasoning_persistence"], "forbidden")
        self.assertEqual(policy["financial_execution_by_learning"], "forbidden")
        self.assertIs(policy["promotion_requires_evidence"], True)


if __name__ == "__main__":
    unittest.main()
