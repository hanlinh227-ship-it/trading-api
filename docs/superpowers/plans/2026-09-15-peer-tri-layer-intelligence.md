# Peer Tri-Layer Intelligence Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a branch-neutral A/B/C learning intelligence layer that normalizes claims and evidence, resolves material conflicts without majority voting, and emits validated evidence artifacts for AI Legion tasks and Evergreen promotion.

**Architecture:** Add a new `AI_SKILL_LIBRARY/v4/legion/` namespace that sits in WARM context only. Experience, Curated, and Exploration branches have identical candidate rights; branch identity contributes provenance only. Claim-specific evidence is normalized and scored, material conflicts are resolved or explicitly blocked, and runtime consumers receive an exact-SHA compiled snapshot rather than live Evergreen state.

**Tech Stack:** Python 3.12, PyYAML, jsonschema, unittest, existing GITHUB_BRAIN_V4 release/CI tooling.

**Spec:** `docs/superpowers/specs/2026-09-15-peer-tri-layer-ai-legion-design.md`

## Global Constraints

- `GITHUB_BRAIN_V4` remains the only routing/reasoning authority.
- Learning branch names are `experience`, `curated`, `exploration`; they MUST NOT be confused with promotion risk Classes A/B/C/D.
- No fixed branch score or source-layer preference is allowed.
- Truth is never selected by vote count or silent averaging.
- Current runtime/project authority and Stable security remain controlling authority where applicable.
- Hidden chain-of-thought, raw private prompts, credentials, secrets, private keys and unauthorized sensitive data never enter persisted evidence.
- FAST loads no Legion/learning state and performs no external learning call.
- STANDARD/DEEP preserve existing limits: max parallel 2/4, max graph nodes 4/10, max supporting skills 2.
- Learning cannot expand permission ceilings or mutate Stable in-flight.
- All behavior changes use RED -> minimum GREEN -> regression -> validators -> CI.

---

### Task 1: Define Peer Tri-Layer policy and typed claim/evidence schemas

**Files:**
- Create: `AI_SKILL_LIBRARY/v4/legion/policy.yaml`
- Create: `AI_SKILL_LIBRARY/v4/legion/learning.yaml`
- Create: `AI_SKILL_LIBRARY/v4/schemas/legion_claim.schema.json`
- Create: `AI_SKILL_LIBRARY/v4/schemas/legion_evidence.schema.json`
- Test: `AI_SKILL_LIBRARY/tests/test_peer_tri_layer_contracts.py`

**Interfaces:**
- Consumes: Stable `security.yaml`, `evidence.yaml`, `harmonization.yaml`, `budgets.yaml`.
- Produces: canonical branch identifiers and JSON schemas used by later tasks.

- [ ] **Step 1: Write the failing contract test**

```python
import json
import unittest
from pathlib import Path
import yaml

ROOT = Path(__file__).resolve().parents[1]

class PeerTriLayerContractTests(unittest.TestCase):
    def test_branches_are_peer_sources_not_authorities(self):
        data = yaml.safe_load((ROOT / "v4/legion/learning.yaml").read_text())
        self.assertEqual(set(data["branches"]), {"experience", "curated", "exploration"})
        self.assertTrue(data["peer_semantics"]["equal_candidate_rights"])
        self.assertFalse(data["peer_semantics"]["fixed_branch_precedence"])
        self.assertEqual(data["conflict_resolution"]["majority_vote"], "forbidden")
        self.assertEqual(data["conflict_resolution"]["silent_averaging"], "forbidden")

    def test_learning_layer_does_not_map_to_risk_class(self):
        data = yaml.safe_load((ROOT / "v4/legion/policy.yaml").read_text())
        self.assertFalse(data["policy"]["learning_layer_implies_risk_class"])
        self.assertFalse(data["policy"]["routing_authority"])
        self.assertFalse(data["policy"]["reasoning_authority"])
```

- [ ] **Step 2: Run RED**

Run:

```bash
python -m unittest AI_SKILL_LIBRARY.tests.test_peer_tri_layer_contracts -v
```

Expected: FAIL because `v4/legion/` and schemas do not exist.

- [ ] **Step 3: Implement the minimum policy contracts**

`learning.yaml` must include this minimum shape:

```yaml
version: 1
branches: [experience, curated, exploration]
peer_semantics:
  equal_candidate_rights: true
  fixed_branch_precedence: false
  branch_identity_is_provenance_only: true
  equal_rights: [hypothesis, challenge, experiment_request, skill_candidate, mutation, upstream_proposal]
conflict_resolution:
  majority_vote: forbidden
  silent_averaging: forbidden
  unresolved_material_conflict: block_dependent_promotion
```

`policy.yaml` must explicitly set `routing_authority: false`, `reasoning_authority: false`, `stable_request_dependency: false`, `permission_expansion_by_learning: false`, `learning_layer_implies_risk_class: false`, and `persist_hidden_reasoning: false`.

- [ ] **Step 4: Define exact schema fields**

`legion_claim.schema.json` requires:

```json
{
  "claim_id": "string",
  "branch": "experience|curated|exploration",
  "domain": "string",
  "claim_summary": "string",
  "source_id": "string",
  "source_revision": "string|null",
  "authority_type": "string",
  "observed_at": "date-time",
  "freshness_requirement": "string",
  "confidence": "number 0..1",
  "verification_state": "unverified|verified|rejected|unresolved",
  "contradicts": ["claim_id"]
}
```

`legion_evidence.schema.json` requires `evidence_id`, `claim_id`, `evidence_reference`, `source_class`, `freshness`, `reproducible`, `benchmark_refs`, `verification_status`, `domain`, `observed_at`.

- [ ] **Step 5: Run GREEN and commit**

```bash
python -m unittest AI_SKILL_LIBRARY.tests.test_peer_tri_layer_contracts -v
git add AI_SKILL_LIBRARY/v4/legion AI_SKILL_LIBRARY/v4/schemas/legion_*.schema.json AI_SKILL_LIBRARY/tests/test_peer_tri_layer_contracts.py
git commit -m "feat: define peer tri-layer intelligence contracts"
```

---

### Task 2: Implement claim normalization and evidence scoring without branch bias

**Files:**
- Create: `AI_SKILL_LIBRARY/v4/tools/peer_intelligence.py`
- Test: `AI_SKILL_LIBRARY/tests/test_peer_tri_layer_evidence.py`

**Interfaces:**
- Consumes: Task 1 schemas/policy.
- Produces:
  - `normalize_claim(raw: dict, *, branch: str, observed_at: str) -> dict`
  - `normalize_evidence(raw: dict, *, observed_at: str) -> dict`
  - `evidence_score(claim: dict, evidence: list[dict], policy: dict) -> float`

- [ ] **Step 1: Write RED tests for branch neutrality**

```python
from AI_SKILL_LIBRARY.v4.tools.peer_intelligence import evidence_score

same = [{
    "freshness": 1.0,
    "reproducible": True,
    "authority_fit": 0.8,
    "benchmark_strength": 0.7,
    "verification_status": "verified",
}]

def test_equal_evidence_equal_score_across_branches():
    scores = [evidence_score({"branch": b}, same, {}) for b in ("experience", "curated", "exploration")]
    assert scores[0] == scores[1] == scores[2]
```

Add tests rejecting unknown branches, confidence outside 0..1, future timestamps, forbidden sensitive keys, NaN scores, and missing provenance.

- [ ] **Step 2: Run RED**

```bash
python -m unittest AI_SKILL_LIBRARY.tests.test_peer_tri_layer_evidence -v
```

Expected: FAIL because `peer_intelligence.py` is absent.

- [ ] **Step 3: Implement normalization and a bounded scoring model**

Use only claim-specific signals:

```python
WEIGHTS = {
    "freshness": 0.20,
    "reproducibility": 0.25,
    "authority_fit": 0.20,
    "benchmark_strength": 0.20,
    "verification": 0.15,
}
```

Do not include `branch` as a weight. Clamp all components and final score to `[0.0, 1.0]`. Reject sensitive fields using the existing Evergreen forbidden-field semantics.

- [ ] **Step 4: Run GREEN plus neighboring regressions**

```bash
python -m unittest AI_SKILL_LIBRARY.tests.test_peer_tri_layer_evidence -v
python -m unittest AI_SKILL_LIBRARY.tests.test_brain_4_8_continuous_intelligence -v
```

- [ ] **Step 5: Commit**

```bash
git add AI_SKILL_LIBRARY/v4/tools/peer_intelligence.py AI_SKILL_LIBRARY/tests/test_peer_tri_layer_evidence.py
git commit -m "feat: add branch neutral evidence scoring"
```

---

### Task 3: Implement conflict sets, challenge rounds, and evidence-weighted resolution

**Files:**
- Modify: `AI_SKILL_LIBRARY/v4/tools/peer_intelligence.py`
- Create: `AI_SKILL_LIBRARY/tests/test_peer_tri_layer_conflicts.py`
- Modify: `AI_SKILL_LIBRARY/v4/evergreen/conflicts.yaml`

**Interfaces:**
- Produces:
  - `build_conflict_set(claims: list[dict]) -> list[dict]`
  - `resolve_claim_set(claims: list[dict], evidence: list[dict], *, material: bool) -> dict`
  - `build_challenge_round(objective: dict, contributions: list[dict]) -> dict`

- [ ] **Step 1: Write RED tests proving majority cannot decide truth**

```python
def test_one_reproducible_exploration_claim_can_beat_two_weak_claims():
    result = resolve_claim_set(
        claims=[A_WEAK, B_WEAK, C_STRONG],
        evidence=EVIDENCE,
        material=True,
    )
    assert result["accepted_claim_id"] == C_STRONG["claim_id"]
    assert result["decision_basis"] != "vote_count"
```

Also test that tied material conflicts return `status="unresolved"`, and security/permission conflicts fail closed.

- [ ] **Step 2: Run RED**

```bash
python -m unittest AI_SKILL_LIBRARY.tests.test_peer_tri_layer_conflicts -v
```

- [ ] **Step 3: Implement deterministic resolution**

Resolution order:

```text
normalize -> provenance -> freshness -> claim-specific authority -> reproducibility -> benchmark/regression -> contradiction check -> checker metadata -> accept/unresolved/reject
```

Do not call an LLM inside the deterministic resolver. External checker/grader results enter only as verified evidence rows.

- [ ] **Step 4: Update Evergreen conflict policy**

Add explicit invariants: peer branch neutrality, no vote count, unresolved material conflict blocks promotion, and permission/security conflict fails closed.

- [ ] **Step 5: Run GREEN and commit**

```bash
python -m unittest AI_SKILL_LIBRARY.tests.test_peer_tri_layer_conflicts -v
git add AI_SKILL_LIBRARY/v4/tools/peer_intelligence.py AI_SKILL_LIBRARY/v4/evergreen/conflicts.yaml AI_SKILL_LIBRARY/tests/test_peer_tri_layer_conflicts.py
git commit -m "feat: resolve peer learning conflicts by evidence"
```

---

### Task 4: Compile an immutable Peer Intelligence snapshot for Stable consumers

**Files:**
- Create: `AI_SKILL_LIBRARY/v4/schemas/legion_intelligence_snapshot.schema.json`
- Create: `AI_SKILL_LIBRARY/v4/tools/compile_legion_intelligence_snapshot.py`
- Create: `AI_SKILL_LIBRARY/v4/tools/validate_legion_intelligence_snapshot.py`
- Test: `AI_SKILL_LIBRARY/tests/test_peer_tri_layer_snapshot.py`

**Interfaces:**
- Produces:
  - `compile_snapshot(root: Path, *, source_sha: str, claims_path: Path, output: Path, generated_at: str) -> dict`
  - `validate_snapshot(root: Path, snapshot_path: Path, *, expected_source_sha: str) -> list[str]`

- [ ] **Step 1: Write RED tests**

Test deterministic sorting, exact `source_sha`, no secrets, no hidden reasoning, branch-neutral metadata, unresolved material conflicts excluded from accepted claims, and immutable input hashes.

- [ ] **Step 2: Run RED**

```bash
python -m unittest AI_SKILL_LIBRARY.tests.test_peer_tri_layer_snapshot -v
```

- [ ] **Step 3: Implement whitelist-only compilation**

Snapshot top-level fields must be:

```json
{
  "schema_version": 1,
  "source_sha": "40-char SHA",
  "generated_at": "ISO8601",
  "routing_authority": false,
  "reasoning_authority": false,
  "branches": ["experience", "curated", "exploration"],
  "accepted_claims": [],
  "unresolved_claim_ids": [],
  "evidence_index": []
}
```

Never copy arbitrary discovery fields.

- [ ] **Step 4: Run GREEN and commit**

```bash
python -m unittest AI_SKILL_LIBRARY.tests.test_peer_tri_layer_snapshot -v
git add AI_SKILL_LIBRARY/v4/schemas/legion_intelligence_snapshot.schema.json AI_SKILL_LIBRARY/v4/tools/compile_legion_intelligence_snapshot.py AI_SKILL_LIBRARY/v4/tools/validate_legion_intelligence_snapshot.py AI_SKILL_LIBRARY/tests/test_peer_tri_layer_snapshot.py
git commit -m "feat: compile validated peer intelligence snapshot"
```

---

### Task 5: Register the subsystem without touching FAST

**Files:**
- Modify: `AI_SKILL_LIBRARY/v4/stable/capability_fusion.yaml`
- Modify: `AI_SKILL_LIBRARY/v4/index/workspace_map.yaml`
- Modify: `AI_SKILL_LIBRARY/evals.yaml`
- Test: `AI_SKILL_LIBRARY/tests/test_peer_tri_layer_integration.py`

**Interfaces:**
- Consumes: Tasks 1-4.
- Produces: WARM-only discoverability and protected eval requirements.

- [ ] **Step 1: Write RED integration tests**

Assert `AI_SKILL_LIBRARY/v4/legion` appears in WARM but not HOT, FAST budgets remain unchanged, `provider_voting=forbidden`, and evals contain peer-branch-neutrality, conflict-resolution, prompt-injection and sensitive-data regression classes.

- [ ] **Step 2: Run RED**

```bash
python -m unittest AI_SKILL_LIBRARY.tests.test_peer_tri_layer_integration -v
```

- [ ] **Step 3: Register the namespace and evals**

Add capability-fusion metadata only; do not add a second router, primary skill, or mandatory external framework.

- [ ] **Step 4: Run all Task 1-5 tests plus canonical validators**

```bash
python -m unittest \
  AI_SKILL_LIBRARY.tests.test_peer_tri_layer_contracts \
  AI_SKILL_LIBRARY.tests.test_peer_tri_layer_evidence \
  AI_SKILL_LIBRARY.tests.test_peer_tri_layer_conflicts \
  AI_SKILL_LIBRARY.tests.test_peer_tri_layer_snapshot \
  AI_SKILL_LIBRARY.tests.test_peer_tri_layer_integration -v
python AI_SKILL_LIBRARY/v4/tools/ci_validate.py --source-sha "$(git rev-parse HEAD)" --skip-tests
```

- [ ] **Step 5: Commit**

```bash
git add AI_SKILL_LIBRARY/v4/stable/capability_fusion.yaml AI_SKILL_LIBRARY/v4/index/workspace_map.yaml AI_SKILL_LIBRARY/evals.yaml AI_SKILL_LIBRARY/tests/test_peer_tri_layer_integration.py
git commit -m "feat: register peer tri-layer intelligence"
```
