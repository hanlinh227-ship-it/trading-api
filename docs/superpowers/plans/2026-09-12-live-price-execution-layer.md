# Live-Price Execution Layer Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make future crypto market scans use venue-correct, fresh executable bid/ask prices from Bybit or Binance with fail-closed freshness, semantic, and divergence gates.

**Architecture:** Preserve generic research routing, but add a separate venue-bound execution-quote path. Provider adapters emit bid/ask/last/mark/index with endpoint-correct timestamps; an execution-quote builder selects ask for LONG and bid for SHORT, applies policy thresholds, and cross-checks only semantically equivalent observations. Bybit remains the default production execution venue under existing trading authority; Binance is a secondary reference unless explicitly requested.

**Tech Stack:** Node.js 22, TypeScript, Fastify 5, Zod 4, Vitest 5, GitHub Actions, Railway.

**Spec:** `docs/superpowers/specs/2026-09-12-live-price-execution-layer-design.md`

## Global Constraints

- Production trading authority remains `docs/checkpoints/CURRENT_HANDOFF.md`.
- Current default production route remains BTCUSDT Bybit Linear Perpetual.
- MARKET LONG uses execution-venue ask; MARKET SHORT uses execution-venue bid.
- `last`, `mark`, `index`, and `mid` must never masquerade as executable fill prices.
- Executable bid/ask freshness target is 2,000 ms; hard stale threshold is 5,000 ms.
- Contextual mark/index freshness tolerance is 10,000 ms.
- Material cross-venue divergence threshold is 30 bps unless project authority is stricter.
- Cross-venue checks require matching symbol, instrument, quote currency, and semantic.
- No silent cross-venue substitution is allowed.
- Missing/invalid source timestamps fail closed.
- Provider output remains evidence, not reasoning authority.
- No API key, secret, live-order, transfer, wallet, signing, or other HIGH_RISK capability is added.
- Zero-local runtime remains mandatory.

---

### Task 1: Checkpoint-resolved live-price policy

**Files:**
- Create: `AI_SKILL_LIBRARY/skills/registry/live_price_policy.yaml`
- Create: `tests/test_live_price_policy.py`
- Modify: `AI_SKILL_LIBRARY/checkpoint.json`
- Modify: `AI_SKILL_LIBRARY/runtime/cloud_runtime.yaml`

**Interfaces:**
- Produces checkpoint pointer `live_price_policy_path`.
- Produces policy values: default venue `bybit`, production instrument `perpetual`, freshness targets, 30 bps divergence, fail-closed, and no silent substitution.

- [ ] **Step 1: Write failing Python policy test**

Test must assert the checkpoint pointer exists and resolves, default execution venue is `bybit`, production instrument is `perpetual`, `executable_target_ms == 2000`, `executable_hard_stale_ms == 5000`, `contextual_max_age_ms == 10000`, `divergence_bps == 30`, `fail_closed == true`, and `allow_cross_venue_execution_substitution == false`.

- [ ] **Step 2: Run RED**

Run:
```bash
python -m unittest discover -s tests -p 'test_live_price_policy.py' -v
```
Expected: FAIL because the pointer/policy file does not exist.

- [ ] **Step 3: Implement minimum policy contract**

Create `live_price_policy.yaml` with explicit values and add `live_price_policy_path` to checkpoint. Add the policy path to cloud runtime metadata without changing HIGH_RISK permissions.

- [ ] **Step 4: Run GREEN and Brain validators**

Run:
```bash
python -m unittest discover -s tests -p 'test_live_price_policy.py' -v
python AI_SKILL_LIBRARY/validate_skill_registry.py
python AI_SKILL_LIBRARY/validate_brain.py
python AI_SKILL_LIBRARY/validate_router.py
python AI_SKILL_LIBRARY/validate_v4.py
python AI_SKILL_LIBRARY/validate_authority.py
```
Expected: PASS.

---

### Task 2: Venue-native bid/ask and timestamp semantics

**Files:**
- Modify: `crypto-research-gateway/test/providers.test.ts`
- Modify: `crypto-research-gateway/src/providers/bybit.ts`
- Modify: `crypto-research-gateway/src/providers/binance.ts`

**Interfaces:**
- Bybit perpetual snapshot emits `bid`, `ask`, `last`, `mark`, `index` using Bybit ticker response `time`.
- Binance perpetual snapshot emits `bid`/`ask` from USD-M bookTicker with bookTicker timestamp; `last` from ticker/price with its own timestamp; `mark`/`index` from premiumIndex with premium timestamp.

- [ ] **Step 1: Add failing provider tests**

Mock Bybit ticker response containing `bid1Price`, `ask1Price`, `lastPrice`, `markPrice`, `indexPrice`, `time`; assert all five observations and semantics.

Mock Binance three public responses: `bookTicker`, `ticker/price`, `premiumIndex`; assert bid/ask timestamps equal bookTicker time, last timestamp equals ticker time, mark/index timestamp equals premium time.

- [ ] **Step 2: Run RED**

Run:
```bash
cd crypto-research-gateway
npm test -- --run test/providers.test.ts
```
Expected: FAIL because bid/ask are absent and Binance timestamps are shared incorrectly.

- [ ] **Step 3: Implement minimum adapter changes**

Bybit: emit bid/ask before last/mark/index and fail if required values are non-positive.

Binance perpetual: fetch `GET /fapi/v1/ticker/bookTicker`, `GET /fapi/v1/ticker/price`, and `GET /fapi/v1/premiumIndex` in parallel. Build observations with endpoint-specific timestamps. Do not derive executable semantics from premiumIndex.

- [ ] **Step 4: Run GREEN**

Run:
```bash
npm test -- --run test/providers.test.ts
npm run typecheck
```
Expected: PASS.

---

### Task 3: Execution quote builder and fail-closed gates

**Files:**
- Create: `crypto-research-gateway/src/execution/execution-quote.ts`
- Create: `crypto-research-gateway/test/execution-quote.test.ts`

**Interfaces:**
```ts
export type TradeSide = 'LONG' | 'SHORT';
export type ExecutionStatus = 'OK' | 'STALE_PRICE' | 'PRICE_DIVERGENCE' | 'SEMANTIC_MISMATCH' | 'VENUE_UNAVAILABLE';
export type LivePricePolicy = {
  executableTargetMs: number;
  executableHardStaleMs: number;
  contextualMaxAgeMs: number;
  divergenceBps: number;
};
export function buildExecutionQuote(input: {
  venue: string;
  symbol: string;
  instrumentType: 'spot' | 'perpetual';
  side: TradeSide;
  observations: MarketObservation[];
  crossVenueObservations?: MarketObservation[];
  policy?: LivePricePolicy;
}): ExecutionQuote;
```

- [ ] **Step 1: Write failing execution tests**

Required tests:
- LONG selects ask and never last/mark/mid.
- SHORT selects bid and never last/mark/mid.
- stale executable observation returns `STALE_PRICE` and `executionVerified=false`.
- missing/invalid timestamp fails closed.
- crossed/invalid book returns semantic failure.
- cross-venue comparison uses ask-vs-ask for LONG and bid-vs-bid for SHORT.
- >30 bps equivalent-semantic divergence returns `PRICE_DIVERGENCE`.
- Spot/Perpetual mismatch cannot verify execution.

Use fixed deterministic timestamps in tests.

- [ ] **Step 2: Run RED**

Run:
```bash
npm test -- --run test/execution-quote.test.ts
```
Expected: FAIL because module is absent.

- [ ] **Step 3: Implement minimum quote builder**

Compute `quoteAgeMs = max(0, receivedTimestampMs - sourceTimestampMs)`, `mid=(bid+ask)/2`, and `spreadBps=((ask-bid)/mid)*10000`. Return status rather than throwing for market-quality rejection. Never average provider prices.

- [ ] **Step 4: Run GREEN and regression**

Run:
```bash
npm test -- --run test/execution-quote.test.ts
npm test
npm run typecheck
```
Expected: PASS.

---

### Task 4: Venue-bound runtime route

**Files:**
- Modify: `crypto-research-gateway/src/research.ts`
- Modify: `crypto-research-gateway/src/routing/capability-router.ts`
- Modify: `crypto-research-gateway/test/routing.test.ts`
- Create: `crypto-research-gateway/test/research-execution.test.ts`

**Interfaces:**
- Add `MarketAction = ... | 'execution_quote'`.
- Add input fields `side?: 'LONG'|'SHORT'` and `executionVenue?: 'bybit'|'binance'`.
- Execution venue resolver returns explicit venue; if absent for production-style perpetual quote, default `bybit`.
- Secondary provider may supply reference observations only; it cannot replace an unavailable execution venue.

- [ ] **Step 1: Write failing routing/runtime tests**

Assert explicit Binance execution selects Binance; default perpetual execution selects Bybit; unavailable Bybit returns `VENUE_UNAVAILABLE` even if Binance is healthy; secondary semantic mismatch is ignored/reported rather than compared incorrectly.

- [ ] **Step 2: Run RED**

Run:
```bash
npm test -- --run test/routing.test.ts test/research-execution.test.ts
```
Expected: FAIL.

- [ ] **Step 3: Implement execution-specific venue resolver and runtime path**

Keep `selectProviders()` unchanged for generic research except adding `execution_quote` to safe capability recognition if needed. Add a separate `resolveExecutionVenue()` that does not use generic provider order as execution authority. Fetch execution venue snapshot first and a single healthy alternate venue for cross-check only.

If execution venue fails or is region-restricted, return structured `VENUE_UNAVAILABLE`; do not promote alternate venue data to executable price.

- [ ] **Step 4: Run GREEN**

Run:
```bash
npm test -- --run test/routing.test.ts test/research-execution.test.ts
npm test
npm run typecheck
```
Expected: PASS.

---

### Task 5: HTTP and MCP read-only execution quote surface

**Files:**
- Modify: `crypto-research-gateway/src/server.ts`
- Modify: `crypto-research-gateway/src/mcp/server.ts`
- Modify: `crypto-research-gateway/test/http.test.ts`
- Modify: `crypto-research-gateway/test/mcp.test.ts`

**Interfaces:**
- `POST /research/market` accepts `action: 'execution_quote'`, `side`, optional `executionVenue`.
- Add MCP read-only tool `market_execution_quote` with symbol, instrument, side, optional executionVenue.

- [ ] **Step 1: Write failing HTTP/MCP tests**

Assert execution quote requires side; `market_execution_quote` appears in allowlist; write-oriented names remain rejected; existing snapshot/candles/orderbook/funding endpoints remain accepted.

- [ ] **Step 2: Run RED**

Run:
```bash
npm test -- --run test/http.test.ts test/mcp.test.ts
```
Expected: FAIL.

- [ ] **Step 3: Implement API/MCP schema changes**

Keep the MCP tool read-only and route it to `ResearchRuntime.runMarket({action:'execution_quote', ...})`. Do not add any order-placement tool or credential surface.

- [ ] **Step 4: Run GREEN/build**

Run:
```bash
npm test
npm run typecheck
npm run build
```
Expected: PASS.

---

### Task 6: CI live-price smoke and documentation

**Files:**
- Modify: `.github/workflows/zero-local-cloud-runtime.yml`
- Modify: `tests/test_zero_local_manifest.py`
- Modify: `crypto-research-gateway/README.md`

**Interfaces:**
- CI verifies live Binance execution quote for BTCUSDT/SOLUSDT.
- Bybit must either produce a fresh valid execution quote or explicit `region_restricted_bybit_cloud_region`/`VENUE_UNAVAILABLE` caused by the known region restriction.

- [ ] **Step 1: Write failing manifest assertion**

Require workflow text to contain a live `execution_quote` smoke, bid/ask validation, freshness validation, and explicit Bybit restriction handling.

- [ ] **Step 2: Run RED**

Run:
```bash
python -m unittest discover -s tests -p 'test_zero_local_manifest.py' -v
```
Expected: FAIL.

- [ ] **Step 3: Extend workflow and docs**

Start the built gateway, POST a Binance `execution_quote` request, assert positive bid/ask, `bid <= ask`, `quoteAgeMs <= 5000`, `executionVerified=true`, and correct executable semantic. Probe Bybit and accept only a valid quote or the explicit known region restriction path. No proxy or geo-bypass.

README must document venue-bound execution semantics and fail-closed statuses.

- [ ] **Step 4: Run all local CI commands in GitHub Actions**

Required:
```bash
python -m unittest discover -s tests -p 'test_live_price_policy.py' -v
python -m unittest discover -s tests -p 'test_cloud_runtime_policy.py' -v
python -m unittest discover -s tests -p 'test_zero_local_manifest.py' -v
cd crypto-research-gateway && npm install --no-audit --no-fund && npm test && npm run typecheck && npm run build
python AI_SKILL_LIBRARY/validate_skill_registry.py
python AI_SKILL_LIBRARY/validate_brain.py
python AI_SKILL_LIBRARY/validate_router.py
python AI_SKILL_LIBRARY/validate_v4.py
python AI_SKILL_LIBRARY/validate_authority.py
```
Expected: PASS.

---

### Task 7: PR, exact-head verification, merge, and production verification

**Files:** no new production behavior.

- [ ] **Step 1: Open draft PR to `main`**
- [ ] **Step 2: Verify all required workflow runs on exact final head SHA**
- [ ] **Step 3: Review diff for no secrets, no HIGH_RISK route, no authority drift**
- [ ] **Step 4: Mark PR ready and merge only after exact-head checks are green**
- [ ] **Step 5: Verify post-merge workflows on canonical merge SHA**
- [ ] **Step 6: Redeploy Railway canonical `main`, verify deployment SUCCESS and `/health`; verify live execution-quote path if public domain access is available through connected tools**

Completion requires evidence for CI and deployment; no claim of live correctness is made solely from source code.