# G9 Continuous Trading Intelligence — Implementation Plan

**Goal:** Extend G8 into a cloud-first, minute-aware research intelligence system that continuously improves market-reading and entry-analysis evidence while preserving all existing production execution authority boundaries.

**Architecture:** Reuse G8 BrainLoop for statistically gated strategy evolution. Add a new G9 package for minute snapshots, experience memory, learning supervision, bounded hypothesis discovery, research-evidence manifests and read-only evidence resolution. Run minute state updates in a dedicated Railway research service; keep Cloudflare/GitHub Brain as stable validated routing/evidence plane.

**Tech stack:** Python 3.13 research runtime, pytest, existing G8 modules, JSON/JSONL persistence, Railway research service, GitHub Actions CI, existing Cloudflare Skill Gateway/Brain V4 validators.

---

## Task 1 — G9 contracts and freshness semantics

**Files:**
- Create `research/cloud_10coin_backtest/g9/__init__.py`
- Create `research/cloud_10coin_backtest/g9/contracts.py`
- Create `research/cloud_10coin_backtest/tests/test_g9_contracts.py`

**RED:** tests require deterministic `MarketStateSnapshot`, `EntryContextSnapshot`, explicit venue/instrument, event/ingest times, quote age, provenance, UNKNOWN degradation, and `production_execution_authority=False`.

**GREEN:** implement frozen dataclasses/serializers and freshness classification (`FRESH`, `DEGRADED`, `STALE`) with >5s live-claim fail-closed semantics.

**Regression:** run targeted G9 tests then all research tests.

## Task 2 — Deterministic minute market-state engine

**Files:**
- Create `research/cloud_10coin_backtest/g9/market_state.py`
- Create `research/cloud_10coin_backtest/tests/test_g9_market_state.py`

**RED:** synthetic causal bars must produce deterministic regime/volatility/directional-efficiency/structure outputs; changing future bars must not change an already-closed snapshot; stale optional derivative/flow fields must become UNKNOWN rather than forward-filled.

**GREEN:** implement causal feature/state builder using only data timestamped at or before snapshot event time. Reuse G7/G8 regime/structure primitives where contracts match.

**Regression:** targeted + all research tests.

## Task 3 — Append-only live experience memory and delayed outcomes

**Files:**
- Create `research/cloud_10coin_backtest/g9/experience.py`
- Create `research/cloud_10coin_backtest/tests/test_g9_experience.py`

**RED:** append-only observations cannot expose TP/SL/MFE/MAE outcome fields before horizon close; later maturation appends a linked outcome record rather than rewriting history.

**GREEN:** JSONL append-only observation/outcome store with stable IDs, schema versioning and atomic append/fsync semantics.

**Regression:** targeted + all research tests.

## Task 4 — Learning Supervisor

**Files:**
- Create `research/cloud_10coin_backtest/g9/supervisor.py`
- Create `research/cloud_10coin_backtest/tests/test_g9_supervisor.py`

**RED:** deterministic fixtures must classify bottlenecks such as unstable folds, poor calibration, cost fragility, weak sample size, regime confusion and high disagreement.

**GREEN:** implement priority-ordered bottleneck diagnosis and research-budget allocation. No LLM free-form mutation is allowed in promotion-critical state; outputs are structured reason codes and bounded dimensions.

**Regression:** targeted + all research tests.

## Task 5 — Bounded hypothesis factory and failure memory

**Files:**
- Create `research/cloud_10coin_backtest/g9/hypothesis.py`
- Create `research/cloud_10coin_backtest/tests/test_g9_hypothesis.py`

**RED:** same parent + same mutation must hash identically; failure memory must block equivalent rejected hypotheses; one child changes only bounded approved dimensions; budget is hard capped.

**GREEN:** implement stable content hashing, parent/provenance lineage, approved mutation dimensions and failure-memory dedupe. Bridge generated candidates into existing G8 candidate/evaluator contracts rather than replacing G8 validation.

**Regression:** targeted + all research tests.

## Task 6 — Stable research-evidence manifest and harmonization adapter

**Files:**
- Create `research/cloud_10coin_backtest/g9/manifest.py`
- Create `research/cloud_10coin_backtest/tests/test_g9_manifest.py`
- Create `AI_SKILL_LIBRARY/v4/tools/validate_g9_trading_evidence.py`
- Create `AI_SKILL_LIBRARY/tests/test_g9_trading_evidence.py`

**RED:** manifest must contain source SHA, snapshot hash, evidence epochs, per-coin profile hashes, research-only marker, authority declaration and compatibility metadata. Any manifest claiming production execution authority must fail validation.

**GREEN:** build deterministic immutable manifest from G8/G9 promoted research evidence and run it through existing Brain V4 validation/harmonization conventions.

**Regression:** G9 tests + `AI_SKILL_LIBRARY/v4/tools/ci_validate.py` + existing G8 Brain snapshot tests.

## Task 7 — Minute worker with single-leader/overlap guard and health

**Files:**
- Create `research/cloud_10coin_backtest/g9_runtime/__init__.py`
- Create `research/cloud_10coin_backtest/g9_runtime/worker.py`
- Create `research/cloud_10coin_backtest/g9_runtime/app.py`
- Create `research/cloud_10coin_backtest/tests/test_g9_worker.py`
- Create `research/cloud_10coin_backtest/g9_runtime/railway.json` or runtime config appropriate to existing Railway service conventions after repository inspection.

**RED:** overlapping ticks are skipped; tick sequence is monotonic; provider failures trip a bounded circuit-breaker/backoff; health exposes last successful tick/source SHA/snapshot age; no order/account-write adapter exists.

**GREEN:** implement a read-only minute loop with injectable public-data provider interface, persistent lease/state file or external lock contract, bounded tick runtime and HTTP health/readiness endpoints.

**Regression:** targeted + all research tests.

## Task 8 — Trading evidence resolver

**Files:**
- Create `research/cloud_10coin_backtest/g9/evidence_resolver.py`
- Create `research/cloud_10coin_backtest/tests/test_g9_evidence_resolver.py`
- Update only the research-safe evidence-loading portion of `crypto-research-gateway`/Brain adapter after exact path inspection; do not modify order/account mutation paths.

**RED:** resolver selects newest valid immutable evidence, rejects stale/invalid/authority-escalating manifests, differentiates OOS WR vs model confidence vs live quality score, and falls back to previous verified evidence.

**GREEN:** implement read-only resolver and adapter so future trading analysis can consume G9 evidence without changing canonical Skill Gateway routing authority.

**Regression:** Python tests + gateway tests/typecheck/build + Cloudflare dry-run CI.

## Task 9 — G9 CI and safe cloud packaging

**Files:**
- Create `.github/workflows/g9-dev-ci.yml`
- Create `.github/workflows/g9-research-evidence.yml`
- Update research runtime packaging files only as required.

**RED/Preflight:** CI initially runs contracts and fails while modules are absent; later GREEN requires targeted G9, full research regression, Brain V4 validators, gateway behavior/typecheck/build and Cloudflare Wrangler dry run where affected.

**GREEN:** wire branch CI and a bounded evidence-generation workflow. GitHub remains hourly-or-slower research promotion; minute scheduling is not delegated to Actions.

## Task 10 — Dedicated Railway research deployment and first real minute tick

**Actions:**
1. Discover current Railway project/service runtime contract.
2. Create or reuse a **research-only** service separate from `crypto-research-gateway-prod`; suggested name `crypto-brain-minute-research`.
3. Set root/start command to G9 runtime.
4. Expose source SHA and health endpoints.
5. Run first real read-only minute ticks.
6. Verify no write-capable trading credentials/actions are required.
7. Confirm repeated minute ticks, non-overlap and snapshot freshness.

**Do not modify:** production service `crypto-research-gateway-prod` or production BTC StateFlow execution authority.

## Task 11 — Cloudflare stable-evidence integration verification

Reuse existing `cloudflare-research-runtime-ci.yml`, `deploy-cloudflare-worker.yml` and Skill Gateway exact-SHA validation. Add only the minimum stable evidence loading/caching path needed. Production deployment remains exact-main and is not triggered from the research branch.

Verify that Cloudflare consumes validated manifests/snapshots and cannot turn G9 research evidence into execution authority.

## Task 12 — End-to-end verification

Run:
- targeted G9 tests
- full research regression
- G8 tests
- Brain V4 validators
- crypto gateway tests/typecheck/build
- Cloudflare Worker check/dry run
- Railway minute-service health and multiple real ticks

Record exact source SHA, active research service, first/last successful tick, evidence manifest hash and any remaining deployment limitation.

**Completion rule:** Do not claim the system is continuously learning every minute until the Railway minute worker is actually deployed and multiple sequential ticks have been observed. Do not claim improved win rate until OOS evidence demonstrates it.
