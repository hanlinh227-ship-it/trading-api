# Brain 4.6 Open Source Fusion Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Strengthen the existing 109 canonical Brain skills using verified open-source patterns while preserving one reasoning-authority chain, zero-local operation, FAST latency, plain-language output, and current trading permission ceilings.

**Architecture:** Keep all upstream repositories as evidence/reference inputs, never runtime reasoning authorities. Add one evaluated quarantine record for Brain 4.6, extend the native capability-fusion and harmonization policies, strengthen existing skill contracts/evals, register only license-verified sources, and release through the existing immutable V4 toolchain.

**Tech Stack:** YAML, Python 3.12 unittest/validators, GitHub Actions, Node 22 Skill Gateway, Cloudflare Workers.

**Spec:** `docs/superpowers/specs/2026-09-13-brain-4-6-open-source-fusion-design.md`

## Global Constraints

- Canonical routed skill count remains exactly `109` unless a separately documented distinct-capability exception passes every gate; this plan creates no new canonical skill.
- Every routable skill keeps a validated execution capsule.
- Upstream/provider output remains evidence/reference only and has no routing or reasoning authority.
- Trading remains read-only under the Brain manifest; no order placement, leverage mutation, wallet signing, transfer, credential, destructive, or account-write permission is added.
- FAST keeps exactly one primary skill, zero supporting skills, zero external routing calls, no synchronous upstream refresh, and no new mandatory semantic-retrieval or checker loop.
- Zero-local remains mandatory for normal use.
- Plain-language presentation from release 4.5.0 remains active.
- Generated release manifests, hashes, history, snapshots, and retrieval index are produced only by canonical repository tools.
- Release rollback target remains `4.5.0` until `4.6.0` is production verified.

---

### Task 1: Add RED contracts for Brain 4.6 invariants

**Files:**
- Create: `AI_SKILL_LIBRARY/tests/test_brain_4_6_open_source_fusion.py`

**Interfaces:**
- Consumes: catalog, Skill Gateway compiler, harmonization policy, capability-fusion policy, source registry, eval policy, domain manifests.
- Produces: regression contract proving selective fusion without skill-count growth or authority/permission widening.

- [ ] **Step 1: Write failing test file**

Use this structure:

```python
import unittest
from pathlib import Path
import yaml
from AI_SKILL_LIBRARY.v4.tools.compile_skill_gateway import compile_snapshot

ROOT = Path(__file__).resolve().parents[2]
SHA = "d" * 40

def load_yaml(rel):
    return yaml.safe_load((ROOT / rel).read_text(encoding="utf-8"))

class Brain46OpenSourceFusionTests(unittest.TestCase):
    def test_skill_count_and_capsules_stay_109(self):
        snapshot = compile_snapshot(ROOT, SHA, generated_at="2026-09-13T00:00:00Z")
        self.assertEqual(len(snapshot["skills"]), 109)
        self.assertEqual(len(snapshot["capsules"]), 109)

    def test_brain_46_candidates_have_zero_authority_and_no_permission_expansion(self):
        record = load_yaml("AI_SKILL_LIBRARY/v4/evergreen/quarantine/brain_4_6_open_source_fusion.yaml")
        self.assertFalse(record["routing_authority"])
        self.assertFalse(record["reasoning_authority"])
        self.assertFalse(record["permission_expansion"])
        self.assertFalse(record["mandatory_runtime_dependency"])
        for row in record["candidates"]:
            self.assertEqual(row["decision"], "reference_only")
            self.assertFalse(row["code_reuse"])
            self.assertFalse(row["permission_expansion"])

    def test_fast_and_trading_contracts_remain_closed(self):
        harmonization = load_yaml("AI_SKILL_LIBRARY/v4/stable/harmonization.yaml")
        trading = load_yaml("AI_SKILL_LIBRARY/v4/skills/trading/manifest.yaml")
        self.assertEqual(harmonization["cognitive_execution"]["FAST"]["max_revisions"], 0)
        self.assertFalse(harmonization["cognitive_execution"]["FAST"]["maker_checker"])
        self.assertEqual(trading["permissions"], ["read_only"])
        self.assertTrue(trading["project_authority_required"])
        self.assertFalse(trading["research_may_grant_execution"])

    def test_fusion_map_contains_vetted_46_sources_as_reference_only(self):
        fusion = load_yaml("AI_SKILL_LIBRARY/v4/stable/capability_fusion.yaml")
        required = {
            "google/adk-python", "openai/openai-agents-python", "NVIDIA/garak",
            "langchain-ai/open-swe", "nautechsystems/nautilus_trader",
            "KhronosGroup/glTF-Validator", "mikedh/trimesh", "isl-org/Open3D",
            "stanfordnlp/dspy", "figma/code-connect",
        }
        self.assertTrue(required.issubset(fusion["upstream_pattern_map"]))
        for repo in required:
            row = fusion["upstream_pattern_map"][repo]
            self.assertFalse(row.get("routing_authority", False))
            self.assertFalse(row.get("mandatory_runtime_dependency", False))

if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Commit only the RED test**

Commit message: `test(brain): add Brain 4.6 fusion contracts`.

- [ ] **Step 3: Run branch CI and verify RED**

Expected failure reasons must be missing Brain 4.6 quarantine/reference/eval data, not syntax errors or unrelated regressions.

---

### Task 2: Verify and quarantine the upstream candidate set

**Files:**
- Create: `AI_SKILL_LIBRARY/v4/evergreen/quarantine/brain_4_6_open_source_fusion.yaml`
- Modify: `AI_SKILL_LIBRARY/sources.yaml`

**Interfaces:**
- Consumes: current public repository identity/license metadata and the source-registry schema.
- Produces: provenance-aware reference-only candidate records with training disabled and no code reuse.

- [ ] **Step 1: Verify repository identity, archive state, and SPDX-compatible license before registration**

Only add candidates whose current identity/license is verified. If a source has unresolved mixed/custom licensing, keep it out of active RAG and record it as manual/design reference only instead of weakening the validator.

- [ ] **Step 2: Create quarantine record**

Record at minimum: `repository`, `license`, `provenance`, `domains`, `decision: reference_only`, absorbed patterns, `code_reuse: false`, `permission_expansion: false`; trading candidate additionally records `financial_execution: false`.

- [ ] **Step 3: Register approved sources without exceeding registry limits**

Use existing categories only: `software`, `code`, `trading`, `ux_ui`, `prompt`, or `game`. Keep `training: false`; prefer `REFERENCE_ONLY` for conceptual sources and `RAG_ONLY` only where registry use is justified.

- [ ] **Step 4: Run `validate_registry.py` locally in CI including remote checks**

Expected: `0 error(s)`; canonical-name changes may be non-blocking warnings but should be fixed when unambiguous.

---

### Task 3: Extend native fusion and harmonization policies

**Files:**
- Modify: `AI_SKILL_LIBRARY/v4/stable/capability_fusion.yaml`
- Modify: `AI_SKILL_LIBRARY/v4/stable/harmonization.yaml`

**Interfaces:**
- Consumes: verified candidates from Task 2.
- Produces: native V4 absorption map and stricter future-upgrade gates.

- [ ] **Step 1: Add reference mappings for agent engineering/eval**

Absorb bounded handoffs, tracing/eval metadata, typed tool contracts, adversarial prompt/capability tests, and explicit state transitions into existing planning/automation/skill/eval/security capabilities.

- [ ] **Step 2: Add software-engineering mappings**

Absorb issue -> inspect -> plan -> isolated change -> test -> review -> PR patterns and bounded large-repository context handling; existing Superpowers/TDD workflow remains implementation authority.

- [ ] **Step 3: Add quant/3D/UX/prompt mappings**

Encode event-driven backtest realism, execution assumptions, design-token/accessibility/component mapping, glTF/geometry/export validation, and measured prompt-regression patterns as native references only.

- [ ] **Step 4: Tighten harmonization intake**

Require maintenance status, permission ceiling, performance impact, authority impact, license/provenance evidence, and an explicit `strengthen_existing_skill_first` decision before any new-skill proposal.

- [ ] **Step 5: Keep all new upstream rows non-authoritative**

Every new row must have `routing_authority: false`, `mandatory_runtime_dependency: false`, and `code_reuse: false` unless separately approved in a future spec.

---

### Task 4: Strengthen existing skill contracts without adding skills

**Files:**
- Modify: `AI_SKILL_LIBRARY/skills/catalog.yaml`
- Modify: `AI_SKILL_LIBRARY/v4/skills/core/manifest.yaml`
- Modify: `AI_SKILL_LIBRARY/v4/skills/engineering/manifest.yaml`
- Modify: `AI_SKILL_LIBRARY/v4/skills/trading/manifest.yaml`
- Modify: `AI_SKILL_LIBRARY/v4/skills/design_2d/manifest.yaml`
- Modify: `AI_SKILL_LIBRARY/v4/skills/design_3d/manifest.yaml`
- Modify: `AI_SKILL_LIBRARY/v4/skills/prompt_media/manifest.yaml`
- Modify: `AI_SKILL_LIBRARY/v4/skills/game/manifest.yaml` only when adding eval labels, never permissions.

**Interfaces:**
- Consumes: native patterns from Task 3.
- Produces: stronger output contracts/eval requirements for existing canonical skill IDs only.

- [ ] **Step 1: Engineering/core strengthening**

Strengthen planning/verification/troubleshooting/coding/debugging/TDD/GitHub/automation/skill/eval contracts to require explicit verification checkpoints, bounded context, reproducibility, and review-feedback handling where material.

- [ ] **Step 2: Trading strengthening**

Strengthen quant/backtest/validation/microstructure/risk/bot contracts to require fees, slippage, fill/latency assumptions, data split semantics, reproducibility, regime stability, and research/live semantic separation. Keep manifest `permissions: [read_only]` and existing execution-authority fields unchanged.

- [ ] **Step 3: UX/3D/prompt strengthening**

Add accessibility/token/component consistency; glTF/geometry/transforms/normals/manifold/material/UV/animation/export-reimport checks; and measurable prompt objective/constraint/regression checks without claiming deterministic generation.

- [ ] **Step 4: Verify no new canonical IDs or trigger ownership conflicts**

Compiled snapshot must still report exactly 109 skills and 109 capsules.

---

### Task 5: Expand evaluation coverage and bottleneck checks

**Files:**
- Modify: `AI_SKILL_LIBRARY/evals.yaml`
- Modify: `AI_SKILL_LIBRARY/tests/test_brain_4_6_open_source_fusion.py`

**Interfaces:**
- Consumes: strengthened contracts from Task 4.
- Produces: measurable gates for repo workflow, quant realism, 3D, UX, prompt regression, adversarial resistance, source/license enforcement, and latency/context cost.

- [ ] **Step 1: Add benchmark classes/cases**

Add explicit evaluation groups for `repository_workflow`, `quant_realism`, `asset_validation_3d`, `design_system_validation`, `prompt_regression`, `source_license_provenance`, and `duplicate_capability_detection` while retaining current scoring weights/protected dimensions unless a test demonstrates a required change.

- [ ] **Step 2: Add protected-regression assertions**

Tests must require zero material regression for correctness, verification, safety, authority, plain-language presentation, and project isolation.

- [ ] **Step 3: Add performance guard assertions**

Keep FAST max revisions/checker behavior unchanged; final Worker benchmark must report `FAST_EXTERNAL_CALLS=0` and p50/p95.

---

### Task 6: Run GREEN regression and generate release 4.6.0

**Files:**
- Generated by canonical tools: `AI_SKILL_LIBRARY/v4/releases/4.6.0/manifest.yaml`
- Generated by canonical tools: `AI_SKILL_LIBRARY/v4/releases/current.json`
- Generated by canonical tools: `AI_SKILL_LIBRARY/v4/releases/history.yaml`
- Generated by canonical tools: `AI_SKILL_LIBRARY/v4/index/retrieval_index.yaml`
- Generated Skill Gateway snapshot as required by CI/deploy.

**Interfaces:**
- Consumes: final stable policies/contracts/tests.
- Produces: immutable 4.6.0 candidate with 4.5.0 rollback.

- [ ] **Step 1: Run focused tests to GREEN**

Expected: Brain 4.6 test passes, plain-language tests remain green, trading authority stays read-only, snapshot contains 109 skills/109 capsules.

- [ ] **Step 2: Run the single validation entrypoint**

Run `python AI_SKILL_LIBRARY/v4/tools/ci_validate.py --source-sha <branch-head-sha>` in GitHub Actions. Require zero failures.

- [ ] **Step 3: Generate release/index with repository tools only**

Run canonical `release.py build --version 4.6.0 --source brain_4_6_open_source_fusion --validated --known-good` only after the pre-release canary is green, then regenerate the retrieval index with its canonical builder. Never hand-edit hashes or generated index rows.

- [ ] **Step 4: Re-run full exact-tree CI**

Require release check, retrieval freshness, all Python tests, repository tests, Skill Gateway compile/snapshot validation, Worker tests, zero-local checks, benchmark, and Cloudflare dry-run to pass.

---

### Task 7: Review, merge, deploy, and production-verify

**Files:**
- No additional implementation files unless a verified regression requires a scoped fix.

**Interfaces:**
- Consumes: exact green branch head.
- Produces: production-verified Brain 4.6.0.

- [ ] **Step 1: Review final diff**

Confirm no temporary workflow remains, no canonical skill ID was renamed, no duplicate reasoning authority exists, no trading/live execution permission widened, no local dependency became mandatory, and all source licenses/provenance are represented.

- [ ] **Step 2: Open PR and require canonical CI**

PR summary must state skill count remains 109 and external repositories are reference-only.

- [ ] **Step 3: Merge with expected head SHA only after green CI**

Use repository-approved merge method; reject merge if head moved unexpectedly.

- [ ] **Step 4: Verify automatic exact-main Cloudflare deployment**

Require `/runtime/contract` and `/brain/health` to expose the exact merged SHA, schema/primary-skill/capsule contract to pass, FAST external routing calls to remain zero, and production route smoke to pass representative core, engineering, design/prompt, and trading cases.

- [ ] **Step 5: Verify no runtime switch mutation**

Production deploy must preserve existing trading switches and live-research authority; Cloudflare Skill Gateway must not silently replace Railway live-price research authority.

- [ ] **Step 6: Mark complete only after production proof**

If any protected gate fails, keep/restore 4.5.0 and report the exact blocked gate rather than claiming completion.
