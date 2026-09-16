# Harmonized Multi-Market Intelligence Implementation Plan

> **Execution discipline:** RED -> minimum GREEN -> regression suite -> Brain validator -> PR CI. Do not promote any non-BTC market to production execution authority.

**Goal:** Extend the existing Trading research lane with a provider-agnostic, research-only orchestration layer that can compare candidate opportunities across Crypto, Forex, Futures, Indices, Metals, and Commodities without creating a second router, source registry, or execution authority.

**Authority constraints:**
- `task_router` remains the sole global routing authority.
- `multi_market_analysis` is the primary Trading reasoning skill for this change; `live_data_validation` and `risk_execution` are supporting skills only.
- `docs/checkpoints/CURRENT_HANDOFF.md` and `docs/checkpoints/BYBIT_BTC_STATEFLOW_2_1_20260904.md` remain the Trading execution authority.
- BTCUSDT Bybit Linear remains the only validated production execution strategy target.
- This feature is research-only and may not place, amend, cancel, or close orders or widen financial permissions.
- Existing crypto provider/freshness/divergence/provenance primitives are reused; no parallel provider registry is introduced.

## Task 1 — Contract tests first (RED)

**Files:**
- Create: `crypto-research-gateway/test/multi-market-intelligence.test.ts`
- Create: `crypto-research-gateway/test/multi-market-http.test.ts`

**Required failing behaviors before implementation:**
1. Default scope includes exactly: `crypto`, `forex`, `futures`, `indices`, `metals`, `commodities`.
2. Domain profiles are research-only and have `productionExecutionAuthority=false`.
3. Stale/unknown evidence, material data conflicts, missing invalidation, or unresolved opposing evidence fail closed to `NO_TRADE`.
4. Candidate scores from heterogeneous domain scales normalize to `[0,100]` without domain-specific arbitrary strategy weights.
5. Ranking excludes blocked candidates and returns `NO_TRADE` when none survive.
6. Chart context never invents a TradingView/exchange mapping: an externally verified chart symbol is preserved; otherwise mapping is explicitly `UNVERIFIED`.
7. HTTP `POST /research/opportunities` returns a research-only result wrapped in the existing data-contract envelope.
8. HTTP schema rejects execution/write fields and invalid candidate contracts.

**RED proof:** Open a PR with tests only and record the failing GitHub Actions run caused by the missing intelligence module/route.

## Task 2 — Minimum GREEN intelligence core

**Files:**
- Create: `crypto-research-gateway/src/intelligence/multi-market.ts`

Implement pure deterministic functions/types only:
- `resolveMarketScope`
- `getMarketProfile`
- `challengeCandidate`
- `normalizeOpportunityScore`
- `rankOpportunities`
- `buildChartContext`

Design requirements:
- No provider calls and no order execution.
- No hidden/opaque domain scoring weights.
- Fail closed on stale/unknown evidence and conflicts.
- Preserve provenance identifiers supplied by upstream domain/source adapters.
- Return explicit reasons for every blocked candidate.
- Use a deterministic tie-break: normalized score, then confidence, then risk/reward, then stable symbol order.

## Task 3 — Research-only HTTP orchestration surface

**Files:**
- Modify: `crypto-research-gateway/src/server.ts`

Add strict `POST /research/opportunities` schema and response.
- Input is already-collected/evaluated candidate evidence; this endpoint does not pretend to fetch Forex/Futures/Metals sources that do not exist in this gateway.
- Output includes requested/resolved scope, ranked opportunities or `NO_TRADE`, blocked candidates with reasons, and chart context.
- Wrap result with the existing `buildDataEnvelope` research-only provenance contract.
- Keep all existing `/research/market` and MCP behavior unchanged.

## Task 4 — GREEN verification and regression

Run via PR CI:
- `npm test -- --reporter=verbose`
- `npm run typecheck`
- `npm run build`
- `python AI_SKILL_LIBRARY/v4/tools/ci_validate.py --source-sha <PR_HEAD_SHA> --skip-tests`
- Existing Bybit bridge safety and Cloudflare dry-run checks from `.github/workflows/cloudflare-research-runtime-ci.yml`.

Acceptance:
- New tests pass.
- Existing gateway tests pass.
- Brain validator passes.
- No live switches, credentials, execution authority, provider registry, or router authority change.

## Task 5 — Review, merge, and production boundary

Before merge:
- Inspect PR diff for permission/authority widening, secrets, duplicate router/provider logic, and accidental execution semantics.
- Require successful PR CI on exact head SHA.

After merge:
- Do **not** call the multi-market capability LIVE merely because source code merged.
- Cloudflare Skill Gateway and Railway live-research runtime remain separate authorities.
- Any Railway deployment of this endpoint requires exact-main connector deployment + runtime `/health` source-SHA verification before claiming it is deployed.
- Non-BTC markets remain research-only until separately validated and explicitly promoted through Trading authority.
