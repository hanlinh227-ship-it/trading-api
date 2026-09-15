# Animation-Safe Video Prompt Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Strengthen canonical `video_prompt` routing and execution guidance so generative-animation prompts preserve temporal state, contact, trajectory, screen direction, body mechanics, camera ownership, object permanence, and provider-appropriate wording without creating a duplicate primary skill.

**Architecture:** Keep `video_prompt` as the only generative-video primary skill. Encode the animation-safety behavior directly in its canonical catalog `output_contract` so the Skill Gateway capsule carries the rules at runtime, add exact non-conflicting specialist triggers for animation-prompt/I2V intent, and add prompt-media manifest quality gates plus a reference-only provenance record. Validate behavior with a focused configuration regression test and the repository's single CI entrypoint.

**Tech Stack:** Python 3.12 `unittest`, PyYAML, GitHub Skill Gateway YAML, GitHub Actions.

**Spec:** `docs/superpowers/specs/2026-09-15-animation-safe-video-prompt-design.md`

## Global Constraints

- Do not add a new primary skill.
- Do not take ownership of the generic `animation` trigger from the `design_3d` domain.
- Keep permissions read-only and preserve zero-local normal operation.
- External repositories/provider docs are evidence/reference only, never reasoning authority.
- Do not promise deterministic or error-free stochastic video generation.
- Use RED -> minimum GREEN -> full `ci_validate.py`/GitHub Actions verification.

---

### Task 1: Add the RED animation-safety contract regression

**Files:**
- Create: `tests/test_animation_prompt_safety.py`
- Read: `AI_SKILL_LIBRARY/skills/catalog.yaml`
- Read: `AI_SKILL_LIBRARY/v4/skills/prompt_media/manifest.yaml`

**Interfaces:**
- Consumes: canonical YAML catalog and prompt-media manifest.
- Produces: a regression test that defines the minimum animation-safety contract expected from `video_prompt`.

- [ ] **Step 1: Create the failing regression test**

```python
from __future__ import annotations

import unittest
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]
CATALOG = ROOT / "AI_SKILL_LIBRARY/skills/catalog.yaml"
MANIFEST = ROOT / "AI_SKILL_LIBRARY/v4/skills/prompt_media/manifest.yaml"


def load_yaml(path: Path) -> dict:
    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise AssertionError(f"expected mapping: {path}")
    return data


class AnimationPromptSafetyTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.catalog = load_yaml(CATALOG)
        cls.manifest = load_yaml(MANIFEST)
        cls.skills = {
            row["id"]: row
            for row in cls.catalog.get("skills", [])
            if isinstance(row, dict) and isinstance(row.get("id"), str)
        }

    def test_specific_animation_prompt_intents_route_to_video_prompt_without_stealing_generic_animation(self):
        video = self.skills["video_prompt"]
        animation = self.skills["animation"]
        self.assertTrue({"animation prompt", "image to video prompt", "i2v prompt"}.issubset(set(video.get("triggers", []))))
        self.assertEqual(animation.get("triggers"), ["animation"])
        self.assertNotIn("animation", video.get("triggers", []))

    def test_video_prompt_contract_contains_animation_safety_invariants(self):
        contract = self.skills["video_prompt"].get("output_contract", "").casefold()
        required = (
            "start/end state",
            "action owner",
            "contact",
            "trajectory",
            "screen direction",
            "camera ownership",
            "motion budget",
            "object permanence",
            "body mechanics",
            "image-to-video",
            "positive operational wording",
            "stochastic",
        )
        for phrase in required:
            self.assertIn(phrase, contract, phrase)

    def test_prompt_media_manifest_declares_animation_safety_quality_gates(self):
        quality = self.manifest.get("quality_requirements", {})
        required_true = (
            "animation_start_end_state_lock",
            "animation_action_owner_unambiguous",
            "animation_contact_continuity",
            "animation_trajectory_consistency",
            "animation_screen_direction_consistency",
            "animation_camera_ownership_explicit",
            "animation_motion_budget_checked",
            "animation_object_permanence",
            "animation_body_mechanics",
            "animation_provider_wording_adapted",
            "animation_i2v_reference_is_authority",
        )
        for key in required_true:
            self.assertIs(quality.get(key), True, key)


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Open a draft PR to run the existing pull-request CI and verify RED**

Expected: `AI Skill Library CI` fails specifically because the new test cannot find the new `video_prompt` triggers/contract/manifest requirements. Existing unrelated validators should remain baseline-green.

- [ ] **Step 3: Capture the failed workflow/job evidence**

Use the PR head SHA with `fetch_commit_workflow_runs`, then inspect the failed job steps/logs. The failure must be attributable to `tests/test_animation_prompt_safety.py`, not YAML syntax or unrelated repository breakage.

---

### Task 2: Implement the minimum canonical video-prompt upgrade

**Files:**
- Modify: `AI_SKILL_LIBRARY/skills/catalog.yaml`
- Modify: `AI_SKILL_LIBRARY/v4/skills/prompt_media/manifest.yaml`

**Interfaces:**
- Consumes: Task 1 regression expectations.
- Produces: `video_prompt` routing triggers and execution-capsule output contract; prompt-media domain quality gates.

- [ ] **Step 1: Extend only the `video_prompt` catalog row**

Add triggers exactly:

```yaml
triggers: [video prompt, video generation, animation prompt, image to video prompt, i2v prompt]
```

Replace its output contract with one that explicitly requires: reference/identity and count preservation; start/end state; action ownership; contact continuity; trajectory and screen direction; timing/body mechanics; camera ownership; object permanence; motion-budget simplification/splitting; image-to-video reference authority; provider-adapted positive operational wording where appropriate; measurable continuity checks; no stochastic-fidelity guarantee.

Do not modify the `animation` skill trigger.

- [ ] **Step 2: Add prompt-media animation quality gates**

Under `quality_requirements` in `AI_SKILL_LIBRARY/v4/skills/prompt_media/manifest.yaml`, add these booleans with value `true`:

```yaml
animation_start_end_state_lock: true
animation_action_owner_unambiguous: true
animation_contact_continuity: true
animation_trajectory_consistency: true
animation_screen_direction_consistency: true
animation_camera_ownership_explicit: true
animation_motion_budget_checked: true
animation_object_permanence: true
animation_body_mechanics: true
animation_provider_wording_adapted: true
animation_i2v_reference_is_authority: true
```

- [ ] **Step 3: Re-run the focused test**

Run through repository CI or locally:

```bash
python -m unittest tests.test_animation_prompt_safety -v
```

Expected: PASS for all animation prompt safety tests.

---

### Task 3: Register external animation/video sources as reference-only evidence

**Files:**
- Create: `AI_SKILL_LIBRARY/v4/evergreen/quarantine/animation_prompt_reference_fusion.yaml`

**Interfaces:**
- Consumes: official/public upstream research already reviewed for the design.
- Produces: provenance/license/authority metadata with zero routing authority and zero code-reuse/runtime dependency.

- [ ] **Step 1: Add a reference-only candidate record**

Record at minimum:

```yaml
version: 1
candidate_set: animation_prompt_reference_fusion
state: evaluated_reference_only
routing_authority: false
reasoning_authority: false
permission_expansion: false
mandatory_runtime_dependency: false
zero_local_preserved: true
promotion_target: strengthen_video_prompt_only
candidates:
  - repository: guoyww/AnimateDiff
    provenance: github_public_official_implementation
    license: Apache-2.0
    decision: reference_only
    absorbs: [motion_priors, motion_pattern_control, sparse_structural_control]
    code_reuse: false
  - repository: Lightricks/LTX-Video
    provenance: github_public_official_repository
    license: Apache-2.0
    decision: reference_only
    absorbs: [chronological_motion_prompting, literal_temporal_action_order]
    code_reuse: false
  - repository: Wan-Video/Wan2.2
    provenance: github_public_official_repository
    license: Apache-2.0
    decision: reference_only
    absorbs: [complex_video_motion_reference, image_to_video_reference]
    code_reuse: false
reference_guidance:
  provider_docs_are_evidence_only: true
  classical_animation_principles_are_reference_only: true
  no_external_framework_as_authority: true
conflict_resolution:
  canonical_skill_first: true
  generic_animation_trigger_stays_with_design_3d: true
  duplicate_reasoning_authority: reject
  permission_widening: reject
```

- [ ] **Step 2: Ensure the record does not enter routing or active provider registries**

No catalog skill row, provider capability, execution permission, or runtime dependency is added for these sources.

---

### Task 4: Verify compiled capsule, routing uniqueness, retrieval/release integrity, and full CI

**Files:**
- Verify: `AI_SKILL_LIBRARY/v4/tools/compile_skill_gateway.py`
- Verify: `AI_SKILL_LIBRARY/v4/index/retrieval_index.yaml`
- Verify: `AI_SKILL_LIBRARY/v4/releases/current.json`
- Verify: `AI_SKILL_LIBRARY/v4/releases/4.8.1/manifest.yaml`

**Interfaces:**
- Consumes: Tasks 1–3.
- Produces: evidence that the existing brain architecture remains valid and the `video_prompt` capsule actually carries the strengthened output contract.

- [ ] **Step 1: Run repository single-entrypoint validation**

```bash
python AI_SKILL_LIBRARY/v4/tools/ci_validate.py --source-sha "$(git rev-parse HEAD)"
```

Expected: `CI_VALIDATE=PASS failures=0`.

- [ ] **Step 2: Verify the generated Skill Gateway snapshot**

Confirm:

- `skills.video_prompt.triggers` includes `animation prompt`, `image to video prompt`, `i2v prompt`;
- `skills.animation.triggers` remains exactly `animation`;
- `capsules.video_prompt.output_contract` contains the strengthened animation-safety semantics;
- primary skill count remains unchanged;
- no ambiguous trigger or alias errors occur.

- [ ] **Step 3: Verify PR CI is green**

Use the latest PR head SHA and GitHub Actions run/job logs. Required workflow: `AI Skill Library CI`. All steps must pass, including `ci_validate.py`, ingest dry run, and upstream repository audit.

- [ ] **Step 4: Review the PR diff for scope and protected regressions**

Confirm only the spec/plan, focused regression test, canonical `video_prompt` contract/triggers, prompt-media quality gates, and reference-only candidate metadata changed. Confirm no trading, security, permission, runtime, secret, or production-deployment settings changed.

- [ ] **Step 5: Do not merge or call Stable updated unless merge/promotion is separately allowed and verified**

Branch/PR completion is distinct from main/Stable promotion. Report exact state and evidence.
