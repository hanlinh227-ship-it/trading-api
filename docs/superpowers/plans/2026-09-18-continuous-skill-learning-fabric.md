# Continuous Skill Learning Fabric Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a governed Continuous Skill Learning Fabric that compiles canonical skills into curricula, records sanitized execution experience, measures MODEL × SKILL × ROLE competency, runs bounded learning cycles, and promotes only evidence-backed improvements without creating any parallel authority.

**Architecture:** Reuse the existing `learning/policy.yaml`, `skill_factory.yaml`, `skill_evo.yaml`, failure ledger, self-development gates, verifier, role branches, Model Mesh evidence, and release gates. New components are non-authoritative data/evaluation helpers only: curriculum compiler, sanitized experience intake, competency matrix builder, and bounded learning-cycle orchestrator. Stable writes remain behind the existing promotion pipeline; model-role preference changes are emitted as candidates/evidence, never applied by the learning layer directly.

**Tech Stack:** Python 3, stdlib `json`/`pathlib`/`hashlib`/`datetime`, YAML already used by the repo, JSON Schema draft 2020-12, unittest/pytest-compatible test suite, existing AI Core CLI/tools.

**Spec:** `docs/superpowers/specs/2026-09-18-continuous-skill-learning-fabric-design.md`

## Global Constraints

- `GITHUB_BRAIN_V4` remains the sole Brain authority.
- `task_router` remains the sole routing authority.
- Model Mesh remains the sole model/provider selection authority.
- Open Model Universe remains the sole model admission/governance authority.
- The existing runtime scheduler remains the sole placement/execution scheduling authority.
- The existing verifier/evidence path remains the sole proof/reconciliation authority.
- The Learning Fabric has no routing, admission, scheduling, permission, trading, or merge authority.
- `stable_direct_write: forbidden` remains true.
- `permission_expansion_by_learning: forbidden` remains true.
- `learning_can_self_approve_authority_change: false` remains true.
- Hidden reasoning persistence is forbidden.
- Secret/private prompt persistence is forbidden.
- Financial execution by learning is forbidden.
- Paid APIs remain disabled unless explicitly authorized elsewhere.
- No live trading capability is introduced.
- No model is marked proficient/primary for a skill without measured evidence.
- No protected regression is tolerated unless an existing canonical policy explicitly allows it.
- Prefer strengthening an existing skill before creating a new primary skill.
- The implementation must be useful with zero weight fine-tuning.

---

## File Structure

**Create**
- `AI_SKILL_LIBRARY/v4/learning/skill_curriculum.yaml` — compiled, non-authoritative curriculum catalog.
- `AI_SKILL_LIBRARY/v4/learning/skill_competency_matrix.json` — evidence-backed MODEL × SKILL × ROLE measurements.
- `AI_SKILL_LIBRARY/v4/learning/experience_ledger.json` — sanitized execution outcomes only.
- `AI_SKILL_LIBRARY/v4/learning/learning_cycles.yaml` — bounded cycle policy/state schema.
- `AI_SKILL_LIBRARY/v4/learning/promotion_evidence.json` — append-safe/non-authoritative promotion evidence index.
- `AI_SKILL_LIBRARY/v4/schemas/skill_curriculum.schema.json`
- `AI_SKILL_LIBRARY/v4/schemas/skill_competency_matrix.schema.json`
- `AI_SKILL_LIBRARY/v4/schemas/experience_ledger.schema.json`
- `AI_SKILL_LIBRARY/v4/tools/compile_skill_curriculum.py`
- `AI_SKILL_LIBRARY/v4/tools/intake_experience.py`
- `AI_SKILL_LIBRARY/v4/tools/build_skill_competency.py`
- `AI_SKILL_LIBRARY/v4/tools/run_learning_cycle.py`
- `AI_SKILL_LIBRARY/tests/test_skill_curriculum.py`
- `AI_SKILL_LIBRARY/tests/test_experience_learning.py`
- `AI_SKILL_LIBRARY/tests/test_skill_competency.py`
- `AI_SKILL_LIBRARY/tests/test_learning_cycle.py`

**Modify**
- `AI_SKILL_LIBRARY/v4/learning/policy.yaml` — declare curriculum/experience/competency surfaces and reaffirm non-authority.
- `AI_SKILL_LIBRARY/v4/learning/skill_evo.yaml` — connect learning-cycle evidence to the existing promotion rules.
- `AI_SKILL_LIBRARY/v4/learning/skill_factory.yaml` — allow curriculum/competency gaps as candidate inputs without stable writes.
- `AI_SKILL_LIBRARY/v4/tools/skill_forge.py` — accept evidence-backed competency gap metadata and keep A/B/C/D promotion semantics.
- `AI_SKILL_LIBRARY/v4/tools/evaluate_skill_candidate.py` — attach competency/curriculum evidence refs to candidate evaluation.
- `AI_SKILL_LIBRARY/v4/control_plane/self_development.py` — add no new authority; only ensure learning-cycle evidence can be represented in scorecards if needed.
- `AI_SKILL_LIBRARY/v4/model_mesh/role_branches.yaml` — add a non-authoritative reference to the competency matrix as evidence input, not as selection authority.
- `AI_SKILL_LIBRARY/v4/stable/continuous_intelligence.yaml` — register the Continuous Skill Learning Fabric as a bounded background learning surface.
- `AI_SKILL_LIBRARY/v4/tools/ci_validate.py` or the repo's actual CI validation registry — add the four new test suites without creating a new CI pipeline.
- Canonical checkpoint/evidence files used by the existing AI Core release gate — record implementation proof.

---

### Task 1: Define Canonical Learning Artifacts and Schemas

**Files:**
- Create: `AI_SKILL_LIBRARY/v4/schemas/skill_curriculum.schema.json`
- Create: `AI_SKILL_LIBRARY/v4/schemas/skill_competency_matrix.schema.json`
- Create: `AI_SKILL_LIBRARY/v4/schemas/experience_ledger.schema.json`
- Create: `AI_SKILL_LIBRARY/v4/learning/skill_curriculum.yaml`
- Create: `AI_SKILL_LIBRARY/v4/learning/skill_competency_matrix.json`
- Create: `AI_SKILL_LIBRARY/v4/learning/experience_ledger.json`
- Create: `AI_SKILL_LIBRARY/v4/learning/learning_cycles.yaml`
- Create: `AI_SKILL_LIBRARY/v4/learning/promotion_evidence.json`
- Modify: `AI_SKILL_LIBRARY/v4/learning/policy.yaml`
- Test: `AI_SKILL_LIBRARY/tests/test_skill_curriculum.py`

**Interfaces:**
- Consumes: canonical skill manifests under `AI_SKILL_LIBRARY/v4/skills/*/manifest.yaml`, existing skill schema, role IDs in `role_branches.yaml`.
- Produces:
  - curriculum entries with keys `skill_id, domain, roles, triggers, capabilities, permissions, risk_class, output_contract, evals, verifier_required, promotion_class, authority`
  - competency rows with keys `model_id, skill_id, role_id, state, measured_score, verifier_pass_rate, evidence_refs, protected_regression_status, last_measured_at`
  - experience ledger rows with sanitized fields only.

- [ ] **Step 1: Write failing schema/seed tests**

Add tests equivalent to:

```python
import json
import unittest
from pathlib import Path

import yaml
from jsonschema import Draft202012Validator

ROOT = Path(__file__).resolve().parents[2]


class SkillCurriculumContractTests(unittest.TestCase):
    def test_seed_artifacts_are_non_authoritative(self):
        curriculum = yaml.safe_load((ROOT / "AI_SKILL_LIBRARY/v4/learning/skill_curriculum.yaml").read_text())
        matrix = json.loads((ROOT / "AI_SKILL_LIBRARY/v4/learning/skill_competency_matrix.json").read_text())
        ledger = json.loads((ROOT / "AI_SKILL_LIBRARY/v4/learning/experience_ledger.json").read_text())

        self.assertIs(curriculum["authority"]["routing_authority"], False)
        self.assertIs(curriculum["authority"]["model_selection_authority"], False)
        self.assertIs(matrix["authority"], False)
        self.assertIs(ledger["authority"], False)

    def test_experience_schema_has_no_raw_prompt_or_hidden_reasoning_fields(self):
        schema = json.loads((ROOT / "AI_SKILL_LIBRARY/v4/schemas/experience_ledger.schema.json").read_text())
        row_props = schema["properties"]["experiences"]["items"]["properties"]
        for forbidden in ("raw_prompt", "raw_private_chat", "hidden_reasoning", "chain_of_thought", "secret", "credentials"):
            self.assertNotIn(forbidden, row_props)

    def test_competency_primary_requires_evidence_shape(self):
        schema = json.loads((ROOT / "AI_SKILL_LIBRARY/v4/schemas/skill_competency_matrix.schema.json").read_text())
        Draft202012Validator.check_schema(schema)
        self.assertIn("evidence_refs", schema["properties"]["rows"]["items"]["required"])
```

- [ ] **Step 2: Run tests and verify failure**

Run:

```bash
python -m unittest AI_SKILL_LIBRARY.tests.test_skill_curriculum -v
```

Expected: FAIL because the new artifacts/schemas do not exist.

- [ ] **Step 3: Add minimal canonical seed artifacts**

Use exact initial semantics:

```yaml
# AI_SKILL_LIBRARY/v4/learning/skill_curriculum.yaml
version: 1
status: CANONICAL
authority:
  routing_authority: false
  reasoning_authority: false
  model_selection_authority: false
  admission_authority: false
  scheduling_authority: false
  evidence_authority: false
stable_write_allowed: false
curricula: []
```

```json
{
  "version": 1,
  "authority": false,
  "stable_write": false,
  "rows": []
}
```

Use the same empty-safe shape for `experience_ledger.json` and `promotion_evidence.json`, with top-level `authority: false`, `stable_write: false`, and arrays named `experiences` / `records`.

Use this bounded-cycle seed:

```yaml
version: 1
authority: false
stable_write_allowed: false
states:
  - OBSERVED
  - REPLAY_FROZEN
  - EVALUATED
  - PROMOTION_CANDIDATE
  - REJECTED
  - HUMAN_GATE
  - COMPLETE
requirements:
  frozen_replay: true
  verifier_required: true
  protected_regressions_max: 0
  stable_direct_write: false
```

- [ ] **Step 4: Add schemas with explicit enums**

The competency schema must use:

```json
"state": {
  "enum": [
    "NOT_TESTED",
    "ELIGIBLE",
    "LEARNING",
    "MEASURED",
    "PROFICIENT",
    "PRIMARY",
    "FALLBACK",
    "QUARANTINED"
  ]
}
```

The experience schema must set `additionalProperties: false` on each experience row and allow only:

```text
experience_id
timestamp
request_class
role_id
skill_ids
model_id
provider_id
worker_id
latency_ms
success
failure_class
verifier_passed
retry_count
escalation_path
fallback_path
resource_observation
quota_impact
user_feedback_signal
evidence_ref
```

- [ ] **Step 5: Extend learning policy without adding authority**

Append declarative paths:

```yaml
continuous_skill_learning:
  curriculum_path: AI_SKILL_LIBRARY/v4/learning/skill_curriculum.yaml
  competency_matrix_path: AI_SKILL_LIBRARY/v4/learning/skill_competency_matrix.json
  experience_ledger_path: AI_SKILL_LIBRARY/v4/learning/experience_ledger.json
  learning_cycles_path: AI_SKILL_LIBRARY/v4/learning/learning_cycles.yaml
  promotion_evidence_path: AI_SKILL_LIBRARY/v4/learning/promotion_evidence.json
  routing_authority: false
  model_selection_authority: false
  stable_write_allowed: false
  weight_fine_tuning_required: false
```

- [ ] **Step 6: Run tests**

Run:

```bash
python -m unittest AI_SKILL_LIBRARY.tests.test_skill_curriculum -v
```

Expected: PASS.

- [ ] **Step 7: Commit**

```bash
git add AI_SKILL_LIBRARY/v4/schemas AI_SKILL_LIBRARY/v4/learning AI_SKILL_LIBRARY/tests/test_skill_curriculum.py
git commit -m "feat(learning): define skill learning fabric contracts"
```

---

### Task 2: Compile Canonical Skills into Replayable Curricula

**Files:**
- Create: `AI_SKILL_LIBRARY/v4/tools/compile_skill_curriculum.py`
- Modify: `AI_SKILL_LIBRARY/v4/learning/skill_curriculum.yaml`
- Modify: `AI_SKILL_LIBRARY/v4/learning/skill_factory.yaml`
- Test: `AI_SKILL_LIBRARY/tests/test_skill_curriculum.py`

**Interfaces:**
- Consumes:
  - `compile_curriculum(root: Path) -> dict`
  - manifests from `AI_SKILL_LIBRARY/v4/skills/*/manifest.yaml`
  - legacy registry only as referenced by canonical manifests
- Produces:
  - deterministic curriculum document
  - no file mutation unless CLI `--output` is explicitly supplied
  - every curriculum entry has `authority: false`.

- [ ] **Step 1: Add failing compiler tests**

```python
from AI_SKILL_LIBRARY.v4.tools.compile_skill_curriculum import compile_curriculum


def test_compiler_discovers_all_manifest_skills(self):
    out = compile_curriculum(ROOT)
    ids = {row["skill_id"] for row in out["curricula"]}
    core = yaml.safe_load((ROOT / "AI_SKILL_LIBRARY/v4/skills/core/manifest.yaml").read_text())
    for skill_id in core["skills"]:
        self.assertIn(skill_id, ids)


def test_compiler_never_widens_permissions(self):
    out = compile_curriculum(ROOT)
    for row in out["curricula"]:
        self.assertFalse(row["authority"])
        self.assertFalse(row["stable_write_allowed"])
        self.assertNotIn("financial_execution", row["permissions"])
```

- [ ] **Step 2: Run tests and verify failure**

Run:

```bash
python -m unittest AI_SKILL_LIBRARY.tests.test_skill_curriculum -v
```

Expected: FAIL with import/module-not-found for `compile_skill_curriculum`.

- [ ] **Step 3: Implement deterministic compiler**

Use this public interface:

```python
from pathlib import Path
from typing import Any

def compile_curriculum(root: Path) -> dict[str, Any]:
    """Compile canonical skill manifests into non-authoritative curriculum rows."""
```

Required row mapping:

```python
row = {
    "skill_id": skill_id,
    "domain": manifest["domain"],
    "roles": sorted(_roles_for_skill(skill_id, manifest, role_branches)),
    "triggers": sorted(_triggers_for_skill(skill_id, root)),
    "capabilities": sorted(_capabilities_for_skill(skill_id, manifest, root)),
    "permissions": sorted(set(manifest.get("permissions", []))),
    "risk_class": _risk_class(manifest),
    "output_contract": _output_contract(skill_id, root),
    "evals": sorted(set(manifest.get("evals", []))),
    "verifier_required": True,
    "promotion_class": _promotion_class_from_risk(manifest),
    "authority": False,
    "stable_write_allowed": False,
}
```

Rules:
- missing optional metadata becomes an empty list or the manifest-level contract; never invent permissions.
- role mapping may be empty; empty role mapping means curriculum exists but is not role-specialized yet.
- sort domains and skill IDs for deterministic output.
- never read model selection as an authority decision here.

- [ ] **Step 4: Add CLI**

CLI:

```bash
python -m AI_SKILL_LIBRARY.v4.tools.compile_skill_curriculum   --root .   --output AI_SKILL_LIBRARY/v4/learning/skill_curriculum.yaml
```

The CLI must print:

```text
SKILL_CURRICULUM_COMPILE=PASS skills=<N>
```

- [ ] **Step 5: Compile the canonical curriculum**

Run the CLI above and inspect the diff. Verify the number of unique `skill_id` values equals the union of canonical manifest skill lists.

- [ ] **Step 6: Extend skill factory policy**

Add:

```yaml
continuous_skill_learning:
  curriculum_gap_is_candidate_input_only: true
  competency_gap_is_candidate_input_only: true
  strengthen_existing_skill_first: true
  stable_catalog_mutation: promotion_pipeline_only
```

- [ ] **Step 7: Run focused tests**

```bash
python -m unittest   AI_SKILL_LIBRARY.tests.test_skill_curriculum   AI_SKILL_LIBRARY.tests.test_skill_forge -v
```

Expected: PASS.

- [ ] **Step 8: Commit**

```bash
git add AI_SKILL_LIBRARY/v4/tools/compile_skill_curriculum.py AI_SKILL_LIBRARY/v4/learning/skill_curriculum.yaml AI_SKILL_LIBRARY/v4/learning/skill_factory.yaml AI_SKILL_LIBRARY/tests/test_skill_curriculum.py
git commit -m "feat(learning): compile canonical skill curricula"
```

---

### Task 3: Add Sanitized Experience Intake

**Files:**
- Create: `AI_SKILL_LIBRARY/v4/tools/intake_experience.py`
- Modify: `AI_SKILL_LIBRARY/v4/learning/experience_ledger.json`
- Test: `AI_SKILL_LIBRARY/tests/test_experience_learning.py`
- Reference: `AI_SKILL_LIBRARY/v4/tools/intake_failure.py`

**Interfaces:**
- Consumes:
  - `normalize_experience(row: dict) -> dict`
  - `merge_experiences(ledger: dict, rows: list[dict]) -> dict`
- Produces:
  - deterministic ledger sorted by `experience_id`
  - `authority: false`
  - `stable_write: false`
  - no hidden/private/raw prompt fields.

- [ ] **Step 1: Write failing privacy and determinism tests**

```python
from AI_SKILL_LIBRARY.v4.tools.intake_experience import normalize_experience, merge_experiences


class ExperienceLearningTests(unittest.TestCase):
    BASE = {
        "experience_id": "exp-1",
        "timestamp": "2026-09-18T00:00:00Z",
        "request_class": "coding",
        "role_id": "CODING_BRANCH",
        "skill_ids": ["debugging"],
        "model_id": "Qwen/Qwen3-8B-GGUF",
        "latency_ms": 1200,
        "success": True,
        "verifier_passed": True,
        "retry_count": 0,
        "evidence_ref": "artifact://run/exp-1"
    }

    def test_private_fields_are_rejected(self):
        for forbidden in ("raw_prompt", "raw_private_chat", "hidden_reasoning", "chain_of_thought", "secret", "credentials"):
            row = dict(self.BASE)
            row[forbidden] = "forbidden"
            with self.assertRaises(ValueError):
                normalize_experience(row)

    def test_duplicate_id_must_be_identical(self):
        row = normalize_experience(self.BASE)
        merged = merge_experiences({"version": 1, "authority": False, "stable_write": False, "experiences": []}, [row, row])
        self.assertEqual(len(merged["experiences"]), 1)
        conflict = dict(row)
        conflict["success"] = False
        with self.assertRaises(ValueError):
            merge_experiences(merged, [conflict])
```

- [ ] **Step 2: Run test and verify failure**

```bash
python -m unittest AI_SKILL_LIBRARY.tests.test_experience_learning -v
```

Expected: FAIL because `intake_experience.py` does not exist.

- [ ] **Step 3: Implement sanitizer using failure-ledger pattern**

Use constants:

```python
_ALLOWED = {
    "experience_id", "timestamp", "request_class", "role_id", "skill_ids",
    "model_id", "provider_id", "worker_id", "latency_ms", "success",
    "failure_class", "verifier_passed", "retry_count", "escalation_path",
    "fallback_path", "resource_observation", "quota_impact",
    "user_feedback_signal", "evidence_ref"
}
_FORBIDDEN = {
    "raw_prompt", "raw_private_chat", "secret", "secrets", "credentials",
    "api_key", "private_key", "authentication_token", "hidden_reasoning",
    "chain_of_thought", "private_tool_payload", "raw_private_tool_payload"
}
_REQUIRED = {
    "experience_id", "timestamp", "request_class", "role_id", "skill_ids",
    "model_id", "success", "verifier_passed", "retry_count", "evidence_ref"
}
```

Reject unknown fields. Validate `skill_ids` as a non-empty unique string list. Cap free-text strings at 500 chars except `evidence_ref` at 500 and `failure_class` at 80.

- [ ] **Step 4: Add CLI**

```bash
python -m AI_SKILL_LIBRARY.v4.tools.intake_experience   --input /tmp/experience.json   --ledger AI_SKILL_LIBRARY/v4/learning/experience_ledger.json   --root .
```

Output:

```text
EXPERIENCE_INTAKE=PASS experiences=<N>
```

- [ ] **Step 5: Run focused privacy regression**

```bash
python -m unittest   AI_SKILL_LIBRARY.tests.test_experience_learning   AI_SKILL_LIBRARY.tests.test_failure_driven_learning -v
```

Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add AI_SKILL_LIBRARY/v4/tools/intake_experience.py AI_SKILL_LIBRARY/v4/learning/experience_ledger.json AI_SKILL_LIBRARY/tests/test_experience_learning.py
git commit -m "feat(learning): add sanitized experience intake"
```

---

### Task 4: Build Evidence-Backed Skill Competency Matrix

**Files:**
- Create: `AI_SKILL_LIBRARY/v4/tools/build_skill_competency.py`
- Modify: `AI_SKILL_LIBRARY/v4/learning/skill_competency_matrix.json`
- Test: `AI_SKILL_LIBRARY/tests/test_skill_competency.py`
- Reference: `AI_SKILL_LIBRARY/v4/model_mesh/capability_evidence.json`
- Reference: `AI_SKILL_LIBRARY/v4/model_mesh/role_branches.yaml`

**Interfaces:**
- Consumes:
  - `build_competency_matrix(curriculum: dict, capability_evidence: dict, experience_ledger: dict, role_branches: dict) -> dict`
- Produces:
  - deterministic rows keyed logically by `(model_id, skill_id, role_id)`
  - states never above `ELIGIBLE` without measured evidence
  - `PRIMARY` / `FALLBACK` only when backed by measured score plus verifier evidence.

- [ ] **Step 1: Write failing evidence-gating tests**

```python
from AI_SKILL_LIBRARY.v4.tools.build_skill_competency import build_competency_matrix


class SkillCompetencyTests(unittest.TestCase):
    def test_unmeasured_model_cannot_be_proficient_or_primary(self):
        curriculum = {"curricula": [{
            "skill_id": "reasoning",
            "roles": ["REASONING_BRANCH"],
            "capabilities": ["text_reasoning"],
            "authority": False
        }]}
        evidence = {"records": []}
        out = build_competency_matrix(curriculum, evidence, {"experiences": []}, {"branches": []})
        self.assertTrue(all(row["state"] in {"NOT_TESTED", "ELIGIBLE"} for row in out["rows"]))

    def test_measured_capability_can_reach_measured_state(self):
        curriculum = {"curricula": [{
            "skill_id": "reasoning",
            "roles": ["REASONING_BRANCH"],
            "capabilities": ["text_reasoning"],
            "authority": False
        }]}
        evidence = {"records": [{
            "evidence_id": "e-1",
            "model_id": "m1",
            "capability": "text_reasoning",
            "score": 0.9,
            "passed": True,
            "provenance": {"reference": "artifact://e-1"}
        }]}
        out = build_competency_matrix(curriculum, evidence, {"experiences": []}, {"branches": []})
        row = out["rows"][0]
        self.assertEqual(row["state"], "MEASURED")
        self.assertEqual(row["evidence_refs"], ["artifact://e-1"])
```

- [ ] **Step 2: Run and verify failure**

```bash
python -m unittest AI_SKILL_LIBRARY.tests.test_skill_competency -v
```

Expected: FAIL with missing module.

- [ ] **Step 3: Implement conservative state transitions**

Use:

```python
def _state(*, measured: bool, verifier_pass_rate: float | None, protected_ok: bool) -> str:
    if not measured:
        return "ELIGIBLE"
    if not protected_ok:
        return "QUARANTINED"
    if verifier_pass_rate is None:
        return "MEASURED"
    if verifier_pass_rate >= 0.95:
        return "PROFICIENT"
    return "MEASURED"
```

Do **not** assign `PRIMARY` or `FALLBACK` inside the basic evidence builder. Those labels belong to a later candidate/preference proposal step because Model Mesh owns selection.

Aggregate experience only when:
- same `model_id`
- same `role_id`
- row contains target `skill_id`
- `evidence_ref` exists.

Calculate verifier pass rate as:

```python
passes = sum(1 for x in rows if x["verifier_passed"] is True)
verifier_pass_rate = passes / len(rows) if rows else None
```

- [ ] **Step 4: Add CLI to rebuild matrix**

```bash
python -m AI_SKILL_LIBRARY.v4.tools.build_skill_competency   --root .   --output AI_SKILL_LIBRARY/v4/learning/skill_competency_matrix.json
```

Output:

```text
SKILL_COMPETENCY_BUILD=PASS rows=<N>
```

- [ ] **Step 5: Rebuild against current canonical evidence**

Inspect rows manually:
- every `PROFICIENT` row has non-empty `evidence_refs`
- no unmeasured model is `PROFICIENT`
- no `PRIMARY` / `FALLBACK` state is emitted yet.

- [ ] **Step 6: Run tests**

```bash
python -m unittest   AI_SKILL_LIBRARY.tests.test_skill_competency   AI_SKILL_LIBRARY.tests.test_model_mesh_evidence_precedence -v
```

Expected: PASS.

- [ ] **Step 7: Commit**

```bash
git add AI_SKILL_LIBRARY/v4/tools/build_skill_competency.py AI_SKILL_LIBRARY/v4/learning/skill_competency_matrix.json AI_SKILL_LIBRARY/tests/test_skill_competency.py
git commit -m "feat(learning): build measured skill competency matrix"
```

---

### Task 5: Run Bounded Learning Cycles Through Existing Promotion Gates

**Files:**
- Create: `AI_SKILL_LIBRARY/v4/tools/run_learning_cycle.py`
- Modify: `AI_SKILL_LIBRARY/v4/learning/skill_evo.yaml`
- Modify: `AI_SKILL_LIBRARY/v4/tools/skill_forge.py`
- Modify: `AI_SKILL_LIBRARY/v4/tools/evaluate_skill_candidate.py`
- Modify: `AI_SKILL_LIBRARY/v4/learning/promotion_evidence.json`
- Test: `AI_SKILL_LIBRARY/tests/test_learning_cycle.py`
- Reference: `AI_SKILL_LIBRARY/v4/control_plane/self_development.py`

**Interfaces:**
- Consumes:
  - `run_learning_cycle(cycle: dict, *, curriculum: dict, competency: dict, candidate: dict, eval_result: dict) -> dict`
  - existing `promotion_decision(candidate, eval_result) -> dict`
  - existing `evaluate_candidate(candidate, eval_result, replay_ref=...) -> dict`
- Produces:
  - immutable cycle result
  - promotion evidence record
  - no stable write.

- [ ] **Step 1: Write failing cycle-state tests**

```python
from AI_SKILL_LIBRARY.v4.tools.run_learning_cycle import run_learning_cycle


class LearningCycleTests(unittest.TestCase):
    def test_missing_frozen_replay_blocks_cycle(self):
        with self.assertRaises(ValueError):
            run_learning_cycle(
                {"cycle_id": "c1", "replay_ref": ""},
                curriculum={"curricula": []},
                competency={"rows": []},
                candidate={"candidate_id": "x", "promotion_class": "A", "permission_unchanged": True},
                eval_result={"all_gates_pass": True, "frozen_replay": False, "protected_regressions": 0, "critical_conflicts": 0, "measured_gain": 0.1},
            )

    def test_class_c_never_self_promotes(self):
        result = run_learning_cycle(
            {"cycle_id": "c2", "replay_ref": "artifact://replay/c2"},
            curriculum={"curricula": []},
            competency={"rows": []},
            candidate={"candidate_id": "x", "promotion_class": "C", "permission_unchanged": True, "sandbox_pass": True},
            eval_result={"all_gates_pass": True, "frozen_replay": True, "protected_regressions": 0, "critical_conflicts": 0, "measured_gain": 0.1},
        )
        self.assertEqual(result["state"], "HUMAN_GATE")
        self.assertFalse(result["stable_write"])
        self.assertFalse(result["routing_authority"])
```

- [ ] **Step 2: Run and verify failure**

```bash
python -m unittest AI_SKILL_LIBRARY.tests.test_learning_cycle -v
```

Expected: FAIL with missing module.

- [ ] **Step 3: Implement bounded orchestrator**

Required signature:

```python
def run_learning_cycle(
    cycle: dict,
    *,
    curriculum: dict,
    competency: dict,
    candidate: dict,
    eval_result: dict,
) -> dict:
```

Required behavior:
1. validate `cycle_id` and non-empty immutable `replay_ref`
2. require `eval_result["frozen_replay"] is True`
3. call existing `evaluate_candidate(...)`
4. map decision:
   - ineligible → `REJECTED`
   - eligible + explicit authorization → `HUMAN_GATE`
   - eligible + automatic → `PROMOTION_CANDIDATE`
5. always emit:
   - `stable_write: false`
   - `routing_authority: false`
   - `model_selection_authority: false`
   - `admission_authority: false`
   - `evidence_refs` containing replay and evaluation refs.

- [ ] **Step 4: Tighten skill_forge for competency gaps**

Extend `triage_gap` to accept optional fields:
- `source_kind` in `{"failure", "curriculum_gap", "competency_gap"}`
- `evidence_refs` non-empty list when `source_kind == "competency_gap"`

If a competency gap lacks evidence, return `action: "discard"`, reason `"competency_gap_missing_evidence"`.

Do not alter existing A/B/C/D semantics.

- [ ] **Step 5: Attach evidence refs to candidate evaluation**

Extend `evaluate_candidate` output with:

```python
"learning_evidence_refs": sorted(set(candidate.get("evidence_refs", []))),
"competency_ref": candidate.get("competency_ref"),
"curriculum_ref": candidate.get("curriculum_ref"),
```

Reject any non-string/empty evidence ref.

- [ ] **Step 6: Add learning policy wiring**

Append to `skill_evo.yaml`:

```yaml
continuous_skill_learning:
  cycle_runner: AI_SKILL_LIBRARY/v4/tools/run_learning_cycle.py
  competency_required_for_model_role_preference_change: true
  curriculum_required_for_skill_instruction_change: true
  user_feedback_alone_sufficient_for_promotion: false
  direct_model_mesh_write: false
  stable_write_allowed: false
```

- [ ] **Step 7: Run tests**

```bash
python -m unittest   AI_SKILL_LIBRARY.tests.test_learning_cycle   AI_SKILL_LIBRARY.tests.test_skill_forge   AI_SKILL_LIBRARY.tests.test_failure_driven_learning   AI_SKILL_LIBRARY.tests.test_local_runtime_selfdev_cycle -v
```

Expected: PASS.

- [ ] **Step 8: Commit**

```bash
git add AI_SKILL_LIBRARY/v4/tools/run_learning_cycle.py AI_SKILL_LIBRARY/v4/tools/skill_forge.py AI_SKILL_LIBRARY/v4/tools/evaluate_skill_candidate.py AI_SKILL_LIBRARY/v4/learning/skill_evo.yaml AI_SKILL_LIBRARY/v4/learning/promotion_evidence.json AI_SKILL_LIBRARY/tests/test_learning_cycle.py
git commit -m "feat(learning): add bounded evidence-gated learning cycles"
```

---

### Task 6: Integrate Competency Evidence with Phase 6 Without Stealing Model Selection

**Files:**
- Modify: `AI_SKILL_LIBRARY/v4/model_mesh/role_branches.yaml`
- Modify: `AI_SKILL_LIBRARY/v4/stable/continuous_intelligence.yaml`
- Modify: `AI_SKILL_LIBRARY/v4/learning/policy.yaml`
- Test: `AI_SKILL_LIBRARY/tests/test_skill_competency.py`
- Test: `AI_SKILL_LIBRARY/tests/test_authority_no_duplication_regression.py`
- Test: `AI_SKILL_LIBRARY/tests/test_federation_ops.py`

**Interfaces:**
- Consumes: competency matrix as evidence input only.
- Produces: policy declaration that Model Mesh may consider measured competency evidence; no direct role/model selection mutation.

- [ ] **Step 1: Add failing authority regression test**

Add:

```python
def test_learning_fabric_never_claims_model_selection_authority(self):
    policy = yaml.safe_load((ROOT / "AI_SKILL_LIBRARY/v4/learning/policy.yaml").read_text())
    fabric = policy["continuous_skill_learning"]
    self.assertIs(fabric["model_selection_authority"], False)
    self.assertIs(fabric["stable_write_allowed"], False)

    roles = yaml.safe_load((ROOT / "AI_SKILL_LIBRARY/v4/model_mesh/role_branches.yaml").read_text())
    evidence_input = roles["learning_evidence_input"]
    self.assertEqual(evidence_input["path"], "AI_SKILL_LIBRARY/v4/learning/skill_competency_matrix.json")
    self.assertIs(evidence_input["selection_authority"], False)
```

- [ ] **Step 2: Run focused test and verify failure**

```bash
python -m unittest AI_SKILL_LIBRARY.tests.test_authority_no_duplication_regression -v
```

Expected: FAIL because `learning_evidence_input` is not yet declared.

- [ ] **Step 3: Add non-authoritative evidence reference to role branches**

Add top-level:

```yaml
learning_evidence_input:
  path: AI_SKILL_LIBRARY/v4/learning/skill_competency_matrix.json
  purpose: measured_skill_role_competency_evidence_for_model_mesh
  selection_authority: false
  routing_authority: false
  admission_authority: false
  note: >-
    This matrix is evidence only. Model Mesh remains the sole selector and may
    ignore stale, missing, or policy-incompatible competency rows.
```

- [ ] **Step 4: Register bounded background learning**

In `continuous_intelligence.yaml`, add one job/policy block using the file's existing syntax with the semantics:

```yaml
continuous_skill_learning:
  enabled: true
  mode: bounded_event_or_schedule
  busy_loop: false
  direct_stable_write: false
  tasks:
    - aggregate_sanitized_experience
    - refresh_competency_measurements
    - replay_frozen_evals
    - propose_skill_candidates
    - refresh_promotion_evidence
```

Do not invent a new scheduler. Attach this to the existing continuous-intelligence schedule/event mechanism.

- [ ] **Step 5: Run regression suites**

```bash
python -m unittest   AI_SKILL_LIBRARY.tests.test_authority_no_duplication_regression   AI_SKILL_LIBRARY.tests.test_skill_competency   AI_SKILL_LIBRARY.tests.test_federation_ops -v
```

Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add AI_SKILL_LIBRARY/v4/model_mesh/role_branches.yaml AI_SKILL_LIBRARY/v4/stable/continuous_intelligence.yaml AI_SKILL_LIBRARY/v4/learning/policy.yaml AI_SKILL_LIBRARY/tests/test_authority_no_duplication_regression.py AI_SKILL_LIBRARY/tests/test_skill_competency.py
git commit -m "feat(phase6): feed measured skill competency into model mesh evidence"
```

---

### Task 7: Prove Learning Cannot Damage Stable Behavior

**Files:**
- Modify: `AI_SKILL_LIBRARY/tests/test_learning_cycle.py`
- Modify: `AI_SKILL_LIBRARY/tests/test_experience_learning.py`
- Modify: `AI_SKILL_LIBRARY/tests/test_skill_competency.py`
- Modify: `AI_SKILL_LIBRARY/tests/test_security_regression.py`
- Modify: existing CI validation registry/tool
- Create or update: canonical evidence file under `CHECKPOINTS/evidence/` using the repository's existing naming pattern.

**Interfaces:**
- Consumes: all previous tasks.
- Produces: release-gate proof that the Learning Fabric is safe, measured, and non-authoritative.

- [ ] **Step 1: Add protected-regression tests**

Add explicit tests:

```python
def test_user_feedback_alone_never_promotes():
    candidate = {
        "candidate_id": "feedback-only",
        "promotion_class": "A",
        "permission_unchanged": True,
        "evidence_refs": ["artifact://feedback/1"],
    }
    eval_result = {
        "all_gates_pass": False,
        "frozen_replay": True,
        "protected_regressions": 0,
        "critical_conflicts": 0,
        "measured_gain": 1.0,
        "source": "user_feedback_only",
    }
    out = evaluate_candidate(candidate, eval_result, replay_ref="artifact://replay/feedback")
    self.assertFalse(out["eligible"])


def test_rejected_cycle_cannot_change_stable_routing():
    before = (ROOT / "AI_SKILL_LIBRARY/v4/stable/router.yaml").read_bytes()
    # run a deliberately failing candidate through run_learning_cycle
    after = (ROOT / "AI_SKILL_LIBRARY/v4/stable/router.yaml").read_bytes()
    self.assertEqual(before, after)
```

Also assert:
- Class C/D remains human-gated.
- `execute_trade` remains forbidden in self-development.
- secret/raw prompt fields fail intake.
- competency matrix cannot confer permission.

- [ ] **Step 2: Run the complete learning subset**

```bash
python -m unittest   AI_SKILL_LIBRARY.tests.test_skill_curriculum   AI_SKILL_LIBRARY.tests.test_experience_learning   AI_SKILL_LIBRARY.tests.test_skill_competency   AI_SKILL_LIBRARY.tests.test_learning_cycle   AI_SKILL_LIBRARY.tests.test_skill_forge   AI_SKILL_LIBRARY.tests.test_failure_driven_learning   AI_SKILL_LIBRARY.tests.test_personal_ai_self_development   AI_SKILL_LIBRARY.tests.test_security_regression   AI_SKILL_LIBRARY.tests.test_authority_no_duplication_regression -v
```

Expected: PASS.

- [ ] **Step 3: Register tests in the existing CI_VALIDATE path**

Do not create a new workflow. Add the new test modules to the existing CI validation aggregator if they are not discovered automatically.

Run the exact repository validation command already used by PR #442. Expected final line:

```text
CI_VALIDATE=PASS
```

- [ ] **Step 4: Run AI Core release gate**

Use the existing release-gate command, not a new script. Expected:

```text
AI_CORE_RELEASE_GATE=PASS
```

If the release gate uses structured JSON rather than the exact text above, assert its canonical pass field and record that artifact.

- [ ] **Step 5: Write evidence file**

Record at minimum:

```json
{
  "continuous_skill_learning_fabric": "PROVEN",
  "routing_authority": false,
  "model_selection_authority": false,
  "admission_authority": false,
  "stable_write": false,
  "weight_fine_tuning_required": false,
  "curriculum_compiled": true,
  "experience_intake_sanitized": true,
  "competency_matrix_evidence_backed": true,
  "bounded_learning_cycle_proven": true,
  "protected_regression_gate_proven": true,
  "class_c_d_human_gate_proven": true,
  "trading_authority": false,
  "ci_validate": "PASS",
  "ai_core_release_gate": "PASS"
}
```

Include exact HEAD SHA and concrete test/evidence references using the repository's existing evidence conventions.

- [ ] **Step 6: Commit**

```bash
git add AI_SKILL_LIBRARY/tests AI_SKILL_LIBRARY/v4 CHECKPOINTS/evidence
git commit -m "test(learning): prove continuous skill learning fabric end to end"
```

---

### Task 8: Final Reconciliation and Handoff

**Files:**
- Modify: canonical checkpoint used by PR #442
- Modify: Phase 6 handoff/checkpoint file if one already exists
- Do not create a duplicate checkpoint.

**Interfaces:**
- Consumes: all implementation/evidence from Tasks 1–7.
- Produces: one concise canonical state for future Claude/ChatGPT sessions.

- [ ] **Step 1: Rebuild final curriculum and competency matrix**

Run:

```bash
python -m AI_SKILL_LIBRARY.v4.tools.compile_skill_curriculum   --root .   --output AI_SKILL_LIBRARY/v4/learning/skill_curriculum.yaml

python -m AI_SKILL_LIBRARY.v4.tools.build_skill_competency   --root .   --output AI_SKILL_LIBRARY/v4/learning/skill_competency_matrix.json
```

Expected: both PASS.

- [ ] **Step 2: Re-run the whole AI Skill Library suite**

Use the repo's canonical full-suite command. If direct unittest discovery is canonical, run:

```bash
python -m unittest discover AI_SKILL_LIBRARY/tests -v
```

Otherwise use the exact current CI command from PR #442.

Expected: zero failures.

- [ ] **Step 3: Re-run CI_VALIDATE and release gate**

Expected:
- `CI_VALIDATE=PASS`
- `AI_CORE_RELEASE_GATE=PASS`

- [ ] **Step 4: Update canonical checkpoint**

Checkpoint must record:

```text
CONTINUOUS_SKILL_LEARNING_FABRIC=PROVEN
CURRICULUM_READY=true
SANITIZED_EXPERIENCE_LEARNING=true
SKILL_COMPETENCY_MATRIX_READY=true
BOUNDED_LEARNING_CYCLES=true
PROTECTED_REGRESSION_GATE=true
MODEL_SELECTION_AUTHORITY=model_mesh
ROUTING_AUTHORITY=task_router
STABLE_DIRECT_WRITE=false
WEIGHT_FINE_TUNING_REQUIRED=false
TRADING_AUTHORITY=false
HUMAN_GATE_FOR_CLASS_C_D=true
```

Also include exact HEAD SHA, release-gate result, and remaining human-only gaps.

- [ ] **Step 5: Commit checkpoint**

```bash
git add AI_SKILL_LIBRARY/checkpoint.json CHECKPOINTS
git commit -m "docs(ai-core): checkpoint continuous skill learning fabric"
```

- [ ] **Step 6: Stop before merge**

Report:
- exact HEAD
- tests
- CI_VALIDATE
- AI Core release gate
- evidence paths
- human-only blockers
- `MERGE_READY`

Do not merge PR #442 automatically.
