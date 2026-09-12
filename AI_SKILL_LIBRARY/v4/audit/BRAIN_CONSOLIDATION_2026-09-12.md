# GITHUB_BRAIN_V4 consolidation audit — 2026-09-12

Tier: COLD (audit record; not loaded on the request path).
Baseline main SHA at audit start: `3216b6b19d8685f4c05ccc8450be1cc8a2c0fa30` (release `4.2.0`).
Baseline: 126 Brain unit tests + 26 root tests green; 9 validators at 0 errors.

Principle applied: ONE BRAIN → ONE ROUTER → ONE AUTHORITY CHAIN → CANONICAL SKILLS → BOUNDED SUPPORTING SKILLS → RELEVANT SOURCES ONLY → FAST RETRIEVAL → VERIFIED OUTPUT.

## 1. Inventory and disposition

| Component | Location | Disposition | Reason |
|---|---|---|---|
| Brain authority | `checkpoint.json`, `GITHUB_BRAIN_V4.md`, `AI_GLOBAL_CHECKPOINT.md`, `AGENTS.md`, `CLAUDE.md` | KEEP | single canonical chain; checkpoint is discovery root |
| Router (canonical) | `v4/stable/router.yaml` + compiled Skill Gateway snapshot | KEEP | only routing authority |
| Router (legacy V2) | `router.yaml` | ALIAS | parallel skill list + execution order; now explicitly `routing_authority: false`, `mode: compatibility_adapter` |
| Runtime | `v4/stable/runtime.yaml` | KEEP + SIMPLIFY | budgets now cross-checked against `v4/stable/budgets.yaml` |
| Runtime (legacy) | `runtime.yaml`, `kernel.yaml`, `bootstrap.yaml`, `context.yaml`, `reliability.yaml`, `evidence.yaml`, `memory.yaml`, `observability.yaml`, `security.yaml`, `migration.yaml`, `CORE_PROTOCOL.md` | ALIAS (compat, COLD) | still pinned by `validate_v3.py` + legacy tests; each now carries `superseded_by: GITHUB_BRAIN_V4` |
| Project authority | `projects.yaml`, `docs/checkpoints/CURRENT_HANDOFF.md` | KEEP | unchanged; Trading authority external to Brain |
| Skills catalog | `skills/catalog.yaml` (118 rows) | MERGE/ALIAS | 14 rows aliased to canonical skills (see §3.2) |
| Domain manifests | `v4/skills/*/manifest.yaml` | SIMPLIFY | alias ids moved from `skills:` to `legacy_aliases:` |
| Legacy skill markdown | `skills/**/*.md` (26) | KEEP (WARM) | still the canonical reasoning text for trading/core skills; alias ids documented |
| Adapters | `v4/skills/legacy_catalog_adapter.yaml` | KEEP | single adapter, not nested |
| Routing aliases | `v4/runtime/routing_aliases.yaml` | KEEP | merged into HOT snapshot |
| Providers / plugins | `skills/providers/crypto_agents.yaml`, `plugins.yaml` | KEEP | evidence/tool metadata; zero routing authority (already) |
| Upstream sources | `sources.yaml` (60), `sources/crypto_agent_official.yaml` | SIMPLIFY | tiers + precedence + growth cap added; no source removed |
| Checkpoints (Brain) | `v4/releases/*` | KEEP + REWRITE history | `history.yaml` omitted 4.0.2/4.1.0/4.2.0 → rollback impossible; now generated |
| Checkpoints (Trading) | `docs/checkpoints/*` | KEEP | untouched |
| Checkpoints (other) | `CHECKPOINTS/KAGGRICULTURE_*` | QUARANTINE (documented) | second checkpoint directory; non-Brain, non-Trading; not routed |
| Manifests / release tool | `v4/tools/release.py` | REWRITE (extend) | `build` command generates manifest + hashes + history; no manual SHA256 |
| Validators | `validate_*.py` (9) + `v4/tools/*` | KEEP + MERGE entrypoint | one `v4/tools/ci_validate.py` runs everything once; duplicate checks documented |
| Tests | `AI_SKILL_LIBRARY/tests` (24 files), `tests/` (4) | KEEP + ADD | `test_v4_consolidation.py` locks every fix below |
| CI workflows (canonical) | 6 brain/gateway workflows | SIMPLIFY | shared validation step; concurrency race removed |
| CI workflows (retired one-shots) | `meme-alpha-*` (307), `run-signalhub-*` (14) | ARCHIVE | retired execution authorities per `CURRENT_HANDOFF.md`; moved to `.github/workflows-archive/` (git history preserved) |
| CI workflows (bybit/btc/kaggriculture one-shots) | ~90 | QUARANTINE (unchanged) | trading-adjacent; out of Brain scope; listed for owner review |
| Cloudflare Worker | `cloudflare-worker/skill-gateway*.js` | KEEP | zero-network routing, first in chain |
| Deployment workflows | `deploy-skill-mandatory-fast-gateway.yml`, `deploy-cloudflare-worker.yml` | SIMPLIFY | same concurrency group with cancel-in-progress → mutual cancellation; now queued |
| Memory | `v4/stable/memory.yaml` | SIMPLIFY | explicit working/project/durable_preferences layers; `authority: false` |
| Semantic retrieval / caches | `v4/stable/context.yaml`, `capability_fusion.yaml` | SIMPLIFY | new `v4/stable/retrieval.yaml` is the single retrieval contract (exact-before-semantic, HOT/WARM/COLD) |
| Capability fusion | `v4/stable/capability_fusion.yaml` | KEEP | subordinate; budgets referenced from `budgets.yaml` |
| Creative fusion | `v4/stable/creative_visual_fusion.yaml` | SIMPLIFY | bindings use canonical ids only; `shared_logic_owner` map |
| Trading authority | `projects.yaml` → `docs/checkpoints/CURRENT_HANDOFF.md` | KEEP + GUARD | bridge `authority_required` now enforced in `mesh.py`; analysis-only skills locked |
| Legacy compatibility | `GITHUB_BRAIN_V1/2/3.md`, `LEGACY_CLEANUP.md`, `README.md` | REWRITE docs | README/LEGACY_CLEANUP claimed V2 as authority → corrected/archived |
| Stray root files | `request.json`, `scan-request.json`, `index.html` | QUARANTINE (documented) | trading/legacy artifacts outside Brain scope; not touched |

## 2. Conflicts found (root cause → impact → owner → fix → regression test)

### 2.1 Authority conflicts
- **A1** `kernel.yaml:2 authority: GITHUB_BRAIN_V3`, `migration.yaml current: 3.0.0 / authority: GITHUB_BRAIN_V3.md`, `bootstrap.yaml checkpoint_id: GITHUB_BRAIN_V3`.
  Root cause: V3→V4 promotion left legacy control-plane files self-describing as current. Impact: an agent that lands on these files first could adopt V3 as authority. Owner: `checkpoint.json`. Fix: every legacy file with a non-V4 authority claim declares `superseded_by: GITHUB_BRAIN_V4` and `authority_role: compatibility_alias`; schema/tests that pin the V3 literal are unchanged (reversible). Test: `test_legacy_control_plane_files_declare_v4_supersession`.
- **A2** `README.md` and `LEGACY_CLEANUP.md` named `GITHUB_BRAIN_V2` as the global authority. Fix: README rewritten to V4 bootstrap; LEGACY_CLEANUP archived under `v4/audit/`. Test: `test_no_document_claims_pre_v4_authority`.
- **A3** Authority precedence chain duplicated in 4 files (`GITHUB_BRAIN_V4.md`, `evidence.yaml`, `harmonization.yaml`, `capability_fusion.yaml`). Fix: `v4/stable/evidence.yaml.source_precedence` is canonical; consistency asserted. Test: `test_single_authority_precedence_chain`.

### 2.2 Skill conflicts
- **S1** 11 legacy V2 skill ids duplicate canonical V4 skills with identical purpose: `software_engineering→coding`, `debugging_tdd→debugging`, `platform_engineering→deployment`, `game_dev→game_development`, `design_2d_ux→ux_ui`, `design_3d_blender→blender`, `adobe_media→photoshop` (application-agnostic Adobe workflow), `image_video_generation→image_prompt`, `generative_media→video_prompt`, `data_documents→report`, `marketing_business→marketing`. Ten of them were routable in manifests but unreachable through `domain_routes` (orphaned); `marketing_business` competed with `marketing`/`business` for the primary role.
  Root cause: V2 catalog merged into V4 catalog without dedupe. Impact: two skills for one purpose, ambiguous primary selection, wasted catalog scans. Fix: `alias_of` on each row; compiler folds alias triggers into the canonical skill, emits `skill_aliases`, alias rows are never `primary_selectable`. Test: `test_alias_rows_never_primary_and_fold_into_canonical`, `test_no_two_active_skills_share_purpose`.
- **S2** Near-duplicates inside canonical set: `trading→trading_router`, `backtesting→quant_backtesting`, `presentation→slides`. Same fix as S1 (aliased). Kept distinct because materially different contracts: `risk_management` (analysis) vs `risk_execution` (execution gate), `technical_analysis` vs `market_analysis`, `troubleshooting`/`error_recovery`/`debugging`, `learning`/`general_problem_solving`.
- **S3** Creative fusion bindings referenced the alias ids `image_video_generation`, `generative_media`. Fix: bindings use canonical ids only; shared creative logic has one owner skill each. Test: `test_creative_bindings_are_canonical_and_shared_logic_has_single_owner`.

### 2.3 Router conflicts
- **R1** Two routers: legacy `router.yaml` (V2 skills/execution_order) and `v4/stable/router.yaml`. Fix: legacy router declares `routing_authority: false`, `canonical_router: AI_SKILL_LIBRARY/v4/stable/router.yaml`. Test: `test_exactly_one_router_has_routing_authority`.
- **R2** Router domain names (`design_2d`, `design_3d`, `prompt_media`) differ from catalog template domains (`design`, `prompt`) — compiler uses router domains, so no runtime ambiguity; documented in `workspace_map.yaml` instead of renaming (no path churn).
- **R3** Routing normalization mismatch: Python `casefold()` vs JS `toLocaleLowerCase('und')`. Impact: triggers with ß-like characters could never match. Fix: compiler rejects trigger/alias terms whose casefold ≠ lower; test `test_routing_terms_are_lowercase_stable`.

### 2.4 Provider conflicts
- **P1** None active: provider registries already `routing_authority: false`, conflict policy forbids majority vote. Locked by `test_no_provider_or_plugin_has_routing_authority`.

### 2.5 Memory conflicts
- **M1** Memory policy in 4 files with different key names (`current_project_authority_precedes_memory` vs `current_authority_precedes_memory`); no validator checked the legacy key. Fix: `v4/stable/memory.yaml` gains `authority: false`, explicit `layers.working/project/durable_preferences`, `conflict_action: reverify_or_supersede`, `never_store`; legacy `memory.yaml` marked superseded. Test: `test_memory_is_context_not_authority`.

### 2.6 Checkpoint / release conflicts
- **C1** `v4/releases/history.yaml` listed only 4.0.0/4.0.1 while pointer was 4.2.0 → `release.py rollback` raised "current release is not present in known-good history". Root cause: manual manifest/history editing. Fix: `release.py build --version X --note ...` generates manifest hashes, updates pointer and history atomically; `validate_v4`-level check via `test_release_history_contains_current_release_and_is_rollbackable`.
- **C2** Second checkpoint directory `CHECKPOINTS/` (Kaggriculture). Not a Brain/Trading authority; documented in `workspace_map.yaml` as out-of-scope so no router path resolves to it.

### 2.7 Source conflicts
- **SRC1** 60 sources without tier/precedence and without growth cap. Fix: `sources.yaml.policy` gains `tiers`, `precedence`, `max_sources_per_category`; every entry gets `tier` via defaults. Test: `test_sources_have_tier_and_bounded_growth`.

### 2.8 Runtime / budget conflicts
- **RT1** Budget numbers duplicated and divergent: `orchestration.yaml max_nodes 12 / max_tool_calls 16` vs `capability_fusion max_nodes_deep 10`; `max_revisions` only in harmonization. Fix: `v4/stable/budgets.yaml` is the single budget authority; validator asserts runtime/fusion/orchestration/harmonization/creative values ≤ budgets. Test: `test_budgets_single_source_and_consistent`.
- **RT2** FAST allowed semantic cache in `capability_fusion.fast_knowledge_plane` and `context.cache`. Fix: FAST is exact-only (`fast_exact_only: true`); semantic cache/retrieval is STANDARD/DEEP only. Test: `test_fast_path_is_exact_only_and_lightweight`.

### 2.9 Creative conflicts
- **CR1** See S3. Continuity/identity/mask-first/negative-constraint logic lives in `creative_visual_fusion.modules` and is bound to exactly one canonical owner skill each.

### 2.10 Trading conflicts
- **T1** `bridges.yaml trading_to_engineering allow: [bot_implementation]` with `authority_required: true`, but `mesh.py` never read `authority_required`. Impact: an engineering-domain request could pull trading context without the Trading authority gate. Fix: `mesh.py.resolve_context_nodes` requires `authority_loaded=True` for any bridge with `authority_required`; `validate_v4` asserts every trading bridge is `authority_required: true`. Test: `test_trading_bridges_require_authority_and_mesh_enforces_it`.
- **T2** Research/multi-market skills must never gain execution permissions. Fix: trading manifest declares `execution_authority: external_project_only` and `analysis_only_skills`; capsule permissions for trading are `read_only` only. Test: `test_trading_skills_cannot_expand_execution_authority`.

### 2.11 Deployment conflicts
- **D1** `deploy-cloudflare-worker.yml` and `deploy-skill-mandatory-fast-gateway.yml` share concurrency group `cloudflare-zero-local-runtime-production` with `cancel-in-progress: true` and overlapping trigger paths → a push touching `cloudflare-worker/**` cancels one deploy mid-flight. Fix: `cancel-in-progress: false` (queue, exact-main both). Test: `test_production_deploy_workflows_do_not_cancel_each_other`.
- **D2** Validator/test steps copy-pasted across 6 workflows (`validate_router` ×5, `validate_authority` ×6, snapshot compile ×6). Fix: `v4/tools/ci_validate.py` single entrypoint; workflows call it. Test: `test_ci_workflows_use_single_validation_entrypoint`.

## 3. Bottlenecks (before → after)

| Bottleneck | Before | After |
|---|---|---|
| GitHub Actions workflow files parsed per push | 430 | 109 (321 retired one-shots archived) |
| Validator invocations across canonical CI per PR | ~27 steps in 5 workflows | 1 entrypoint per workflow |
| Skills competing for primary role | 118 rows, 108 routable (incl. 4 duplicates), 10 orphaned | 105 routable (incl. task_router), 14 aliases folded, 0 orphaned, 0 ambiguous trigger terms |
| Retrieval contract files | 3 (context/capability_fusion/memory) | 1 canonical (`retrieval.yaml`) + references |
| Budget definitions | 5 files, divergent | 1 (`budgets.yaml`) + consistency validator |
| Release hash maintenance | manual SHA256 | `release.py build` |
| Rollback | impossible (history stale) | possible (history generated) |
| FAST preload | exact+semantic cache eligible | exact-only, HOT tier only |
| Lookup "where is X" | read README (stale) | `v4/index/workspace_map.yaml` + `retrieval_index.yaml` |

## 4. Performance budgets
See `v4/stable/budgets.yaml` (single source). FAST: 1 skill load, 0 supporting, 0 sources, ≤3 index hits, 1 retrieval stage (exact), 1 graph node, 0 revisions, 0 durable memory, ≤2500 context tokens, ≤2 file reads (checkpoint + snapshot), 0 tool calls.

## 5. Not done (deliberately)
- Legacy top-level YAML files not moved: pinned by `validate_v3.py`, schemas and 8 tests; moving = path churn without lookup gain. They are COLD-tier and marked superseded.
- Bybit/BTC/Kaggriculture one-shot workflows not archived: trading-adjacent; owner review required (listed in `workspace_map.yaml`).
- Brain V5 not created; router not duplicated; no new framework dependency.

## 6. Known limitations recorded at review
- Release rollback is pointer-only (unchanged design): rolling the pointer back to 4.2.0 also requires reverting the stable files to that release's hashes (`git revert` of the release commit); `release.py verify` will report the mismatch otherwise.
- `v4/tools/evergreen.py` still emits per-skill manifest rows; `release.py check` accepts extra rows as long as every canonical `RELEASE_FILES` entry is present and fresh. Evergreen promotion remains gated to 4.0.x by its own `_next_release` (pre-existing).
- Full CI runs the validator set twice (once directly, once inside `test_ci_validate_entrypoint_runs_clean`); accepted for now, ~6 s.
- Historical trading checkpoints are indexed as one COLD directory pointer so routine trading handoffs never stale the Brain index or block a Brain deploy.
