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

    A scalar ``authority`` is *checked*, not stepped over. The earlier version of
    this helper fell straight through to ``authority_flags`` whenever the scalar
    was not a mapping, so a file that had quietly flipped to ``authority: true``
    read exactly like a correct one. Denial has to be observed, not assumed.
    """
    authority = document.get("authority")
    if isinstance(authority, dict):
        return authority
    if authority is not False:
        raise AssertionError(
            f"scalar authority must be exactly False, got {authority!r}"
        )
    flags = document.get("authority_flags")
    if not isinstance(flags, dict):
        raise AssertionError(
            "artifact declares neither an authority mapping nor an "
            "authority_flags block"
        )
    return flags


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


# --- Review remediation: privacy/gating/contract tests ------------------------
#
# Each class below exists because the reviewed artifacts accepted something they
# should not have. The findings were all of one kind: a field was typed as
# "a string" when what it actually is, is a *classifier*, an *identifier*, a
# *reference* or a *timestamp*. "A string" is a 2KB slot that will hold a prompt
# body and an API key just as happily as it holds "coding".

#: A realistic model id as it appears in the Model Mesh today. A tightened
#: pattern that rejects these would be a worse bug than the one it fixes.
REALISTIC_MODEL_IDS = ("Qwen/Qwen3-8B-GGUF", "@cf/baai/bge-m3", "some/model")
REALISTIC_EVIDENCE_REFS = (
    "CHECKPOINTS/evidence/WAVE0_CAPABILITY_QWEN3_8B.json",
    "artifact://learning/cycle-0001/promotion_evidence.json",
)
#: What a leaked prompt/secret actually looks like arriving through a field that
#: was only ever typed "string".
#: Deliberately not a realistic credential. What the schema actually rejects is
#: the *shape* - length, whitespace, "=" - so the fixture carries that shape and
#: nothing that a secret scanner or a reader could mistake for a real key.
LEAKY_STRING = (
    "API_KEY=EXAMPLE-NOT-A-REAL-KEY passphrase=EXAMPLE-NOT-A-REAL-PASSPHRASE "
    "and here is the user's whole prompt: " + ("please summarise this " * 60)
)
PLACEHOLDER_REFS = ("   ", "n/a", "TODO", "-", "")


class ExperienceFieldShapeTests(unittest.TestCase):
    """BLOCKER 1 - privacy has to be structural for the *allowed* fields too.

    The closed field set already stops an unknown field arriving. It does
    nothing about a known field being used as a smuggling channel.
    """

    def _validator(self):
        return Draft202012Validator(_json(SCHEMAS / "experience_ledger.schema.json"))

    def _document(self, row):
        return {
            "version": 1,
            "ledger_id": "EXPERIENCE_LEDGER",
            "authority": False,
            "stable_write": False,
            "authority_flags": {flag: False for flag in REQUIRED_AUTHORITY_FLAGS},
            "experiences": [row],
        }

    def _base_row(self, **overrides):
        row = {
            "experience_id": "exp-0001",
            "timestamp": "2026-09-18T00:00:00Z",
            "request_class": "coding",
            "success": True,
        }
        row.update(overrides)
        return row

    CLASSIFIER_FIELDS = (
        "request_class",
        "failure_class",
        "resource_observation",
        "quota_impact",
    )
    IDENTIFIER_FIELDS = ("experience_id", "model_id", "provider_id", "worker_id")

    def test_classifier_fields_reject_prose_and_secrets(self):
        validator = self._validator()
        for field in self.CLASSIFIER_FIELDS:
            document = self._document(self._base_row(**{field: LEAKY_STRING}))
            self.assertTrue(
                list(validator.iter_errors(document)),
                f"{field} accepted a 2KB prose/secret blob",
            )

    def test_identifier_fields_reject_prose_and_secrets(self):
        validator = self._validator()
        for field in self.IDENTIFIER_FIELDS:
            document = self._document(self._base_row(**{field: LEAKY_STRING}))
            self.assertTrue(
                list(validator.iter_errors(document)),
                f"{field} accepted a 2KB prose/secret blob",
            )

    def test_identifier_fields_still_accept_real_model_ids(self):
        validator = self._validator()
        for model_id in REALISTIC_MODEL_IDS:
            document = self._document(
                self._base_row(model_id=model_id, provider_id="cloudflare_workers_ai",
                               worker_id="cf-worker-01")
            )
            self.assertEqual(
                [e.message for e in validator.iter_errors(document)], [], model_id
            )

    def test_id_and_path_arrays_reject_prose_and_are_bounded(self):
        validator = self._validator()
        for field in ("skill_ids", "escalation_path", "fallback_path"):
            leaky = self._document(self._base_row(**{field: [LEAKY_STRING]}))
            self.assertTrue(
                list(validator.iter_errors(leaky)),
                f"{field} accepted a 2KB prose/secret blob as an item",
            )
            unbounded = self._document(
                self._base_row(**{field: [f"skill-{n}" for n in range(4096)]})
            )
            self.assertTrue(
                list(validator.iter_errors(unbounded)),
                f"{field} accepted an unbounded array",
            )

    def test_experiences_array_itself_is_bounded(self):
        schema = _json(SCHEMAS / "experience_ledger.schema.json")
        self.assertIn("maxItems", schema["properties"]["experiences"])

    def test_evidence_ref_must_look_like_a_reference(self):
        validator = self._validator()
        for ref in REALISTIC_EVIDENCE_REFS:
            document = self._document(self._base_row(evidence_ref=ref))
            self.assertEqual(
                [e.message for e in validator.iter_errors(document)], [], ref
            )
        for junk in PLACEHOLDER_REFS + (LEAKY_STRING,):
            document = self._document(self._base_row(evidence_ref=junk))
            self.assertTrue(
                list(validator.iter_errors(document)),
                f"evidence_ref accepted a non-reference: {junk!r}",
            )

    def test_timestamp_is_enforced_not_merely_annotated(self):
        validator = self._validator()
        for bad in ("not-a-date", "tomorrow", "2026-13-45", "18/09/2026", ""):
            document = self._document(self._base_row(timestamp=bad))
            self.assertTrue(
                list(validator.iter_errors(document)),
                f"timestamp accepted {bad!r}; format: date-time is annotation-only",
            )
        for good in ("2026-09-18T00:00:00Z", "2026-09-18T00:00:00.123456Z",
                     "2026-09-18T07:00:00+07:00"):
            document = self._document(self._base_row(timestamp=good))
            self.assertEqual(
                [e.message for e in validator.iter_errors(document)], [], good
            )


class CompetencyGateTests(unittest.TestCase):
    """BLOCKER 2 and SHOULD-FIX 3/4/5 - the states a reader acts on."""

    def _validator(self):
        return Draft202012Validator(_json(SCHEMAS / "skill_competency_matrix.schema.json"))

    def _document(self, row):
        return {
            "version": 1,
            "matrix_id": "SKILL_COMPETENCY_MATRIX",
            "authority": False,
            "stable_write": False,
            "authority_flags": {flag: False for flag in REQUIRED_AUTHORITY_FLAGS},
            "rows": [row],
        }

    def _measured_row(self, **overrides):
        row = {
            "model_id": "Qwen/Qwen3-8B-GGUF",
            "skill_id": "some_skill",
            "role_id": "CODING_BRANCH",
            "state": "PRIMARY",
            "evidence_refs": ["CHECKPOINTS/evidence/WAVE0_CAPABILITY_QWEN3_8B.json"],
            "protected_regression_status": "PASS",
            "measured_score": 0.91,
            "verifier_pass_rate": 0.88,
            "last_measured_at": "2026-09-18T00:00:00Z",
        }
        row.update(overrides)
        return row

    def test_fallback_is_gated_like_any_other_operational_state(self):
        """Selecting a fallback is an operational decision (design s10/s15)."""
        validator = self._validator()
        ungated = {
            "model_id": "m",
            "skill_id": "s",
            "role_id": "CODING_BRANCH",
            "state": "FALLBACK",
            "evidence_refs": [],
            "protected_regression_status": "NOT_RUN",
        }
        self.assertTrue(
            list(validator.iter_errors(self._document(ungated))),
            "FALLBACK accepted with no evidence and no regression run",
        )
        failed = dict(ungated, protected_regression_status="FAIL")
        self.assertTrue(
            list(validator.iter_errors(self._document(failed))),
            "FALLBACK accepted on a FAILED protected regression",
        )
        good = self._measured_row(state="FALLBACK")
        self.assertEqual(
            [e.message for e in validator.iter_errors(self._document(good))], []
        )

    def test_evidence_refs_reject_placeholders(self):
        validator = self._validator()
        for junk in PLACEHOLDER_REFS:
            row = self._measured_row(evidence_refs=[junk])
            self.assertTrue(
                list(validator.iter_errors(self._document(row))),
                f"evidence_refs accepted a placeholder: {junk!r}",
            )
        for ref in REALISTIC_EVIDENCE_REFS:
            row = self._measured_row(evidence_refs=[ref])
            self.assertEqual(
                [e.message for e in validator.iter_errors(self._document(row))], [], ref
            )

    def test_last_measured_at_is_enforced_not_merely_annotated(self):
        validator = self._validator()
        for bad in ("tomorrow", "not-a-date", "2026-09-18"):
            row = self._measured_row(last_measured_at=bad)
            self.assertTrue(
                list(validator.iter_errors(self._document(row))),
                f"last_measured_at accepted {bad!r}",
            )

    def test_operational_states_need_a_score_above_the_capability_floor(self):
        """A model that failed every run may not be PRIMARY.

        The floor reuses hard_capability_min_score from
        AI_SKILL_LIBRARY/v4/model_mesh/domain_capabilities.yaml rather than
        inventing a second number.
        """
        validator = self._validator()
        for state in ("PROFICIENT", "PRIMARY", "FALLBACK"):
            floored = self._measured_row(state=state, measured_score=0.0,
                                         verifier_pass_rate=0.0)
            self.assertTrue(
                list(validator.iter_errors(self._document(floored))),
                f"{state} accepted with measured_score 0 and verifier_pass_rate 0",
            )
            just_under = self._measured_row(state=state, measured_score=0.34,
                                            verifier_pass_rate=0.34)
            self.assertTrue(
                list(validator.iter_errors(self._document(just_under))),
                f"{state} accepted below the capability floor",
            )
            at_floor = self._measured_row(state=state, measured_score=0.35,
                                          verifier_pass_rate=0.35)
            self.assertEqual(
                [e.message for e in validator.iter_errors(self._document(at_floor))],
                [], f"{state} rejected at the documented capability floor",
            )

    def test_matrix_floor_matches_the_model_mesh_capability_floor(self):
        mesh = _yaml(ROOT / "AI_SKILL_LIBRARY/v4/model_mesh/domain_capabilities.yaml")
        floor = mesh["policy"]["hard_capability_min_score"]
        text = (SCHEMAS / "skill_competency_matrix.schema.json").read_text(encoding="utf-8")
        self.assertIn(str(floor), text)

    def test_promoted_requires_evidence_and_a_promotion_evidence_ref(self):
        validator = self._validator()
        bogus = {
            "model_id": "m/x",
            "skill_id": "s",
            "role_id": "CODING_BRANCH",
            "state": "NOT_TESTED",
            "evidence_refs": [],
            "protected_regression_status": "NOT_RUN",
            "promotion_state": "PROMOTED",
        }
        self.assertTrue(
            list(validator.iter_errors(self._document(bogus))),
            "PROMOTED accepted on an untested row with no evidence",
        )
        no_ref = self._measured_row(promotion_state="PROMOTED")
        self.assertTrue(
            list(validator.iter_errors(self._document(no_ref))),
            "PROMOTED accepted with no promotion_evidence_ref",
        )
        good = self._measured_row(
            promotion_state="PROMOTED",
            promotion_evidence_ref="CHECKPOINTS/evidence/promotion_cycle_0001.json",
        )
        self.assertEqual(
            [e.message for e in validator.iter_errors(self._document(good))], []
        )

    def test_matrix_identifier_fields_reject_prose_and_keep_real_ids(self):
        validator = self._validator()
        for field in ("model_id", "skill_id"):
            row = self._measured_row(**{field: LEAKY_STRING})
            self.assertTrue(
                list(validator.iter_errors(self._document(row))),
                f"{field} accepted a 2KB prose/secret blob",
            )
        for model_id in REALISTIC_MODEL_IDS:
            row = self._measured_row(model_id=model_id)
            self.assertEqual(
                [e.message for e in validator.iter_errors(self._document(row))],
                [], model_id,
            )

    def test_rows_array_is_bounded(self):
        schema = _json(SCHEMAS / "skill_competency_matrix.schema.json")
        self.assertIn("maxItems", schema["properties"]["rows"])


class CurriculumContractTests(unittest.TestCase):
    """SHOULD-FIX 8 - a curriculum CONTAINS privacy and invariants (design s4.1/s8)."""

    def _validator(self):
        return Draft202012Validator(_json(SCHEMAS / "skill_curriculum.schema.json"))

    def _document(self, entry):
        authority = {
            "routing_authority": False,
            "reasoning_authority": False,
            "model_selection_authority": False,
            "admission_authority": False,
            "scheduling_authority": False,
            "evidence_authority": False,
            "stable_write_authority": False,
            "merge_authority": False,
            "trading_authority": False,
        }
        return {
            "version": 1,
            "status": "CANONICAL",
            "authority": dict(authority),
            "stable_write_allowed": False,
            "curricula": [dict(entry, authority=dict(authority))],
        }

    def _entry(self, **overrides):
        entry = {
            "skill_id": "some_skill",
            "domain": "core",
            "roles": ["CODING_BRANCH"],
            "triggers": ["refactor a module"],
            "capabilities": ["coding"],
            "permissions": {
                "inherited_from": "AI_SKILL_LIBRARY/v4/skills/some_skill.yaml",
                "permission_ceiling": ["read_repo"],
                "widened_by_learning": False,
            },
            "privacy_constraints": ["no_raw_prompt_persistence"],
            "protected_invariants": ["authority_invariants"],
            "risk_class": "A",
            "output_contract": "a unified diff",
            "evals": [],
            "verifier_required": True,
            "promotion_class": "A",
        }
        entry.update(overrides)
        return entry

    def test_privacy_and_invariants_are_required_not_optional(self):
        validator = self._validator()
        self.assertEqual(
            [e.message for e in validator.iter_errors(self._document(self._entry()))], []
        )
        for field in ("privacy_constraints", "protected_invariants"):
            entry = self._entry()
            entry.pop(field)
            self.assertTrue(
                list(validator.iter_errors(self._document(entry))),
                f"curriculum entry accepted without {field}",
            )

    def test_promotion_class_may_never_be_more_permissive_than_risk_class(self):
        """Design s11: learning must never lower a risk class."""
        validator = self._validator()
        order = ["A", "B", "C", "D"]
        for risk in order:
            for promotion in order:
                entry = self._entry(risk_class=risk, promotion_class=promotion)
                errors = list(validator.iter_errors(self._document(entry)))
                permissive = order.index(promotion) < order.index(risk)
                if permissive:
                    self.assertTrue(
                        errors,
                        f"risk_class {risk} accepted the more permissive "
                        f"promotion_class {promotion}",
                    )
                else:
                    self.assertEqual(
                        [e.message for e in errors], [],
                        f"risk_class {risk} rejected promotion_class {promotion}",
                    )


class UnschemaedArtifactTests(unittest.TestCase):
    """SHOULD-FIX 6 - learning_cycles.yaml and promotion_evidence.json.

    Neither has a schema, so the assertions are the only thing standing between
    them and a silent authority flip.
    """

    FILES = (
        ("learning_cycles.yaml", _yaml),
        ("promotion_evidence.json", _json),
    )

    def test_helper_rejects_a_scalar_true_authority(self):
        with self.assertRaises(AssertionError):
            _authority_flags({"authority": True, "authority_flags":
                              {flag: False for flag in REQUIRED_AUTHORITY_FLAGS}})

    def test_helper_rejects_a_missing_authority_declaration(self):
        with self.assertRaises(AssertionError):
            _authority_flags({"authority_flags": {}})

    def test_scalar_authority_on_unschemaed_artifacts_is_exactly_false(self):
        for name, loader in self.FILES:
            document = loader(LEARNING / name)
            self.assertIn("authority", document, name)
            self.assertIs(document["authority"], False, name)
            self.assertIsInstance(document.get("authority_flags"), dict, name)

    def test_unschemaed_artifacts_deny_every_authority_by_name(self):
        for name, loader in self.FILES:
            flags = _authority_flags(loader(LEARNING / name))
            for flag in REQUIRED_AUTHORITY_FLAGS + ("reasoning_authority",
                                                    "evidence_authority"):
                self.assertIn(flag, flags, f"{name} does not declare {flag}")
                self.assertIs(flags[flag], False, f"{name}: {flag} must be false")

    def test_promotion_evidence_records_a_decision_it_does_not_make_one(self):
        document = _json(LEARNING / "promotion_evidence.json")
        self.assertEqual(document["ledger_id"], "LEARNING_PROMOTION_EVIDENCE")
        self.assertIs(document["stable_write"], False)
        self.assertEqual(document["records"], [])

    def test_learning_cycles_declare_zero_tolerance_protected_dimensions(self):
        document = _yaml(LEARNING / "learning_cycles.yaml")
        self.assertIs(document["stable_write_allowed"], False)
        self.assertEqual(document["requirements"]["protected_regressions_max"], 0)
        for dimension in ("reliability", "security", "instruction_adherence",
                          "vietnamese_retention", "privacy_policy",
                          "authority_invariants", "provenance_requirements"):
            self.assertIn(dimension, document["protected_dimensions"])


class RolePatternRejectionTests(unittest.TestCase):
    """SHOULD-FIX 7 - the accepting test alone is satisfied by '^.*$'."""

    REJECTED = ("coding_branch", "CODING", "", "NOT A BRANCH", "_BRANCH",
                "CODING_BRANCH_EXTRA", "1CODING_BRANCH")

    def _patterns(self):
        import re

        matrix = _json(SCHEMAS / "skill_competency_matrix.schema.json")
        ledger = _json(SCHEMAS / "experience_ledger.schema.json")
        curriculum = _json(SCHEMAS / "skill_curriculum.schema.json")
        return {
            "skill_competency_matrix.schema.json":
                matrix["properties"]["rows"]["items"]["properties"]["role_id"]["pattern"],
            "experience_ledger.schema.json":
                ledger["properties"]["experiences"]["items"]["properties"]["role_id"]["pattern"],
            "skill_curriculum.schema.json":
                curriculum["$defs"]["role_id"]["pattern"],
        }

    def test_role_pattern_rejects_non_role_ids(self):
        import re

        for name, pattern in self._patterns().items():
            compiled = re.compile(pattern)
            for bad in self.REJECTED:
                self.assertIsNone(
                    compiled.fullmatch(bad),
                    f"{name} role_id pattern accepted {bad!r}",
                )

    def test_role_pattern_still_accepts_every_canonical_role_id(self):
        import re

        role_ids = [branch["role_id"] for branch in _yaml(ROLE_BRANCHES)["branches"]]
        for name, pattern in self._patterns().items():
            compiled = re.compile(pattern)
            for role_id in role_ids:
                self.assertIsNotNone(compiled.fullmatch(role_id), f"{name}: {role_id}")


if __name__ == "__main__":
    unittest.main()
