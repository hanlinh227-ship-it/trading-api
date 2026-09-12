# Crypto Agent Skill Registry Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Integrate official crypto-agent provider capabilities into the GitHub-first Brain through a lazy, risk-gated registry while preserving one reasoning authority and deterministic conflict resolution.

**Architecture:** Every request remains routed by `task_router`. A tiny registry index is consulted on every request; provider registries are loaded only after domain selection. Provider capabilities are evidence/tool metadata, never competing reasoning authorities. HIGH_RISK capability is discoverable but non-routable and non-activating.

**Tech Stack:** YAML registry/configuration, Markdown skill protocol, Python 3 validator/tests, existing GITHUB_BRAIN_V4 validators.

**Spec:** `docs/superpowers/specs/2026-09-12-crypto-agent-skill-registry-design.md`

## Global Constraints

- Do not mutate active release hash-pinned Stable files.
- Preserve one primary domain and at most two supporting skills.
- Provider capability never overrides current project/runtime authority.
- No live credential, API key, private key, seed phrase, wallet login, trade, transfer, swap, bridge, broadcast or payment activation.
- HIGH_RISK capability must have `routing_authority: false` and `auto_activate: false`.
- External provider repositories are RAG/reference inputs, not training authority.

---

### Task 1: Registry contracts and conflict policy

**Files:**
- Create: `AI_SKILL_LIBRARY/skills/registry/index.yaml`
- Create: `AI_SKILL_LIBRARY/skills/registry/conflict_policy.yaml`

**Interfaces:**
- Consumes: existing `task_router`, skill catalog, stable evidence precedence.
- Produces: `registry_index_path`, lazy provider lookup policy, normalized conflict-resolution contract.

- [ ] **Step 1: Add registry index** with `lookup_every_request: true`, `lazy_provider_load: true`, `preload_provider_details: false`, max 3 provider candidates, canonical catalog pointer, and crypto provider registry pointer.
- [ ] **Step 2: Add conflict policy** that normalizes venue/symbol/time/unit semantics and applies current-runtime -> current-project-authority -> current-first-party -> fresher-equal-authority precedence.
- [ ] **Step 3: Verify manually** that neither file grants execution permission or creates a new current authority.

### Task 2: Crypto provider capability registry

**Files:**
- Create: `AI_SKILL_LIBRARY/skills/providers/crypto_agents.yaml`

**Interfaces:**
- Consumes: official Binance, OKX, Bybit, Gate, KuCoin and Coinbase source roots.
- Produces: normalized provider bundles and capability rows with modes `RESEARCH_SAFE`, `AUTH_READ_ONLY`, `HIGH_RISK`.

- [ ] **Step 1: Add provider bundles** with official repository URLs, upstream roots, provenance and default mode.
- [ ] **Step 2: Add normalized safe/read-only capabilities** for market data, token research, risk checks, smart money, sentiment/news and derivatives data.
- [ ] **Step 3: Add HIGH_RISK capability rows** for all trading, wallet, transfer, withdrawal, swap/bridge, signing/broadcast, payment, account mutation and DeFi/earn actions.
- [ ] **Step 4: Ensure every HIGH_RISK row** has `routing_authority: false`, `auto_activate: false`, `can_affect_real_funds: true` where applicable.

### Task 3: Wire registry into routing without parallel authorities

**Files:**
- Modify: `AI_SKILL_LIBRARY/skills/core/task_router.md`
- Modify: `AI_SKILL_LIBRARY/router.yaml`
- Modify: `AI_SKILL_LIBRARY/skills/catalog.yaml`
- Modify: `AI_SKILL_LIBRARY/v4/skills/core/manifest.yaml`
- Modify: `AI_SKILL_LIBRARY/v4/skills/trading/manifest.yaml`
- Modify: `AI_SKILL_LIBRARY/v4/mesh/domains/trading.yaml`
- Modify: `AI_SKILL_LIBRARY/skills/trading/trading_router.md`
- Modify: `AI_SKILL_LIBRARY/skills/trading/market_analysis.md`

**Interfaces:**
- Consumes: registry index and provider registry.
- Produces: one deterministic route: reasoning skill first, provider capability selection later.

- [ ] **Step 1: Update task_router protocol** to consult registry index on every request but load provider registry only after domain selection.
- [ ] **Step 2: Add router defaults** for registry index path and lazy provider lookup, without adding provider skills to primary/supporting skill counts.
- [ ] **Step 3: Add catalog metadata** describing provider registry as capability metadata, not a primary reasoning skill.
- [ ] **Step 4: Attach registry pointers** to V4 core/trading skill packs and trading domain policy without editing hash-pinned Stable release files.
- [ ] **Step 5: Update trading_router and market_analysis** to reconcile provider evidence through conflict policy and block unresolved material divergence.

### Task 4: Register official sources and Evergreen discovery

**Files:**
- Modify: `AI_SKILL_LIBRARY/sources.yaml`
- Modify: `AI_SKILL_LIBRARY/v4/evergreen/discovery.yaml`

**Interfaces:**
- Consumes: official provider repository identities.
- Produces: provenance-preserving RAG/reference sources and quarantined discovery path for future upstream skills.

- [ ] **Step 1: Add official provider repositories** with `RAG_ONLY` or `REFERENCE_ONLY`, `training: false`, licenses, and trading focus.
- [ ] **Step 2: Add crypto-provider discovery queries** to Evergreen while keeping quarantine and zero routing authority for newly discovered skills.
- [ ] **Step 3: Confirm Class D financial/credential capability cannot auto-promote.**

### Task 5: Registry validator and regression tests

**Files:**
- Create: `AI_SKILL_LIBRARY/validate_skill_registry.py`
- Create: `tests/test_skill_registry.py`
- Modify: `AI_SKILL_LIBRARY/checkpoint.json` only to add non-breaking registry/validator pointers if existing validators tolerate additional keys.

**Interfaces:**
- Consumes: registry index, conflict policy, provider registry.
- Produces: deterministic validation errors and non-zero exit on unsafe configuration.

- [ ] **Step 1: Write failing tests** for duplicate capability ids, invalid risk mode, routable HIGH_RISK capability, low-risk real-funds capability, preload-all-provider configuration, missing source repo and authority override.
- [ ] **Step 2: Run targeted tests before validator implementation** and confirm failure.
- [ ] **Step 3: Implement validator** to make tests pass.
- [ ] **Step 4: Run targeted tests** and confirm pass.
- [ ] **Step 5: Run `python AI_SKILL_LIBRARY/validate_skill_registry.py`.**
- [ ] **Step 6: Run existing `validate_brain.py`, `validate_router.py`, `validate_v4.py`, and `validate_authority.py`.**
- [ ] **Step 7: Inspect Git diff** for accidental secret material or edits to immutable hash-pinned release files.

### Task 6: Final verification and handoff

**Files:**
- Update: `crypto-agent-skills/README_SETUP.md`
- Update: `crypto-agent-skills/INSTALLED_SKILLS_REPORT.md`
- Update: `crypto-agent-skills/SETUP_ERRORS.md` only if verification finds issues.

**Interfaces:**
- Consumes: validator results and final Git diff.
- Produces: documented current state and remaining local-runtime limitations.

- [ ] **Step 1: Record registry integration state** as prepared/active-at-repo-level, not local package installation.
- [ ] **Step 2: Record HIGH_RISK remains disabled.**
- [ ] **Step 3: Re-run final validators after documentation changes.**
