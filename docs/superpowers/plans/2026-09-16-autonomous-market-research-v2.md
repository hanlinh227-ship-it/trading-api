# Autonomous Market Research V2 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a zero-local autonomous multi-market research pipeline so a short request can be converted into validated market evidence, candidates, cross-market ranking, and chart context without manual provider/timeframe selection.

**Architecture:** Extend the existing `crypto-research-gateway` research lane on top of PR #383. Add typed observation, planning, candidate-building, and HTTP orchestration modules while reusing the existing crypto provider runtime, data contract, `rankOpportunities()`, and research-only authority boundaries. External connector observations are validated evidence only; they are never execution authority.

**Tech Stack:** TypeScript 6, Node 22+, Fastify 5, Zod 4, Vitest 5, existing GitHub Actions/Brain validators.

**Spec:** `docs/superpowers/specs/2026-09-16-autonomous-market-research-v2-design.md`

## Global Constraints

- One global router only: `AI_SKILL_LIBRARY/v4/stable/router.yaml`.
- Primary Trading skill remains `multi_market_analysis`.
- Zero-local user operation remains mandatory.
- Production execution authority remains BTCUSDT Linear Perpetual/Bybit only.
- All new multi-market capability is research-only and cannot grant order permission.
- No TradingView scraping or paid TradingView dependency.
- Unknown/stale/conflicting market evidence fails closed.
- External connector credentials are never assumed available inside Railway.

---

### Task 1: Autonomous planning and normalized observation contracts

**Files:**
- Create: `crypto-research-gateway/src/intelligence/autonomous-scan.ts`
- Create: `crypto-research-gateway/test/autonomous-scan.test.ts`

**Interfaces:**
- Produces `AutonomousResearchRequest`, `NormalizedMarketObservation`, `TimeframePlan`, `CoverageRecord`, `buildTimeframePlan()`, `validateObservationSemantics()`, and `groupObservations()`.
- Consumes `MarketDomain`, `ResearchFreshness`, `VerifiedChartMapping` from `multi-market.ts`.

- [ ] **Step 1: Write failing tests**

Test default all-domain scope, deterministic timeframe plan, valid OHLC acceptance, malformed OHLC rejection, inverted bid/ask rejection, and grouping by domain/symbol.

```ts
it('builds the autonomous default timeframe plan', () => {
  expect(buildTimeframePlan()).toEqual({ context: '1h', entry: '15m', fast: '5m' });
});

it('rejects impossible OHLC geometry', () => {
  expect(validateObservationSemantics(obs({ high: 99, open: 100 }))).toContain('INVALID_OHLC');
});
```

- [ ] **Step 2: Run RED verification**

Run: `cd crypto-research-gateway && npm test -- autonomous-scan.test.ts`

Expected: FAIL because `../src/intelligence/autonomous-scan.js` does not exist.

- [ ] **Step 3: Implement minimal contracts/planner**

Implement typed records, deterministic timeframe planner, semantic validation, and grouping only. Do not build trading candidates yet.

- [ ] **Step 4: Run GREEN verification**

Run: `cd crypto-research-gateway && npm test -- autonomous-scan.test.ts`

Expected: PASS.

- [ ] **Step 5: Commit**

`git commit -m "feat: add autonomous market research contracts"`

---

### Task 2: Research-only candidate builder

**Files:**
- Modify: `crypto-research-gateway/src/intelligence/autonomous-scan.ts`
- Modify: `crypto-research-gateway/test/autonomous-scan.test.ts`

**Interfaces:**
- Produces `buildCandidateFromObservations(domain, symbol, observations)` and `buildCandidatesFromObservations(observations)`.
- Returns existing `OpportunityCandidate` values or explicit blocked reasons.
- Reuses `getMarketProfile()` and existing challenge/ranking semantics.

- [ ] **Step 1: Add failing candidate tests**

Cover: bullish sequence -> LONG candidate, bearish sequence -> SHORT candidate, ambiguous structure -> blocked, stale observation -> blocked, missing minimum evidence -> blocked, invalidation derived from structure.

```ts
it('builds a LONG research candidate from fresh rising structure', () => {
  const result = buildCandidateFromObservations('forex', 'EURUSD', risingBars());
  expect(result.candidate?.direction).toBe('LONG');
  expect(result.candidate?.freshness).toBe('FRESH');
  expect(result.candidate?.invalidation).toContain('structure');
});
```

- [ ] **Step 2: Run RED verification**

Expected: FAIL because candidate builder exports do not exist.

- [ ] **Step 3: Implement minimum explainable builder**

Use only observed price structure/current-location/freshness and bounded context evidence. Do not make indicators sole entry authority. Require at least three same-timeframe observations for a domain/symbol. Build aligned/opposing evidence explicitly; return a blocked reason when direction is ambiguous.

- [ ] **Step 4: Run GREEN + regression**

Run:
- `npm test -- autonomous-scan.test.ts`
- `npm test -- multi-market-intelligence.test.ts`

Expected: PASS.

- [ ] **Step 5: Commit**

`git commit -m "feat: build research candidates from market evidence"`

---

### Task 3: Autonomous HTTP orchestration

**Files:**
- Modify: `crypto-research-gateway/src/server.ts`
- Create: `crypto-research-gateway/test/autonomous-scan-http.test.ts`

**Interfaces:**
- Adds `POST /research/autoscan`.
- Request: `{ intent?, requestedDomains?, symbols?, externalObservations?, maxResults? }` strict schema.
- Response capability: `autonomous_multi_market_research`.
- Uses `resolveMarketScope()`, autonomous observation utilities, candidate builder, and `rankOpportunities()`.

- [ ] **Step 1: Write failing HTTP tests**

Cover: strict rejection of `placeOrder`, research-only flags, coverage gaps, TOP_SETUP with valid observations, NO_TRADE with stale/insufficient observations, `dataContract.kind=autonomous_multi_market_research`.

```ts
it('rejects order directives on autoscan', async () => {
  const response = await app.inject({ method: 'POST', url: '/research/autoscan', payload: { placeOrder: true } });
  expect(response.statusCode).toBe(400);
});
```

- [ ] **Step 2: Run RED verification**

Expected: endpoint returns 404 and tests fail for missing behavior.

- [ ] **Step 3: Implement endpoint**

Validate request with strict Zod schemas. For V2, external observations are the typed connector plane; the existing gateway-native crypto runtime remains separately available and must not be duplicated. Build coverage, candidates, ranking, max-results truncation, and data envelope. Missing requested domains must be reported as coverage gaps and never silently ranked.

- [ ] **Step 4: Run GREEN + full gateway tests**

Run:
- `npm test -- autonomous-scan-http.test.ts`
- `npm test`
- `npm run typecheck`
- `npm run build`

Expected: PASS.

- [ ] **Step 5: Commit**

`git commit -m "feat: add autonomous multi-market research endpoint"`

---

### Task 4: Natural-language skill contract and chart-navigation hardening

**Files:**
- Modify: `AI_SKILL_LIBRARY/skills/catalog.yaml`
- Modify: `crypto-research-gateway/src/intelligence/multi-market.ts`
- Modify: `crypto-research-gateway/test/multi-market-intelligence.test.ts`

**Interfaces:**
- Strengthens existing `multi_market_analysis`; no new primary skill.
- Adds common autonomous intent triggers to the existing skill.
- Adds non-authoritative chart navigation hint while preserving `mappingStatus=UNVERIFIED` for unknown mappings.

- [ ] **Step 1: Write failing chart/skill regression tests**

Add tests showing verified mappings remain verified and unknown mappings remain unverified while a safe search/navigation hint may be produced. Add Brain validation expectation that canonical skill count does not increase.

- [ ] **Step 2: Run RED verification**

Expected: tests fail because navigation hint/intent contract is not present.

- [ ] **Step 3: Implement minimal hardening**

Update `multi_market_analysis` triggers/output contract in place; do not add a skill/router/provider authority. Extend chart context with an optional safe navigation/search hint that does not assert an exchange symbol mapping.

- [ ] **Step 4: Run complete verification**

Run:
- `cd crypto-research-gateway && npm test`
- `npm run typecheck`
- `npm run build`
- repository Brain validator workflow / `AI_SKILL_LIBRARY/v4/tools/ci_validate.py --source-sha <head>` in CI
- existing Bybit bridge safety tests
- existing Worker/Wrangler dry-run workflows

Expected: all PASS, canonical skill count unchanged, no execution-authority widening.

- [ ] **Step 5: Commit and open PR**

Open a PR against `feat/harmonized-multi-market-intelligence` first so the autonomous delta is reviewable independently. After PR #383 lands, retarget to `main` and require exact-head CI before merge.

---

### Task 5: Merge/deploy gates

**Files:** none unless CI reveals a defect.

- [ ] **Step 1: Verify PR diff and reviews**

Confirm no credential files, no order placement code, no Bybit live-switch changes, no second router/provider registry.

- [ ] **Step 2: Require exact-head successful CI**

Verify gateway tests, typecheck, build, Brain validator, Bybit safety, zero-local runtime, and Worker bundle/dry-run are green for the exact PR head.

- [ ] **Step 3: Merge dependency PR #383 if still open**

Use expected-head SHA protection. Verify new `main` SHA.

- [ ] **Step 4: Retarget/merge autonomous PR after dependency is on main**

Require fresh exact-head checks after retarget/rebase/merge-base change.

- [ ] **Step 5: Railway production rollout only from exact verified main**

Set `DEPLOYMENT_SOURCE_SHA` to the exact merged main commit and deploy existing `crypto-research-gateway-prod` through the Railway connector. Do not create a replacement service.

- [ ] **Step 6: Post-deploy verification**

Require Railway deployment metadata `SUCCESS` with matching source commit and public `/health` matching `deploymentSourceSha` / `deploymentCommitSha`. Only then call the research capability LIVE. BTC execution authority remains unchanged.
