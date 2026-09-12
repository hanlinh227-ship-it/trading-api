# Creative Visual Fusion Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a canonical Creative Visual Fusion capability to GITHUB_BRAIN_V4 that improves image prompting, storyboard/script decomposition, visual continuity, design reasoning, and image/video editing without creating duplicate authorities or mandatory external runtime dependencies.

**Architecture:** Keep the existing task router, primary skills, Capability Fusion, Harmonization, security, and project authority unchanged. Add one checkpoint-resolved creative capability policy consumed only for relevant prompt/design/adobe/writing work; register open-source sources as reference/RAG inputs and release the change as an immutable V4 bundle.

**Tech Stack:** YAML policy contracts, Python unittest contract tests, existing V4 release tooling/validators, GitHub Actions Skill Gateway deployment.

**Spec:** `docs/superpowers/specs/2026-09-12-creative-visual-fusion-design.md`

## Global Constraints
- One canonical reasoning authority chain.
- No parallel creative router/brain.
- Existing canonical skills are strengthened rather than duplicated.
- Zero-local cloud runtime remains the default.
- Open-source repositories are reference/evidence inputs only.
- No hidden chain-of-thought persistence.
- Stable security/project authority outrank creative capability patterns.
- FAST keeps zero external routing calls.
- Behavior changes use RED -> GREEN -> full verification.

---

### Task 1: Creative Fusion Contract Tests

**Files:**
- Create: `AI_SKILL_LIBRARY/tests/test_v4_creative_visual_fusion.py`

**Interfaces:**
- Consumes: existing `checkpoint.json`, `capability_fusion.yaml`, `harmonization.yaml`, `runtime.yaml`, `skills/catalog.yaml`, `sources.yaml`.
- Produces: regression contract for the creative capability policy and source registry.

- [ ] Write failing tests asserting checkpoint pointer, single authority, canonical skill reuse, bounded continuity/edit behavior, FAST safety, upstream source registration, and training=false.
- [ ] Open PR so GitHub Actions demonstrates RED because the creative policy/pointer/source additions do not yet exist.

### Task 2: Canonical Creative Visual Fusion Policy

**Files:**
- Create: `AI_SKILL_LIBRARY/v4/stable/creative_visual_fusion.yaml`
- Modify: `AI_SKILL_LIBRARY/checkpoint.json`
- Modify: `AI_SKILL_LIBRARY/v4/stable/capability_fusion.yaml`
- Modify: `AI_SKILL_LIBRARY/v4/stable/harmonization.yaml`

**Interfaces:**
- Consumes: existing capability-fusion authority and harmonization rules.
- Produces: checkpoint-resolved native creative capability contract.

- [ ] Add six native modules: creative_direction, script_to_shots, visual_prompt_compiler, continuity_engine, visual_edit_reasoning, render_quality_critic.
- [ ] Explicitly declare `routing_authority: false`, `reasoning_authority: false`, canonical-skill-first, zero-local, permission non-expansion, bounded continuity, fail-closed edit targeting.
- [ ] Wire creative fusion as a sub-capability of Capability Fusion, not a parallel authority.
- [ ] Extend harmonization future-upgrade contract so new creative methods pass overlap/dedupe/license/security/eval gates.

### Task 3: Open-Source Creative Source Registry

**Files:**
- Modify: `AI_SKILL_LIBRARY/sources.yaml`

**Interfaces:**
- Consumes: source registry usage-tier/license policy.
- Produces: approved reference/RAG inputs for creative methods.

- [ ] Register verified repositories for ControlNet, IP-Adapter, Segment Anything, GroundingDINO, Real-ESRGAN, and ComfyUI where license metadata is acceptable.
- [ ] Mark all creative upstreams `training: false` through registry defaults.
- [ ] Use reference-only for sources whose code/runtime should not become a Stable dependency.

### Task 4: Runtime/Skill Integration Without Duplication

**Files:**
- Modify only if needed after tests: `AI_SKILL_LIBRARY/v4/stable/runtime.yaml`
- Modify only if needed after tests: `AI_SKILL_LIBRARY/skills/catalog.yaml`

**Interfaces:**
- Consumes: existing canonical creative skills.
- Produces: profile-aware creative fusion activation while preserving primary-skill selection.

- [ ] Keep existing skill IDs (`image_prompt`, `video_prompt`, `prompt_debugging`, `character_consistency`, `scene_continuity`, `camera_direction`, `storyboard`, design/adobe/writing skills) as the routing surface.
- [ ] Do not add semantically equivalent primary skills.
- [ ] FAST uses a lightweight creative contract only; STANDARD/DEEP may use bounded continuity/critic modules.

### Task 5: Immutable Release and Verification

**Files:**
- Create: `AI_SKILL_LIBRARY/v4/releases/<next>/manifest.yaml`
- Modify: `AI_SKILL_LIBRARY/v4/releases/current.json`
- Modify release history only if required by existing release contract.

**Interfaces:**
- Consumes: exact changed Stable file hashes.
- Produces: immutable capability release suitable for exact-SHA Skill Gateway deployment.

- [ ] Run full Brain unittest suite and validators.
- [ ] Compile/validate Skill Gateway snapshot.
- [ ] Verify release manifest hashes.
- [ ] Run PR CI and review failures rather than bypassing them.
- [ ] Merge only after canonical CI is green.
- [ ] Verify exact-main Cloudflare deployment, `/brain/health`, and route matrix after merge.
- [ ] Treat unrelated external Cloudflare GitHub App status separately from the canonical GitHub Actions deployment.
