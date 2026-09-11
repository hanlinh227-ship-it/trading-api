# GITHUB_BRAIN_V2 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the flat V1 bootstrap with a modular V2 router/skill/plugin/authority architecture, remove superseded state files from `main`, and activate `GITHUB_BRAIN_V2` without breaking the existing license-aware source pipeline.

**Architecture:** `checkpoint.json` points to one V2 checkpoint. `router.yaml` owns task-to-skill and project-authority routing; skills are focused Markdown contracts; `plugins.yaml` maps logical capabilities; `sources.yaml` remains knowledge-only. Validation is split so source/license checks and brain/router checks can fail independently.

**Tech Stack:** Markdown, YAML, JSON, Python 3.12, PyYAML, unittest, GitHub Actions.

**Spec:** `docs/superpowers/specs/2026-09-11-github-brain-v2-design.md`

## Global Constraints

- Stable checkpoint ID: `GITHUB_BRAIN_V2`.
- Compatibility activation alias: `GITHUB_BRAIN_V1` routes to V2 during migration.
- Default domain-skill budget: one primary plus at most two supporting skills.
- Core review layers `critical_thinking` and `verification` do not count toward that budget.
- Do not globally preload trading state.
- One current authority per project scope.
- New source entries default to non-training unless explicitly approved.
- Never execute third-party repositories merely to ingest knowledge.
- Git history, not duplicate working-tree snapshots, is the archive for retired checkpoint/update files.

---

### Task 1: Define V2 integration contracts first

**Files:**
- Modify: `AI_SKILL_LIBRARY/tests/test_integration.py`
- Create: `AI_SKILL_LIBRARY/tests/test_brain_v2.py`

**Interfaces:**
- Consumes: current V1 files.
- Produces: failing tests that define the V2 checkpoint, router, plugin registry, authority uniqueness, skill-path existence, and compatibility alias behavior.

- [ ] **Step 1: Update the checkpoint contract test to expect V2**

Add assertions equivalent to:

```python
manifest = json.loads((LIB / 'checkpoint.json').read_text(encoding='utf-8'))
self.assertEqual(manifest['checkpoint_id'], 'GITHUB_BRAIN_V2')
self.assertIn('GITHUB_BRAIN_V1', manifest['activation_aliases'])
self.assertEqual(manifest['router_path'], 'AI_SKILL_LIBRARY/router.yaml')
self.assertEqual(manifest['plugins_path'], 'AI_SKILL_LIBRARY/plugins.yaml')
```

- [ ] **Step 2: Add router/skill/authority tests**

Create tests that load `router.yaml` and assert:

```python
self.assertEqual(router['version'], 2)
self.assertEqual(router['defaults']['max_domain_skills'], 3)
self.assertEqual(len(set(skill_ids)), len(skill_ids))
for skill in router['skills']:
    self.assertTrue((ROOT / skill['path']).is_file())
```

Also test that every `requires`/`conflicts_with` ID exists and that each `authorities` scope has exactly one `CURRENT_AUTHORITY` entry.

- [ ] **Step 3: Add conflict rejection unit test for `validate_brain.py`**

Use an in-memory router containing two `CURRENT_AUTHORITY` entries for the same scope and assert the validator reports an error containing `multiple current authorities`.

- [ ] **Step 4: Commit the tests before implementation**

Commit message: `test: define GITHUB_BRAIN_V2 contracts`.

- [ ] **Step 5: Verify RED in GitHub Actions**

Open/update the PR and confirm the AI Skill Library CI fails because V2 files/fields are missing. The expected failure is missing `router.yaml`, `plugins.yaml`, `GITHUB_BRAIN_V2.md`, or V1 manifest assertions no longer matching.

---

### Task 2: Implement the V2 bootstrap and routing schema

**Files:**
- Replace: `AI_SKILL_LIBRARY/checkpoint.json`
- Create: `AI_SKILL_LIBRARY/GITHUB_BRAIN_V2.md`
- Create: `AI_SKILL_LIBRARY/CORE_PROTOCOL.md`
- Create: `AI_SKILL_LIBRARY/router.yaml`
- Create: `AI_SKILL_LIBRARY/plugins.yaml`
- Remove after green migration: `AI_SKILL_LIBRARY/AI_GLOBAL_CHECKPOINT.md`

**Interfaces:**
- Produces: a stable bootstrap contract consumed by agents, tests, and `validate_brain.py`.

- [ ] **Step 1: Write V2 manifest**

Manifest must include:

```json
{
  "checkpoint_id": "GITHUB_BRAIN_V2",
  "version": "2.0.0",
  "canonical_repo": "hanlinh227-ship-it/trading-api",
  "canonical_branch": "main",
  "checkpoint_path": "AI_SKILL_LIBRARY/GITHUB_BRAIN_V2.md",
  "router_path": "AI_SKILL_LIBRARY/router.yaml",
  "plugins_path": "AI_SKILL_LIBRARY/plugins.yaml",
  "registry_path": "AI_SKILL_LIBRARY/sources.yaml",
  "validator_path": "AI_SKILL_LIBRARY/validate_brain.py",
  "activation_key": "GITHUB_BRAIN_V2",
  "activation_aliases": ["GITHUB_BRAIN_V1"],
  "mode": "github-first-routed",
  "fallback": "continue_from_last_known_context_and_disclose_refresh_failure"
}
```

- [ ] **Step 2: Add `CORE_PROTOCOL.md`**

It must define evidence hierarchy, fact/inference separation, freshness checks for current data, project-state precedence, explicit uncertainty, critical review before final conclusions, and verification-before-completion.

- [ ] **Step 3: Add `router.yaml`**

Define schema version 2, default skill budget, skill registry, composite routes for trading/game/creative/engineering/research/document tasks, and project authorities. The trading authority must point to `docs/checkpoints/CURRENT_HANDOFF.md` as `CURRENT_AUTHORITY` and treat older trading state as non-authoritative.

- [ ] **Step 4: Add `plugins.yaml`**

Define logical capabilities for Figma, Product Design, Runway, to3D, Scite, Massive, Binance, and Superpowers with `optional: true`; routing must not fail if unavailable.

- [ ] **Step 5: Add `GITHUB_BRAIN_V2.md`**

Document the exact flow: checkpoint -> router -> selected skills -> project authority -> sources/plugins -> critical review -> execution -> verification. Explicitly prohibit loading all skills or all project states.

- [ ] **Step 6: Commit**

Commit message: `feat: add GITHUB_BRAIN_V2 routed bootstrap`.

---

### Task 3: Add focused skill packs with room for extension

**Files:**
- Create skill files under:
  - `AI_SKILL_LIBRARY/skills/core/`
  - `AI_SKILL_LIBRARY/skills/engineering/`
  - `AI_SKILL_LIBRARY/skills/trading/`
  - `AI_SKILL_LIBRARY/skills/creative/`
  - `AI_SKILL_LIBRARY/skills/academic/`
  - `AI_SKILL_LIBRARY/skills/productivity/`

**Interfaces:**
- Consumes: `router.yaml` registry.
- Produces: small reasoning contracts with stable IDs and no project-specific state embedded in them.

- [ ] **Step 1: Add core skill files**

Create focused contracts for `task_router`, `critical_thinking`, `research`, `planning`, `verification`, and `error_recovery`.

- [ ] **Step 2: Add engineering skill files**

Create grouped contracts covering coding/software architecture/debugging/TDD/review/GitHub/API/database/security/deployment/Cloudflare/Android/web/automation/agent coordination.

- [ ] **Step 3: Add trading skill files**

Create `trading_router.md` plus focused files for market analysis/live-data validation, risk/execution, quant/backtesting, and MT5/MQL5. Trading files must say project authority is loaded only after the router selects trading.

- [ ] **Step 4: Add creative skill files**

Create grouped files for game development, 2D/UX/product design, 3D/Blender, Adobe workflows, prompt engineering, image/video generation, continuity/camera, and script/voice-over/content retention.

- [ ] **Step 5: Add academic/productivity skill files**

Create grouped files for academic research/methodology/argumentation and for data/spreadsheets/charts/reports/docx/pdf/slides/presentations.

- [ ] **Step 6: Commit**

Commit message: `feat: add modular V2 skill packs`.

---

### Task 4: Validate the brain separately from the source registry

**Files:**
- Create: `AI_SKILL_LIBRARY/validate_brain.py`
- Modify: `AI_SKILL_LIBRARY/validate_registry.py`
- Modify: `AI_SKILL_LIBRARY/sources.yaml`

**Interfaces:**
- Produces: `validate_brain_data(router, plugins, manifest)` and CLI validation for V2.

- [ ] **Step 1: Implement router validation minimally to satisfy Task 1 tests**

Validate unique skill IDs, existing paths, valid required/conflict references, plugin capability references, max-domain-skill limits for declared composite routes, and one current authority per scope.

- [ ] **Step 2: Update checkpoint validation for V2**

`validate_registry.py` should stop hard-coding `GITHUB_BRAIN_V1`; checkpoint-specific V2 structure belongs in `validate_brain.py`.

- [ ] **Step 3: Change source policy to opt-in training**

Set registry policy defaults so `default_training: false`. Preserve current entries explicitly as approved where their licensing already passes V1 policy; new entries require an explicit usage tier.

- [ ] **Step 4: Run all tests conceptually through CI and fix only V2 validation failures**

Expected green commands:

```bash
python -m py_compile AI_SKILL_LIBRARY/ingest_sources.py AI_SKILL_LIBRARY/validate_registry.py AI_SKILL_LIBRARY/validate_brain.py
python -m unittest discover -s AI_SKILL_LIBRARY/tests -v
python AI_SKILL_LIBRARY/validate_registry.py
python AI_SKILL_LIBRARY/validate_brain.py
python AI_SKILL_LIBRARY/ingest_sources.py --all --dry-run --output /tmp/ai-skill-library.jsonl
```

- [ ] **Step 5: Commit**

Commit message: `feat: validate V2 routing and authorities`.

---

### Task 5: Remove global trading preload and clean superseded checkpoint/update files

**Files:**
- Modify: `AGENTS.md`
- Delete after migration verification: `AI_SKILL_LIBRARY/AI_GLOBAL_CHECKPOINT.md`
- Delete stale root update/audit/handoff snapshots proven superseded.
- Delete retired `CHECKPOINTS/` snapshots proven unrelated to active authority.
- Delete superseded `docs/checkpoints/` update/plan/state snapshots only when the current authority does not depend on them.

**Interfaces:**
- Consumes: V2 authority registry and current trading handoff.
- Produces: a working tree with one discoverable global bootstrap and no competing global trading authority.

- [ ] **Step 1: Replace `AGENTS.md` with a concise bootstrap**

It must instruct agents to read `AI_SKILL_LIBRARY/checkpoint.json` first, route the task, then load project authority only if selected. It must retain the no-secrets/no-fabricated-data/no-risk-bypass invariants for trading without forcing non-trading tasks through trading docs.

- [ ] **Step 2: Retire the stale master authority**

Do not leave `MASTER_TRADING_STATE.md` as a competing current authority. Migrate any unique still-valid invariant needed by the current BTC authority, then delete or convert the stale file only if no active workflow references it.

- [ ] **Step 3: Remove obvious superseded snapshot files**

Use repository reference checks plus the cleanup policy from the spec. Preserve executable/runtime/config files and any document referenced by the current authority.

- [ ] **Step 4: Add a cleanup manifest**

Create `AI_SKILL_LIBRARY/LEGACY_CLEANUP.md` listing removed paths, reason, replacement authority where applicable, and a note that Git history retains them.

- [ ] **Step 5: Commit**

Commit message: `chore: remove superseded AI and project checkpoints`.

---

### Task 6: Activate CI, review, and merge only when green

**Files:**
- Modify: `.github/workflows/ai-skill-library-ci.yml`
- Modify: `AI_SKILL_LIBRARY/README.md`

**Interfaces:**
- Produces: automated enforcement on PR and `main`.

- [ ] **Step 1: Update workflow branch/path coverage**

The workflow must run on `main` and V2 branch changes and compile/run `validate_brain.py` in addition to V1 registry checks.

- [ ] **Step 2: Update README**

Describe V2 routing, extension procedure, skill budget, compatibility alias, source usage tiers, and plugin-vs-skill separation.

- [ ] **Step 3: Verify PR CI GREEN**

All compile, unittest, registry, brain, dry-run ingest, and remote upstream audit steps must succeed.

- [ ] **Step 4: Review the PR diff for accidental runtime/trading-code changes**

The V2 migration should change knowledge/protocol/checkpoint files and cleanup snapshots, not live order-execution code.

- [ ] **Step 5: Squash-merge after fresh green verification**

Use a merge message that identifies `GITHUB_BRAIN_V2`, modular skill routing, authority validation, plugin routing, and legacy cleanup.

- [ ] **Step 6: Verify the `main` push workflow GREEN**

Do not report the system active until the post-merge `main` workflow concludes successfully.
