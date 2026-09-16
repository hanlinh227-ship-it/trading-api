# Live Multi-Market Data Fabric V3 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Extend Autonomous Market Research V2 into an entitlement-aware, provider-agnostic live multi-market research fabric that can ingest gateway-native crypto evidence and connector-plane Forex/Futures/Indices/Metals/Commodities evidence, enforce domain evidence requirements, and return auditable Entry/Stop/Target research levels without expanding production execution authority beyond BTCUSDT.

**Architecture:** Keep `task_router` and `multi_market_analysis` as the only routing/research authority. Add small pure TypeScript modules under `crypto-research-gateway/src/intelligence/` for market universe, source planning, entitlement/freshness classification, current-contract validation, and research levels; evolve `POST /research/autoscan` to capability version 3 while keeping the V2 request shape backward compatible. Connector credentials stay outside Railway; Railway accepts only normalized observations and non-secret acquisition metadata.

**Tech Stack:** TypeScript 6, Node >=22, Fastify 5, Zod 4, Vitest 5, GitHub Brain V4, Railway research runtime, Cloudflare Skill Gateway.

**Spec:** `docs/superpowers/specs/2026-09-16-live-multi-market-data-fabric-v3-design.md`

## Global Constraints

- `AI_SKILL_LIBRARY/v4/stable/router.yaml` remains the sole global routing authority.
- `multi_market_analysis` remains the primary skill for broad market scans; no new primary skill or parallel router.
- Production order execution remains BTCUSDT Linear Perpetual on Bybit under `BYBIT-BTC-STATEFLOW-2.1`.
- Every non-BTC multi-market output is research-only and must never widen signed-order authority.
- Connector credentials never enter Railway, Cloudflare, logs, fixtures, provenance, or response payloads.
- A provider capability is not an entitlement; `NOT_ENTITLED`, delayed, unknown, stale, or conflicting evidence fails closed for live-current labeling.
- TradingView is presentation/navigation only and never market-data authority.
- Zero-local remains mandatory for normal user operation.
- No implicit paid fallback.
- Existing V2 request fields remain accepted by `/research/autoscan`.
- Existing Brain/Model Mesh/Image Render/Bybit safety/gateway regressions must stay green.

---

## File Structure

Create focused modules:

- `crypto-research-gateway/src/intelligence/market-universe.ts` — canonical product/symbol intents and verified provider mapping metadata.
- `crypto-research-gateway/src/intelligence/source-planner.ts` — deterministic `DataAcquisitionPlan` and coverage-gap planning.
- `crypto-research-gateway/src/intelligence/evidence-quality.ts` — delay/entitlement/freshness/session classification with deterministic clock input.
- `crypto-research-gateway/src/intelligence/contract-resolver.ts` — futures current-contract validation and expiry rules; never guesses a contract.
- `crypto-research-gateway/src/intelligence/research-levels.ts` — Entry/Stop/Target research math and entry semantics.
- `crypto-research-gateway/src/intelligence/autonomous-scan.ts` — extend existing observation type and candidate builder to consume the new quality/evidence contracts; do not absorb source-planning logic.
- `crypto-research-gateway/src/server.ts` — V3 schemas, acquisition context, response fields, and fail-closed HTTP behavior.
- `crypto-research-gateway/test/live-multi-market-v3.test.ts` — pure module RED/GREEN coverage.
- `crypto-research-gateway/test/autonomous-scan-http.test.ts` — V3 endpoint compatibility/security coverage.
- `AI_SKILL_LIBRARY/tests/test_autonomous_market_routing.py` — one-command route contract and research-only wording.
- `AI_SKILL_LIBRARY/skills/catalog.yaml` — update existing `multi_market_analysis` output contract only if needed; do not create a new skill.
- `docs/checkpoints/LIVE_MULTI_MARKET_DATA_FABRIC_V3_<DATE>.md` — production closure only after exact-main runtime verification.

---

### Task 1: Market Universe and Source Planner

**Files:**
- Create: `crypto-research-gateway/src/intelligence/market-universe.ts`
- Create: `crypto-research-gateway/src/intelligence/source-planner.ts`
- Create: `crypto-research-gateway/test/live-multi-market-v3.test.ts`

**Interfaces:**
- Produces:
  - `type MarketUniverseEntry = { domain: MarketDomain; canonicalSymbol: string; productCode?: string; instrumentType: 'spot'|'perpetual'|'forex'|'future'|'index'; mappings: Record<string, { symbol: string; verified: boolean }> }`
  - `DEFAULT_MARKET_UNIVERSE: readonly MarketUniverseEntry[]`
  - `resolveUniverse(requestedDomains?: MarketDomain[], requestedSymbols?: Partial<Record<MarketDomain,string[]>>): { entries: MarketUniverseEntry[]; unresolved: Array<{domain: MarketDomain; symbol: string; reason:'UNVERIFIED_SYMBOL'}> }`
  - `type SourceCapability = { source: string; sourceType: 'gateway'|'connector'; domains: MarketDomain[]; entitlement: 'VERIFIED_REALTIME'|'VERIFIED_DELAYED'|'UNVERIFIED'|'NOT_ENTITLED'; available: boolean }`
  - `type DataAcquisitionPlan = { requestedDomains: MarketDomain[]; resolvedDomains: MarketDomain[]; symbolsByDomain: Partial<Record<MarketDomain,string[]>>; sourcesByDomain: Partial<Record<MarketDomain,string[]>>; timeframesByDomain: Partial<Record<MarketDomain,string[]>>; requiredEvidenceByDomain: Partial<Record<MarketDomain,string[]>>; entitlementStateBySource: Record<string,string>; fallbackPolicy:'FAIL_CLOSED_CONTINUE_COVERED'; gaps:Array<{domain:MarketDomain;reason:string}>; researchOnly:true; productionExecutionAuthority:false }`
  - `buildDataAcquisitionPlan(...)`

- [ ] **Step 1: Write failing universe/source-plan tests**

```ts
it('plans all six domains for a broad scan without inventing provider coverage', () => {
  const plan = buildDataAcquisitionPlan({
    capabilities: [
      { source: 'crypto-gateway', sourceType: 'gateway', domains: ['crypto'], entitlement: 'VERIFIED_REALTIME', available: true },
      { source: 'massive', sourceType: 'connector', domains: ['forex','futures','indices','metals','commodities'], entitlement: 'NOT_ENTITLED', available: true },
    ],
  });
  expect(plan.requestedDomains).toEqual(['crypto','forex','futures','indices','metals','commodities']);
  expect(plan.sourcesByDomain.crypto).toEqual(['crypto-gateway']);
  expect(plan.gaps).toEqual(expect.arrayContaining([
    { domain: 'forex', reason: 'NO_ENTITLED_SOURCE' },
    { domain: 'futures', reason: 'NO_ENTITLED_SOURCE' },
  ]));
  expect(plan.productionExecutionAuthority).toBe(false);
});

it('never guesses an unknown requested symbol', () => {
  const resolved = resolveUniverse(['futures'], { futures: ['MADEUP'] });
  expect(resolved.entries).toEqual([]);
  expect(resolved.unresolved).toEqual([{ domain: 'futures', symbol: 'MADEUP', reason: 'UNVERIFIED_SYMBOL' }]);
});
```

- [ ] **Step 2: Run RED**

Run:
```bash
cd crypto-research-gateway && npm test -- live-multi-market-v3.test.ts
```
Expected: FAIL because `market-universe.js` / `source-planner.js` do not exist.

- [ ] **Step 3: Implement minimal universe and source planner**

Use only verified intent-level entries from the spec. Futures/metals/commodities entries use product codes (`ES`,`NQ`,`YM`,`RTY`,`GC`,`SI`,`HG`,`CL`,`NG`) without permanently dated contracts. Provider mapping is marked verified only when explicitly encoded or resolved later.

- [ ] **Step 4: Run GREEN plus typecheck**

```bash
cd crypto-research-gateway
npm test -- live-multi-market-v3.test.ts
npm run typecheck
```
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add crypto-research-gateway/src/intelligence/market-universe.ts crypto-research-gateway/src/intelligence/source-planner.ts crypto-research-gateway/test/live-multi-market-v3.test.ts
git commit -m "feat: add multi-market universe and source planner"
```

---

### Task 2: Entitlement, Freshness, and Session-Aware Evidence Quality

**Files:**
- Create: `crypto-research-gateway/src/intelligence/evidence-quality.ts`
- Modify: `crypto-research-gateway/src/intelligence/autonomous-scan.ts`
- Modify: `crypto-research-gateway/test/live-multi-market-v3.test.ts`
- Modify: `crypto-research-gateway/test/autonomous-scan.test.ts`

**Interfaces:**
- Extends `NormalizedMarketObservation` with optional:
  - `latencyMs?: number`
  - `delayClass?: 'REALTIME'|'DELAYED'|'UNKNOWN'`
  - `entitlement?: 'VERIFIED_REALTIME'|'VERIFIED_DELAYED'|'UNVERIFIED'`
  - `instrumentType?: 'spot'|'perpetual'|'forex'|'future'|'index'`
  - `providerSymbol?: string`
  - `canonicalSymbol?: string`
  - `contractExpiry?: string`
  - `evidenceKind?: 'quote'|'snapshot'|'bar'|'trade'|'session'|'context'`
- Produces:
  - `classifyEvidenceQuality(observation, { nowMs, maxAgeMs, clockSkewMs }): { liveEligible:boolean; state:'LIVE_REALTIME'|'DELAYED_CONTEXT'|'STALE'|'UNKNOWN'|'INVALID'; reasons:string[] }`

- [ ] **Step 1: Add failing quality tests**

```ts
it('blocks delayed evidence from live eligibility even when event time is recent', () => {
  const q = classifyEvidenceQuality(obs({
    entitlement: 'VERIFIED_DELAYED', delayClass: 'DELAYED', eventTime: '2026-09-16T12:00:00.000Z', ingestTime: '2026-09-16T12:00:01.000Z',
  }), { nowMs: Date.parse('2026-09-16T12:00:02.000Z'), maxAgeMs: 10_000, clockSkewMs: 2_000 });
  expect(q.liveEligible).toBe(false);
  expect(q.state).toBe('DELAYED_CONTEXT');
});

it('rejects future event timestamps beyond skew tolerance', () => {
  const q = classifyEvidenceQuality(obs({ eventTime: '2026-09-16T12:01:00.000Z', ingestTime: '2026-09-16T12:01:01.000Z', entitlement: 'VERIFIED_REALTIME', delayClass: 'REALTIME' }),
    { nowMs: Date.parse('2026-09-16T12:00:00.000Z'), maxAgeMs: 10_000, clockSkewMs: 2_000 });
  expect(q.state).toBe('INVALID');
  expect(q.reasons).toContain('EVENT_TIME_IN_FUTURE');
});
```

- [ ] **Step 2: Run RED**

```bash
cd crypto-research-gateway && npm test -- live-multi-market-v3.test.ts autonomous-scan.test.ts
```
Expected: FAIL because quality module/fields are missing.

- [ ] **Step 3: Implement deterministic quality classifier**

Requirements:
- no `Date.now()` inside pure classifier;
- entitlement is independent from HTTP recency;
- `ingestTime < eventTime - clockSkewMs` => INVALID;
- `VERIFIED_DELAYED` => context-only;
- `UNVERIFIED`/missing entitlement on connector evidence => not live-eligible;
- preserve V2 backward compatibility by treating legacy gateway crypto observations under existing freshness semantics only inside the compatibility path, not by upgrading connector data to verified real-time.

- [ ] **Step 4: Run GREEN**

```bash
cd crypto-research-gateway
npm test -- live-multi-market-v3.test.ts autonomous-scan.test.ts
npm run typecheck
```
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add crypto-research-gateway/src/intelligence/evidence-quality.ts crypto-research-gateway/src/intelligence/autonomous-scan.ts crypto-research-gateway/test/live-multi-market-v3.test.ts crypto-research-gateway/test/autonomous-scan.test.ts
git commit -m "feat: enforce entitlement-aware evidence quality"
```

---

### Task 3: Futures Current-Contract Resolver

**Files:**
- Create: `crypto-research-gateway/src/intelligence/contract-resolver.ts`
- Modify: `crypto-research-gateway/test/live-multi-market-v3.test.ts`

**Interfaces:**
- Produces:
  - `type ContractCandidate = { productCode:string; ticker:string; expiry:string; active:boolean; entitlement:'VERIFIED_REALTIME'|'VERIFIED_DELAYED'|'UNVERIFIED' }`
  - `resolveCurrentContract(productCode:string, candidates:ContractCandidate[], nowMs:number): { status:'RESOLVED'; contract:ContractCandidate } | { status:'BLOCKED'; reason:'CONTRACT_UNRESOLVED'|'CONTRACT_EXPIRED' }`

- [ ] **Step 1: Add failing resolver tests**

```ts
it('selects the nearest active non-expired verified contract', () => {
  const r = resolveCurrentContract('NQ', [
    { productCode:'NQ', ticker:'NQU26', expiry:'2026-09-18T21:00:00Z', active:true, entitlement:'VERIFIED_REALTIME' },
    { productCode:'NQ', ticker:'NQZ26', expiry:'2026-12-18T21:00:00Z', active:true, entitlement:'VERIFIED_REALTIME' },
  ], Date.parse('2026-09-16T12:00:00Z'));
  expect(r.status).toBe('RESOLVED');
  if (r.status === 'RESOLVED') expect(r.contract.ticker).toBe('NQU26');
});

it('blocks rather than guessing when no valid contract exists', () => {
  expect(resolveCurrentContract('GC', [], Date.parse('2026-09-16T12:00:00Z'))).toEqual({ status:'BLOCKED', reason:'CONTRACT_UNRESOLVED' });
});
```

- [ ] **Step 2: Run RED**

```bash
cd crypto-research-gateway && npm test -- live-multi-market-v3.test.ts
```
Expected: FAIL missing resolver.

- [ ] **Step 3: Implement resolver**

Sort valid same-product active contracts by expiry ascending. Never synthesize ticker strings. Reject expired candidates. Do not select `VERIFIED_DELAYED` or `UNVERIFIED` as a live-current contract; they may remain context metadata outside this resolver.

- [ ] **Step 4: Run GREEN/typecheck**

```bash
cd crypto-research-gateway
npm test -- live-multi-market-v3.test.ts
npm run typecheck
```
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add crypto-research-gateway/src/intelligence/contract-resolver.ts crypto-research-gateway/test/live-multi-market-v3.test.ts
git commit -m "feat: add verified futures contract resolver"
```

---

### Task 4: Domain Evidence Profiles and Multi-Timeframe Enforcement

**Files:**
- Modify: `crypto-research-gateway/src/intelligence/autonomous-scan.ts`
- Modify: `crypto-research-gateway/src/intelligence/multi-market.ts`
- Modify: `crypto-research-gateway/test/autonomous-scan.test.ts`
- Modify: `crypto-research-gateway/test/live-multi-market-v3.test.ts`

**Interfaces:**
- Produces `evaluateDomainEvidence(domain, observations, nowMs): { eligible:boolean; reasons:string[]; selected:NormalizedMarketObservation[]; qualitySummary:Record<string,number> }`
- Candidate builder consumes this evaluator before direction scoring.

- [ ] **Step 1: Add RED tests for profile enforcement**

```ts
it('does not treat three 15m bars as forex context confirmation', () => {
  const bars = risingBars().map(x => ({ ...x, timeframe:'15m', session:'london', entitlement:'VERIFIED_REALTIME' as const, delayClass:'REALTIME' as const }));
  const result = buildCandidateFromObservations('forex','EURUSD',bars);
  expect(result.candidate).toBeUndefined();
  expect(result.blockedReasons).toContain('MISSING_CONTEXT_TIMEFRAME');
});

it('requires current contract evidence for futures', () => {
  const result = evaluateDomainEvidence('futures', /* valid bars without contract metadata */, Date.parse('2026-09-16T12:00:00Z'));
  expect(result.eligible).toBe(false);
  expect(result.reasons).toContain('CONTRACT_UNRESOLVED');
});
```

Use concrete fixture objects rather than comments in the actual test file.

- [ ] **Step 2: Run RED**

```bash
cd crypto-research-gateway && npm test -- autonomous-scan.test.ts live-multi-market-v3.test.ts
```
Expected: FAIL because V2 builder currently accepts single-timeframe structure.

- [ ] **Step 3: Implement profile enforcement**

Rules from spec become executable checks. `1h` context + `15m` entry are distinct. `5m` is optional refinement. For indices/metals/commodities, context evidence must be explicit; absence blocks live ranking instead of being silently scored neutral.

- [ ] **Step 4: Run GREEN/full gateway tests**

```bash
cd crypto-research-gateway
npm test
npm run typecheck
npm run build
```
Expected: all gateway tests PASS.

- [ ] **Step 5: Commit**

```bash
git add crypto-research-gateway/src/intelligence/autonomous-scan.ts crypto-research-gateway/src/intelligence/multi-market.ts crypto-research-gateway/test/autonomous-scan.test.ts crypto-research-gateway/test/live-multi-market-v3.test.ts
git commit -m "feat: enforce domain evidence profiles"
```

---

### Task 5: Entry / Stop / Target Research Levels

**Files:**
- Create: `crypto-research-gateway/src/intelligence/research-levels.ts`
- Modify: `crypto-research-gateway/src/intelligence/autonomous-scan.ts`
- Modify: `crypto-research-gateway/test/live-multi-market-v3.test.ts`

**Interfaces:**
- Produces:
  - `type ResearchLevels = { entry:number; entrySemantic:'EXECUTABLE_ASK'|'EXECUTABLE_BID'|'REFERENCE_CLOSE'; stop:number; target:number; riskReward:number; invalidationBasis:string; researchOnly:true }`
  - `buildResearchLevels({ direction, observations, structuralStop, riskReward }): { levels?:ResearchLevels; blockedReason?:string }`

- [ ] **Step 1: Add RED math/semantic tests**

```ts
it('uses verified realtime ask for LONG research entry', () => {
  const out = buildResearchLevels({ direction:'LONG', observations:risingBarsV3(), structuralStop:1.18, riskReward:2 });
  expect(out.levels?.entrySemantic).toBe('EXECUTABLE_ASK');
  expect(out.levels?.target).toBeCloseTo(out.levels!.entry + (out.levels!.entry - 1.18) * 2, 8);
  expect(out.levels?.researchOnly).toBe(true);
});

it('uses verified realtime bid for SHORT research entry', () => {
  const out = buildResearchLevels({ direction:'SHORT', observations:fallingBarsV3(), structuralStop:1.19, riskReward:2 });
  expect(out.levels?.entrySemantic).toBe('EXECUTABLE_BID');
});

it('labels close-only levels as non-executable reference', () => {
  const out = buildResearchLevels({ direction:'LONG', observations:risingBarsV3().map(({bid,ask,...x}) => x), structuralStop:1.18, riskReward:2 });
  expect(out.levels?.entrySemantic).toBe('REFERENCE_CLOSE');
});
```

- [ ] **Step 2: Run RED**

```bash
cd crypto-research-gateway && npm test -- live-multi-market-v3.test.ts
```
Expected: FAIL missing level builder.

- [ ] **Step 3: Implement level builder**

Only use bid/ask as executable semantics when observation quality is verified real-time. Ensure risk > 0 and all outputs finite. Otherwise return `INVALID_RISK_GEOMETRY`. Every output remains `researchOnly:true`.

- [ ] **Step 4: Run GREEN**

```bash
cd crypto-research-gateway
npm test -- live-multi-market-v3.test.ts autonomous-scan.test.ts
npm run typecheck
```
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add crypto-research-gateway/src/intelligence/research-levels.ts crypto-research-gateway/src/intelligence/autonomous-scan.ts crypto-research-gateway/test/live-multi-market-v3.test.ts
git commit -m "feat: add research entry stop target levels"
```

---

### Task 6: Autoscan V3 HTTP Contract

**Files:**
- Modify: `crypto-research-gateway/src/server.ts`
- Modify: `crypto-research-gateway/test/autonomous-scan-http.test.ts`
- Modify: `crypto-research-gateway/test/live-multi-market-v3.test.ts`

**Interfaces:**
- Request remains V2-compatible and adds optional `acquisitionContext` containing only non-secret capability/entitlement metadata.
- Response adds `capabilityVersion:3`, `dataAcquisitionPlan`, `sourceCoverage`, `entitlementSummary`, and levels on eligible ranked candidates.

- [ ] **Step 1: Add failing HTTP tests**

```ts
it('returns capabilityVersion 3 and source gaps without fabricating connector calls', async () => {
  const res = await app.inject({ method:'POST', url:'/research/autoscan', payload:{ intent:'quét đa thị trường', acquisitionContext:{ sources:[{ source:'massive', sourceType:'connector', domains:['forex'], entitlement:'NOT_ENTITLED', available:true }] } } });
  expect(res.statusCode).toBe(200);
  const body = res.json();
  expect(body.capabilityVersion).toBe(3);
  expect(body.dataAcquisitionPlan.gaps).toEqual(expect.arrayContaining([{ domain:'forex', reason:'NO_ENTITLED_SOURCE' }]));
});

it.each(['apiKey','token','quantity','leverage','placeOrder'])('rejects forbidden autoscan field %s', async (field) => {
  const res = await app.inject({ method:'POST', url:'/research/autoscan', payload:{ [field]:'x' } });
  expect(res.statusCode).toBe(400);
});
```

- [ ] **Step 2: Run RED**

```bash
cd crypto-research-gateway && npm test -- autonomous-scan-http.test.ts live-multi-market-v3.test.ts
```
Expected: FAIL on missing V3 fields/context schema.

- [ ] **Step 3: Implement strict V3 schemas and response assembly**

Do not add provider SDK calls to `server.ts`. It receives only normalized evidence and sanitized acquisition metadata. Preserve V2 external observations. Coverage gaps are explicit and do not crash covered domains.

- [ ] **Step 4: Run full gateway suite**

```bash
cd crypto-research-gateway
npm test
npm run typecheck
npm run build
```
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add crypto-research-gateway/src/server.ts crypto-research-gateway/test/autonomous-scan-http.test.ts crypto-research-gateway/test/live-multi-market-v3.test.ts
git commit -m "feat: evolve autoscan to capability v3"
```

---

### Task 7: One-Command Brain Orchestration Contract

**Files:**
- Modify: `AI_SKILL_LIBRARY/skills/catalog.yaml`
- Modify: `AI_SKILL_LIBRARY/tests/test_autonomous_market_routing.py`
- Inspect/update only if necessary: the existing execution capsule for `multi_market_analysis` resolved by the V4 compiler.

**Interfaces:**
- Existing skill ID remains `multi_market_analysis`.
- Existing trigger ownership remains with that skill.
- Output/capsule contract must state: resolve universe, acquire approved gateway/connector evidence using available tools, preserve entitlement labels, call V3 research path, return TOP_SETUP/NO_TRADE, and never widen execution authority.

- [ ] **Step 1: Add RED routing/contract assertions**

```py
def test_multi_market_analysis_contract_requires_live_source_planning_without_execution_widening():
    skill = catalog_by_id()["multi_market_analysis"]
    contract = skill["output_contract"].lower()
    assert "source" in contract
    assert "entitlement" in contract
    assert "top_setup" in contract
    assert "no_trade" in contract
    assert "production execution" in contract or "execution authority" in contract
```

Also retain exact routing assertions for `tìm lệnh`, `quét market`, and `quét đa thị trường`.

- [ ] **Step 2: Run RED**

```bash
python AI_SKILL_LIBRARY/tests/test_autonomous_market_routing.py
```
Expected: FAIL only if V3 orchestration wording/trigger is absent; existing route ownership must not regress.

- [ ] **Step 3: Update existing skill contract minimally**

Do not create a new skill or router. Keep connector/tool providers as evidence only. Explicitly require `NOT_ENTITLED`/delayed/unknown to become coverage gaps/context-only.

- [ ] **Step 4: Run Brain validators/regressions**

```bash
python AI_SKILL_LIBRARY/v4/tools/ci_validate.py --source-sha $(git rev-parse HEAD)
python AI_SKILL_LIBRARY/tests/test_autonomous_market_routing.py
```
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add AI_SKILL_LIBRARY/skills/catalog.yaml AI_SKILL_LIBRARY/tests/test_autonomous_market_routing.py
git commit -m "feat: route one-command scans through live source fabric"
```

---

### Task 8: Security and BTC Execution Authority Regression

**Files:**
- Modify only tests unless a regression is found:
  - `crypto-research-gateway/test/live-multi-market-v3.test.ts`
  - existing Cloudflare Bybit authority regression test file(s)

**Interfaces:**
- No new execution interface.
- Existing signed writer must continue rejecting every symbol except BTCUSDT.

- [ ] **Step 1: Add/retain explicit non-BTC authority assertion**

Test that a ranked `NQ`, `EURUSD`, `GC`, or non-BTC crypto candidate can contain research levels but does not expose order permission and cannot pass the signed Bybit writer authority guard.

- [ ] **Step 2: Run targeted safety tests**

```bash
cd crypto-research-gateway && npm test
cd ../cloudflare-worker && npm run check
```
Expected: all existing BTC-only authority validators and Worker safety tests PASS.

- [ ] **Step 3: Fix only if a real regression is found**

Any failure widening non-BTC execution is a blocker; repair at the narrowest guard layer and add a regression reproducer before implementation.

- [ ] **Step 4: Run all targeted suites again**

Expected: PASS.

- [ ] **Step 5: Commit test-only hardening if changed**

```bash
git add crypto-research-gateway/test cloudflare-worker
git commit -m "test: lock multi-market research behind BTC execution authority"
```

---

### Task 9: Exact-Head CI, Review, Merge, and Runtime Rollout

**Files:**
- No feature code unless CI reveals a real defect.
- Create after production verification: `docs/checkpoints/LIVE_MULTI_MARKET_DATA_FABRIC_V3_2026-09-16.md`

**Interfaces:**
- Exact-head branch SHA is the only merge candidate.
- Exact-main merge SHA is the only production candidate.

- [ ] **Step 1: Open/update PR and verify exact-head workflows**

Required gates:
- Crypto Skill Registry Validate;
- AI Skill Library CI;
- Skill-Mandatory Fast Gateway CI;
- Cloudflare Research Runtime CI;
- Zero Local Cloud Runtime.

Every gate must be `completed/success` for the same head SHA.

- [ ] **Step 2: Review diff against spec**

Check:
- no provider credential material;
- no second router/skill authority;
- no non-BTC execution widening;
- no hard-coded permanent futures expiry;
- no entitlement upgrade from capability alone;
- V2 request compatibility retained.

- [ ] **Step 3: Merge with expected-head protection**

Merge only if `main` has not invalidated the branch; otherwise update/rebase by a conflict-safe branch workflow and rerun exact-head CI.

- [ ] **Step 4: Deploy Railway exact-main**

Set non-secret `DEPLOYMENT_SOURCE_SHA` to exact merged `main` SHA and redeploy existing `crypto-research-gateway-prod` service only. Require deployment metadata `SUCCESS` and matching commit hash.

- [ ] **Step 5: Verify Railway read-only runtime**

Require:
- `/health` exact SHA;
- `/capabilities` includes `autonomous_multi_market_research` capability V3 semantics;
- `/research/autoscan` returns V3 contract;
- unsupported/unentitled domains return explicit gaps;
- no order route is invoked.

- [ ] **Step 6: Deploy/verify Cloudflare exact-main if Brain files changed**

Require:
- `/brain/health` exact SHA;
- route matrix maps `tìm lệnh`, `quét market`, `quét đa thị trường` to `multi_market_analysis`;
- Model Mesh/FAST/SECRET/FREE_ONLY gates stay green;
- rollback skipped.

- [ ] **Step 7: Run live read-only provider smoke from available tool plane**

For each domain actually accessible by the connected tool plane, collect only read-only market evidence. If a provider returns `NOT_ENTITLED`, record that state and keep the domain gap; never fabricate PASS. A domain is `ALL_MARKETS_LIVE_READY` only when at least one approved source returns verified real-time entitlement plus fresh evidence.

- [ ] **Step 8: Write closure checkpoint and promote release only after runtime proof**

Closure document must list per-domain status as one of:
- `LIVE_REALTIME`;
- `DELAYED_CONTEXT_ONLY`;
- `NOT_ENTITLED`;
- `NO_SOURCE`;
- `BLOCKED`.

Do not mark the capability release known-good until production exact-SHA gates and honest per-domain coverage evidence are complete.

---

## Plan Self-Review

- Spec coverage: source planning, provider-agnostic architecture, universe, contract resolution, entitlement/freshness, multi-timeframe profiles, levels, V3 HTTP contract, one-command routing, credential boundary, BTC-only execution, observability/runtime rollout are each assigned to tasks.
- Placeholder scan: no implementation step relies on `TBD`/`TODO`; all blockers have explicit fail-closed outcomes.
- Type consistency: `NormalizedMarketObservation` V3 fields, `DataAcquisitionPlan`, `ContractCandidate`, and `ResearchLevels` names are stable across tasks.
- Scope: native non-crypto provider credentials/adapters are intentionally extension points, not fabricated as part of V3. The deliverable is a complete fabric plus honest operational coverage based on actual entitlements.
