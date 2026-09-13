# Harmonized Skills Expansion Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add four distinct canonical skills, strengthen overlapping existing skills, capture vetted upstream patterns without parallel authority, and preserve GITHUB_BRAIN_V4 routing/security/runtime invariants.

**Architecture:** Extend the existing catalog/router/domain-manifest path only. New upstream repositories remain reference/evidence inputs through capability fusion and Evergreen provenance metadata. Generated retrieval/snapshot/release artifacts are rebuilt by canonical tools and are never hand-edited.

**Tech Stack:** YAML skill/router manifests, Python 3.12 validators/tests, GitHub Actions, Cloudflare Skill Gateway release tooling.

**Spec:** `docs/superpowers/specs/2026-09-13-harmonized-skills-expansion-design.md`

## Global Constraints

- Exactly one primary reasoning skill per routed request.
- Maximum supporting skills remain controlled by existing runtime profiles.
- No duplicate trigger ownership after compilation.
- No parallel reasoning authority from upstream repositories/providers/plugins.
- `quant_validation` remains analysis-only/read-only and cannot grant execution authority.
- Zero-local cloud runtime is preserved; no new mandatory local dependency.
- Stable security, project authority, freshness, and permission ceilings cannot be weakened.
- Retrieval index, gateway snapshot, and immutable release metadata are generated only by canonical tools.
- Protected regression tolerance remains 0.0 for correctness, authority, security, verification, and project isolation.

---

### Task 1: RED contract tests for the new skill surface

**Files:**
- Create: `AI_SKILL_LIBRARY/tests/test_harmonized_skills_expansion.py`
- Read: `AI_SKILL_LIBRARY/v4/tools/compile_skill_gateway.py`

**Interfaces:**
- Consumes: canonical catalog/router/manifests and `compile_snapshot(ROOT, sha, generated_at=...)`.
- Produces: failing behavioral contracts for skill presence, domain ownership, capsules, routing boundaries, and upstream reference policy.

- [ ] **Step 1: Write failing tests** asserting:
  - `skill_engineering` and `eval_engineering` compile under engineering.
  - `quant_validation` compiles under trading and inherits trading read-only/project-authority boundaries.
  - `asset_validation_3d` compiles under design_3d.
  - representative primary triggers are unique.
  - `quant_backtesting` does not own `validate this backtest`.
  - Blender creation stays owned by `blender`, while export/asset validation belongs to `asset_validation_3d`.
  - upstream source names are recorded as reference patterns, not provider/reasoning authority.
- [ ] **Step 2: Open a draft PR to `main` so `AI Skill Library CI` runs the RED suite.**
- [ ] **Step 3: Verify failure reason is missing new skill behavior, not malformed test code.**

### Task 2: Add the four canonical skills and unambiguous routing ownership

**Files:**
- Modify: `AI_SKILL_LIBRARY/skills/catalog.yaml`
- Modify: `AI_SKILL_LIBRARY/v4/stable/router.yaml`
- Modify: `AI_SKILL_LIBRARY/v4/skills/engineering/manifest.yaml`
- Modify: `AI_SKILL_LIBRARY/v4/skills/trading/manifest.yaml`
- Modify: `AI_SKILL_LIBRARY/v4/skills/design_3d/manifest.yaml`
- Modify only if needed for language aliases: `AI_SKILL_LIBRARY/v4/runtime/routing_aliases.yaml`

**Interfaces:**
- Produces canonical IDs: `skill_engineering`, `eval_engineering`, `quant_validation`, `asset_validation_3d`.
- Compiler must produce a capsule for every new canonical ID.

- [ ] **Step 1: Add minimal catalog rows** with narrow triggers/excludes/output contracts.
- [ ] **Step 2: Add each ID to exactly one router domain and matching V4 domain manifest.**
- [ ] **Step 3: Preserve trading `project_authority_required`, read-only analysis classification, and execution authority inheritance.**
- [ ] **Step 4: Run CI through the draft PR; new RED contracts must turn GREEN without breaking existing compiler/validator tests.**

### Task 3: Strengthen existing canonical skills instead of duplicating them

**Files:**
- Modify: `AI_SKILL_LIBRARY/skills/catalog.yaml`
- Modify: `AI_SKILL_LIBRARY/v4/runtime/routing_aliases.yaml` only where an alias is needed.
- Test: `AI_SKILL_LIBRARY/tests/test_harmonized_skills_expansion.py`

**Interfaces:**
- `security` absorbs repository-grounded threat-model intent.
- `debugging` absorbs GitHub Actions/CI failure diagnosis intent.
- `ux_ui` / `product_design` absorb design-system/design-to-code verification intent.
- `quant_backtesting` stays experiment construction/execution; `quant_validation` owns methodological audit.

- [ ] **Step 1: Add boundary tests for neighboring intents.**
- [ ] **Step 2: Add only the minimum trigger/alias/output-contract changes needed to preserve one owner per purpose.**
- [ ] **Step 3: Verify no alias row becomes primary and no trigger collision appears in compiled snapshot.**

### Task 4: Capture vetted upstream patterns and provenance without runtime dependency

**Files:**
- Modify: `AI_SKILL_LIBRARY/v4/stable/capability_fusion.yaml`
- Modify: `AI_SKILL_LIBRARY/v4/evergreen/discovery.yaml` only when a discovery query is missing.
- Create: `AI_SKILL_LIBRARY/v4/evergreen/quarantine/harmonized_skills_expansion.yaml`
- Test: `AI_SKILL_LIBRARY/tests/test_harmonized_skills_expansion.py`

**Interfaces:**
- References: `openai/skills`, `agentskills/agentskills`, `ml4t/skills`, `ifBars/blender-agent-studio`.
- Every reference declares status, absorbed patterns, code reuse policy, and non-authority/runtime-dependency constraints.

- [ ] **Step 1: Add RED assertions for all four provenance entries and their non-authority status.**
- [ ] **Step 2: Add native capability-fusion mappings.**
- [ ] **Step 3: Record provenance/license/risk/overlap decision in quarantine metadata; no external framework becomes mandatory.**
- [ ] **Step 4: Verify financial capability remains quarantined from permission expansion.**

### Task 5: Full validation, generated artifacts, immutable release, and production gate

**Files:**
- Generated by canonical tooling only: retrieval index, compiled gateway snapshot, release manifest/history/pointer if release is built.
- No manual edits to generated artifacts.

**Interfaces:**
- Validation entrypoint: `python AI_SKILL_LIBRARY/v4/tools/ci_validate.py --source-sha <sha>`.

- [ ] **Step 1: Ensure draft PR CI is fully green.**
- [ ] **Step 2: Review changed files/diff for scope creep and permission changes.**
- [ ] **Step 3: Rebuild generated artifacts using the canonical tooling required by CI/release workflow.**
- [ ] **Step 4: Re-run full CI and require zero protected regressions.**
- [ ] **Step 5: Mark PR ready only after GREEN evidence.**
- [ ] **Step 6: Merge only with green required checks and exact head SHA.**
- [ ] **Step 7: Treat production runtime as updated only after exact-SHA post-merge deployment/health verification; otherwise report implementation merged but production verification pending.**

## Self-review

- Spec coverage: all four new canonical skills, four strengthen-not-duplicate areas, provenance/license intake, routing ownership, financial permission ceiling, zero-local constraint, validators, generated artifacts, and release verification have explicit tasks.
- Placeholder scan: no TBD/TODO/implement-later placeholders.
- Type/name consistency: skill IDs exactly match the approved spec and router/manifest/compiler naming conventions.
