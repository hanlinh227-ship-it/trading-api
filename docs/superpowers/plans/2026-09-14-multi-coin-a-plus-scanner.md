# Multi-Coin A+ Scanner Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Replace the BTC-only opportunity-scan assumption with a research-only A+ scanner that dynamically searches liquid USDT perpetuals across Bybit, Binance, and OKX, while preserving the existing BTC/Bybit live-order boundary until a later separately approved execution migration.

**Architecture:** Keep GitHub Brain V4 and `docs/checkpoints/CURRENT_HANDOFF.md` as the single Trading authority entrypoint. Split that authority explicitly into scan/research authority (`MULTI-COIN-USDT-PERP-A-PLUS-SCANNER-1.0`) and production execution authority (`BYBIT-BTC-STATEFLOW-2.1`). Extend the existing `crypto-research-gateway` rather than creating a parallel runtime: add dynamic market discovery, normalized scanner evidence, staged universe pruning, deterministic structure/microstructure gates, gate-first A+ ranking, and a read-only HTTP/MCP scan surface. Existing venue-bound `execution_quote` behavior remains backward-compatible and must not become order authority.

**Tech Stack:** Python 3 validators/tests, YAML/Markdown authority/policy files, Node.js 22, TypeScript, Fastify 5, Zod 4, Vitest 5, existing public Bybit/Binance/OKX adapters, GitHub Actions, Railway zero-local runtime.

**Spec:** `docs/superpowers/specs/2026-09-14-multi-coin-a-plus-scanner-design.md`

---

## Global Constraints

- Default scan scope is all eligible **USDT-margined perpetuals** discoverable on Bybit, Binance, and OKX; BTC receives no ranking bonus or routing preference.
- Scan/research outputs are always `researchOnly: true` and `productionExecutionAuthority: false`.
- The existing production order authority stays `BYBIT-BTC-STATEFLOW-2.1` until a separate execution spec is explicitly approved and verified.
- Preserve `BYBIT_AUTO_LIVE`, `BYBIT_BTC_LIVE_ACK`, Bybit signing/private proxy, `/bybit/health`, and the existing BTC state/KV key unchanged.
- Do not resurrect the retired legacy multi-coin Bybit engine, Signal V10/V11, AI-council execution, martingale, grid rescue, or add-to-loser logic.
- Do not change `AI_SKILL_LIBRARY/skills/registry/live_price_policy.yaml` to make multi-coin research look like multi-venue live-order authority. Scanner policy is separate and checkpoint-resolved.
- No provider/indicator/funding/OI/book signal can independently authorize A+; mandatory gates are structure-first and fail closed.
- No order placement/cancel/leverage/account/wallet/transfer/withdrawal/swap/bridge/payment MCP or HTTP action may be added.
- Liquidation evidence is optional in Phase 1 when a provider does not expose reliable public data; absence must be explicit, never fabricated.
- Keep Gate/KuCoin generic research support intact, but the A+ scanner universe in this version is only Bybit + Binance + OKX.
- No production merge/deploy without a separate explicit production approval because `main` is Railway auto-deploying.

---

### Task 1: Split Trading scan authority from execution authority

**Files:**
- Create: `docs/checkpoints/MULTI_COIN_A_PLUS_SCANNER_1_0_20260914.md`
- Create: `AI_SKILL_LIBRARY/tests/test_multi_coin_scanner_authority.py`
- Modify: `docs/checkpoints/CURRENT_HANDOFF.md`
- Modify: `AI_SKILL_LIBRARY/projects.yaml`
- Modify: `AI_SKILL_LIBRARY/validate_authority.py`
- Modify: `AI_SKILL_LIBRARY/router.yaml`
- Modify: `AI_SKILL_LIBRARY/skills/trading/trading_router.md`

**Target contract:**
- Current Trading authority entrypoint remains `docs/checkpoints/CURRENT_HANDOFF.md`.
- Current scan/research checkpoint becomes `docs/checkpoints/MULTI_COIN_A_PLUS_SCANNER_1_0_20260914.md`.
- `authority_token: MULTI-COIN-USDT-PERP-A-PLUS-SCANNER-1.0`.
- Add explicit `execution_authority_token: BYBIT-BTC-STATEFLOW-2.1` and `execution_checkpoint: docs/checkpoints/BYBIT_BTC_STATEFLOW_2_1_20260904.md` to the Trading project row.
- Handoff must state that broad scanning is multi-coin while live order placement remains BTCUSDT/Bybit only.

- [ ] **Step 1: Write the failing authority regression test**

Create `AI_SKILL_LIBRARY/tests/test_multi_coin_scanner_authority.py` asserting:
- Trading `canonical_checkpoint` is the new multi-coin scanner checkpoint.
- scanner authority token is `MULTI-COIN-USDT-PERP-A-PLUS-SCANNER-1.0`.
- execution token/checkpoint still point to `BYBIT-BTC-STATEFLOW-2.1`.
- `CURRENT_HANDOFF.md` names both authorities and explicitly states scan/research cannot grant execution.
- validator rejects a Trading row where scan authority and execution authority are silently collapsed.
- compatibility router follows the current scanner checkpoint, not the historical BTC checkpoint as its single generic Trading pointer.

- [ ] **Step 2: Run RED**

```bash
python -m unittest AI_SKILL_LIBRARY.tests.test_multi_coin_scanner_authority -v
```

Expected: FAIL because the Trading project still has the BTC-only canonical checkpoint and the new checkpoint does not exist.

- [ ] **Step 3: Implement the minimum authority migration**

Write the new checkpoint from the approved design. Rewrite `CURRENT_HANDOFF.md` as an umbrella authority with separate headings `SCAN/RESEARCH AUTHORITY` and `PRODUCTION EXECUTION AUTHORITY`. Preserve all existing BTC live infrastructure and risk governors. Update `projects.yaml`, compatibility `router.yaml`, `trading_router.md`, and replace the BTC-only hard-coded assertions in `validate_authority.py` with explicit dual-authority checks.

Do not modify G9 research manifests to claim live execution; their existing `production_execution_authority: false` remains correct.

- [ ] **Step 4: Run GREEN and authority regressions**

```bash
python -m unittest AI_SKILL_LIBRARY.tests.test_multi_coin_scanner_authority -v
python AI_SKILL_LIBRARY/validate_authority.py
python -m unittest AI_SKILL_LIBRARY.tests.test_harmonization_multimarket -v
python -m unittest discover -s AI_SKILL_LIBRARY/tests -p 'test_*.py'
```

Expected: PASS; existing harmonization still treats research coverage as non-execution authority.

- [ ] **Step 5: Commit checkpoint**

```bash
git add docs/checkpoints AI_SKILL_LIBRARY/projects.yaml AI_SKILL_LIBRARY/validate_authority.py AI_SKILL_LIBRARY/router.yaml AI_SKILL_LIBRARY/skills/trading/trading_router.md AI_SKILL_LIBRARY/tests/test_multi_coin_scanner_authority.py
git commit -m "feat: separate multi-coin scan and BTC execution authority"
```

---

### Task 2: Add checkpoint-resolved scanner policy and deterministic data types

**Files:**
- Create: `AI_SKILL_LIBRARY/skills/registry/multi_coin_scanner_policy.yaml`
- Create: `tests/test_multi_coin_scanner_policy.py`
- Modify: `AI_SKILL_LIBRARY/checkpoint.json`
- Modify: `AI_SKILL_LIBRARY/runtime/cloud_runtime.yaml`
- Modify: `AI_SKILL_LIBRARY/v4/tools/build_retrieval_index.py`
- Create: `crypto-research-gateway/src/scanner/types.ts`
- Create: `crypto-research-gateway/src/scanner/config.ts`
- Create: `crypto-research-gateway/test/scanner-config.test.ts`

**Policy requirements:**
- Venues exactly `[bybit, binance, okx]`.
- Instrument universe is USDT perpetual only.
- Minimum cross-venue coverage is 2.
- Broad/deep candidate limits, minimum quote volume, maximum spread, minimum near-touch depth, minimum candle history, minimum RR, tie tolerance, and evidence weights are configuration values rather than strategy literals.
- Executable freshness and price-divergence thresholds reference/agree with the existing live-price policy instead of silently redefining execution semantics.

- [ ] **Step 1: Write RED policy tests**

Python test asserts the checkpoint resolves `multi_coin_scanner_policy_path`, the policy is research-only, uses the three approved venues, has `min_venue_coverage == 2`, no BTC priority field, and does not grant execution.

Vitest asserts `loadScannerConfig()` validates positive thresholds, rejects zero/negative candidate limits, and exposes no `preferredSymbol`/BTC bonus.

- [ ] **Step 2: Run RED**

```bash
python -m unittest discover -s tests -p 'test_multi_coin_scanner_policy.py' -v
cd crypto-research-gateway && npm test -- --run test/scanner-config.test.ts
```

Expected: FAIL because scanner policy/types/config do not exist.

- [ ] **Step 3: Implement minimum policy/types/config**

Define scanner types for venue, market summary, normalized candle, trade print, order book, derivatives context, structure signal, candidate evidence, venue quote quality, candidate state, and final scan result. Every final result type carries `researchOnly: true` and `productionExecutionAuthority: false`.

- [ ] **Step 4: Run GREEN**

```bash
python -m unittest discover -s tests -p 'test_multi_coin_scanner_policy.py' -v
cd crypto-research-gateway && npm test -- --run test/scanner-config.test.ts && npm run typecheck
```

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add AI_SKILL_LIBRARY/checkpoint.json AI_SKILL_LIBRARY/runtime/cloud_runtime.yaml AI_SKILL_LIBRARY/skills/registry/multi_coin_scanner_policy.yaml AI_SKILL_LIBRARY/v4/tools/build_retrieval_index.py tests/test_multi_coin_scanner_policy.py crypto-research-gateway/src/scanner crypto-research-gateway/test/scanner-config.test.ts
git commit -m "feat: define multi-coin scanner policy contract"
```

---

### Task 3: Add dynamic Bybit/Binance/OKX perpetual discovery and executed-flow data

**Files:**
- Modify: `crypto-research-gateway/src/providers/types.ts`
- Modify: `crypto-research-gateway/src/providers/binance.ts`
- Modify: `crypto-research-gateway/src/providers/bybit.ts`
- Modify: `crypto-research-gateway/src/providers/okx.ts`
- Modify: `crypto-research-gateway/test/providers.test.ts`

**Provider interface additions:**
```ts
listPerpetualMarkets?(): Promise<PerpetualMarketSummary[]>;
recentTrades?(symbol: string, limit: number): Promise<TradePrint[]>;
```

Optional historical OI support may be added only if it is needed for a deterministic OI delta and has a reliable public endpoint.

**Expected first-party reads:**
- Binance: USD-M `exchangeInfo`, 24h ticker/book data, `aggTrades`; normalize `m=true` as seller-taker and `m=false` as buyer-taker.
- Bybit: V5 `instruments-info?category=linear`, linear tickers with pagination where required, `recent-trade`.
- OKX: `public/instruments?instType=SWAP`, `market/tickers?instType=SWAP`, `market/trades`; only `*-USDT-SWAP` enters this scanner.
- Fix OKX snapshot to emit native `bidPx`/`askPx` observations so it can participate in recommended-venue pricing.

- [ ] **Step 1: Extend mocked provider tests first**

Assert each venue:
- discovers active USDT perpetuals and excludes spot/delivery/non-USDT instruments;
- maps to canonical `BASEUSDT` symbols;
- returns quote volume/spread/source timestamps where available;
- returns normalized buyer/seller taker trades;
- OKX snapshot returns bid/ask/last/mark with correct semantic timestamps.

- [ ] **Step 2: Run RED**

```bash
cd crypto-research-gateway
npm test -- --run test/providers.test.ts
```

Expected: FAIL because discovery/trade methods and OKX bid/ask are absent.

- [ ] **Step 3: Implement provider additions using GET-only public APIs**

Keep timeout, region restriction, and no-auth behavior. Do not add credentials or write endpoints.

- [ ] **Step 4: Run GREEN/regression**

```bash
npm test -- --run test/providers.test.ts
npm test
npm run typecheck
```

Expected: PASS; existing Bybit/Binance `execution_quote` behavior remains unchanged.

- [ ] **Step 5: Commit**

```bash
git add crypto-research-gateway/src/providers crypto-research-gateway/test/providers.test.ts
git commit -m "feat: discover liquid perpetuals across scanner venues"
```

---

### Task 4: Build the broad universe and liquidity/freshness gates

**Files:**
- Create: `crypto-research-gateway/src/scanner/universe.ts`
- Create: `crypto-research-gateway/test/scanner-universe.test.ts`

**Interface:**
```ts
export function buildEligibleUniverse(input: {
  marketsByVenue: Partial<Record<ScannerVenue, PerpetualMarketSummary[]>>;
  config: ScannerConfig;
  nowMs: number;
}): UniverseDecision;
```

The result must include eligible symbols plus per-symbol rejection reasons for auditability.

- [ ] **Step 1: Write RED universe tests**

Required cases:
- ETH/SOL can qualify while BTC fails liquidity/freshness; no BTC exception.
- one-venue-only symbols fail coverage.
- stale quotes fail.
- excessive spread fails.
- insufficient configured 24h quote volume fails.
- inactive/non-USDT/non-perpetual markets fail.
- deterministic order uses liquidity/quality fields and symbol only as final stable tie-breaker, never BTC preference.

- [ ] **Step 2: Run RED**

```bash
npm test -- --run test/scanner-universe.test.ts
```

Expected: FAIL because universe builder is absent.

- [ ] **Step 3: Implement staged broad filter**

Do no deep candles/orderbook/trades in this layer. Keep it cheap: merge canonical symbols, enforce minimum venue coverage, freshness, spread and volume, then cap to configured broad candidates.

- [ ] **Step 4: Run GREEN**

```bash
npm test -- --run test/scanner-universe.test.ts
npm run typecheck
```

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add crypto-research-gateway/src/scanner/universe.ts crypto-research-gateway/test/scanner-universe.test.ts
git commit -m "feat: add unbiased perpetual universe filter"
```

---

### Task 5: Normalize deep evidence and implement structure-first setup detection

**Files:**
- Create: `crypto-research-gateway/src/scanner/normalizers.ts`
- Create: `crypto-research-gateway/src/scanner/structure.ts`
- Create: `crypto-research-gateway/test/scanner-normalizers.test.ts`
- Create: `crypto-research-gateway/test/scanner-structure.test.ts`

**Supported setup families:**
- `SWEEP_RECLAIM`
- `BREAK_RETEST`
- `DISPLACEMENT_RETEST`
- `REGIME_CONTINUATION`

**Contract:** A structure signal must contain direction, trigger, entry zone, structural invalidation, stop, target logic, RR, setup family, timeframe context, and evidence timestamps. Missing invalidation or insufficient history cannot become A+.

- [ ] **Step 1: Write deterministic fixtures and failing tests**

Use synthetic 5m/1h candles rather than live provider data. Assert:
- sell-side sweep + close reclaim yields LONG candidate;
- buy-side sweep + reclaim down yields SHORT candidate;
- clean break/retest holds in the breakout direction;
- false breakout / no acceptance returns no qualifying signal;
- insufficient bars returns `INSUFFICIENT_HISTORY`;
- no clear stop/invalidation fails closed;
- computed RR below policy minimum is not A+ eligible.

Also test Bybit/Binance/OKX raw candle payload normalization separately.

- [ ] **Step 2: Run RED**

```bash
npm test -- --run test/scanner-normalizers.test.ts test/scanner-structure.test.ts
```

Expected: FAIL because normalizers/structure engine do not exist.

- [ ] **Step 3: Implement minimal deterministic structure engine**

Use closed candles only for trigger confirmation. Keep thresholds/configuration explicit. Do not introduce RSI/MACD/EMA as independent authority.

- [ ] **Step 4: Run GREEN**

```bash
npm test -- --run test/scanner-normalizers.test.ts test/scanner-structure.test.ts
npm run typecheck
```

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add crypto-research-gateway/src/scanner/normalizers.ts crypto-research-gateway/src/scanner/structure.ts crypto-research-gateway/test/scanner-normalizers.test.ts crypto-research-gateway/test/scanner-structure.test.ts
git commit -m "feat: add structure-first A+ setup detection"
```

---

### Task 6: Add executed-flow, L2 and derivatives context without turning them into triggers

**Files:**
- Create: `crypto-research-gateway/src/scanner/microstructure.ts`
- Create: `crypto-research-gateway/test/scanner-microstructure.test.ts`

**Computed evidence:**
- taker buy/sell notional and normalized imbalance;
- burst intensity / recent-flow alignment;
- best bid/ask spread;
- depth imbalance within configured 2/5/10 bps bands;
- distance-weighted near-touch imbalance and microprice where inputs permit;
- OI direction/change when history exists;
- funding/premium/crowding modifiers when available;
- liquidation context as explicit `available: false` when unavailable.

- [ ] **Step 1: Write RED tests**

Assert bullish structure is supported by buyer-taker flow but flow alone with no structure cannot create a candidate. Assert spoof-like static wall without executed support does not independently promote. Assert extreme crowding can reduce quality but cannot create opposite-direction trade. Assert crossed books/stale order books fail the relevant gate.

- [ ] **Step 2: Run RED**

```bash
npm test -- --run test/scanner-microstructure.test.ts
```

Expected: FAIL.

- [ ] **Step 3: Implement evidence calculations**

Return typed metrics/modifiers only. Keep final promotion logic in the ranker.

- [ ] **Step 4: Run GREEN**

```bash
npm test -- --run test/scanner-microstructure.test.ts
npm run typecheck
```

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add crypto-research-gateway/src/scanner/microstructure.ts crypto-research-gateway/test/scanner-microstructure.test.ts
git commit -m "feat: add scanner flow and microstructure evidence"
```

---

### Task 7: Implement cross-venue quote quality, venue recommendation and gate-first A+ ranker

**Files:**
- Create: `crypto-research-gateway/src/scanner/venue-quality.ts`
- Create: `crypto-research-gateway/src/scanner/ranker.ts`
- Create: `crypto-research-gateway/test/scanner-venue-quality.test.ts`
- Create: `crypto-research-gateway/test/scanner-ranker.test.ts`

**Rules:**
- Use existing `buildExecutionQuote()` semantics to validate LONG ask / SHORT bid freshness per venue where practical.
- For scanner research, evaluate Bybit/Binance/OKX as candidate quote venues; this is `selectedVenue`/`recommendedVenue`, not live order permission.
- Cross-venue comparison uses semantically equivalent bid-vs-bid or ask-vs-ask and existing divergence policy.
- Mandatory gates run before scoring.
- Scoring weights come from scanner config.
- Material tie/contradiction returns `WATCHLIST` or `NO A+ SETUP`, never arbitrary winner.

- [ ] **Step 1: Write RED ranking tests**

Required regressions:
- SOL can rank above BTC when SOL evidence is stronger.
- BTC receives no fixed bonus.
- candidate with best score but stale quote cannot pass mandatory gates.
- candidate with unresolved `PRICE_DIVERGENCE` cannot be A+.
- clear structure + aligned flow + adequate L2 + sane derivatives + RR/freshness passes A+.
- two materially tied finalists do not get an arbitrary A+ winner.
- every result has `researchOnly=true`, `productionExecutionAuthority=false` and `executionAuthority='none'`.
- selected venue can be OKX when its fresh executable quote/liquidity quality is best, without implying OKX order authority.

- [ ] **Step 2: Run RED**

```bash
npm test -- --run test/scanner-venue-quality.test.ts test/scanner-ranker.test.ts
```

Expected: FAIL.

- [ ] **Step 3: Implement venue quality and ranker**

Return auditable gate results and component scores. Store reason codes for every failed gate.

- [ ] **Step 4: Run GREEN**

```bash
npm test -- --run test/scanner-venue-quality.test.ts test/scanner-ranker.test.ts
npm test
npm run typecheck
```

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add crypto-research-gateway/src/scanner/venue-quality.ts crypto-research-gateway/src/scanner/ranker.ts crypto-research-gateway/test/scanner-venue-quality.test.ts crypto-research-gateway/test/scanner-ranker.test.ts
git commit -m "feat: rank A+ candidates without BTC preference"
```

---

### Task 8: Orchestrate staged market-wide scan

**Files:**
- Create: `crypto-research-gateway/src/scanner/scanner.ts`
- Create: `crypto-research-gateway/test/scanner-runtime.test.ts`
- Modify: `crypto-research-gateway/src/research.ts`

**Interface:**
```ts
runAPlusScan(input?: {
  symbols?: string[];
  maxWatchlist?: number;
}): Promise<ScanResult>
```

`symbols` is an optional bounded override for tests/smoke/manual diagnostics. Omitting it must perform dynamic broad-universe discovery.

**Pipeline:**
1. discover three-venue perpetual markets;
2. broad liquidity/freshness prune;
3. fetch 1h + 5m candles only for broad finalists;
4. structural pre-screen and cap to deep candidates;
5. fetch recent trades/orderbook/derivatives/snapshots only for deep candidates;
6. cross-venue validation and venue recommendation;
7. rank and return one A+, watchlist, or no setup.

- [ ] **Step 1: Write RED orchestration tests with fake providers**

Assert expensive deep calls are not made for rejected broad symbols, a non-BTC symbol can become top candidate, provider failure on one symbol does not abort all symbols, and no qualifying symbol returns `NO A+ SETUP` rather than forced entry.

- [ ] **Step 2: Run RED**

```bash
npm test -- --run test/scanner-runtime.test.ts
```

Expected: FAIL.

- [ ] **Step 3: Implement staged scanner orchestration**

Use bounded concurrency and per-symbol error capture. No hidden fallback to BTC.

- [ ] **Step 4: Run GREEN/regression**

```bash
npm test -- --run test/scanner-runtime.test.ts
npm test
npm run typecheck
```

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add crypto-research-gateway/src/scanner/scanner.ts crypto-research-gateway/src/research.ts crypto-research-gateway/test/scanner-runtime.test.ts
git commit -m "feat: orchestrate market-wide A+ research scan"
```

---

### Task 9: Expose read-only HTTP and MCP scan surfaces

**Files:**
- Modify: `crypto-research-gateway/src/server.ts`
- Modify: `crypto-research-gateway/src/mcp/server.ts`
- Modify: `crypto-research-gateway/test/http.test.ts`
- Modify: `crypto-research-gateway/test/mcp.test.ts`
- Modify: `crypto-research-gateway/test/gateway-contract-integration.test.ts`

**Surfaces:**
- Add `POST /research/scan`.
- Add read-only MCP tool `market_a_plus_scan`.
- `/health` exposes scanner authority name and scan venues, but still reports zero-local/read-only runtime.
- `/capabilities` remains read-only and contains no order/fund-moving capability.

**Response contract:**
- `state`: `A+ LIVE CANDIDATE | WATCHLIST | NO A+ SETUP`.
- top candidate fields when present: symbol, direction, selected venue, executable price/quote age, trigger, entry zone, stop, target(s), RR, rationale, invalidation, cross-venue summary, freshness/provenance.
- always include `scannerAuthority: MULTI-COIN-USDT-PERP-A-PLUS-SCANNER-1.0`, `researchOnly: true`, `productionExecutionAuthority: false`.

- [ ] **Step 1: Write RED HTTP/MCP/data-contract tests**

Assert default scan requires no symbol, optional `symbols` is bounded, invalid inputs fail 400, MCP allowlist adds only the read-only scan tool, and scanner envelope cannot escalate `authority.execution` or production authority.

- [ ] **Step 2: Run RED**

```bash
npm test -- --run test/http.test.ts test/mcp.test.ts test/gateway-contract-integration.test.ts
```

Expected: FAIL.

- [ ] **Step 3: Implement API/MCP wiring**

Do not modify existing `market_execution_quote` semantics or add any write tool.

- [ ] **Step 4: Run GREEN/build**

```bash
npm test
npm run typecheck
npm run build
```

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add crypto-research-gateway/src/server.ts crypto-research-gateway/src/mcp/server.ts crypto-research-gateway/test
git commit -m "feat: expose read-only multi-coin A+ scan API"
```

---

### Task 10: Refresh retrieval metadata, docs and CI without widening execution

**Files:**
- Modify: `AI_SKILL_LIBRARY/v4/index/retrieval_index.yaml` (generated only)
- Modify: `crypto-research-gateway/README.md`
- Modify: `.github/workflows/zero-local-cloud-runtime.yml`
- Modify: `tests/test_zero_local_manifest.py` only if required for the new bounded scanner smoke

- [ ] **Step 1: Add/adjust failing CI manifest assertions**

Require pre-merge validation to exercise a bounded scan fixture/symbol subset such as BTCUSDT/ETHUSDT/SOLUSDT and assert:
- scanner response is research-only;
- output state is in the three-state vocabulary;
- no production execution permission is exposed;
- existing venue-bound execution quote smoke remains intact.

Do not make GitHub-hosted CI perform an unbounded all-market scan.

- [ ] **Step 2: Run RED for manifest assertion if changed**

```bash
python -m unittest discover -s tests -p 'test_zero_local_manifest.py' -v
```

Expected: FAIL until workflow contains the new bounded scan smoke.

- [ ] **Step 3: Update docs/workflow and regenerate retrieval index**

README must explain the distinction between `market_a_plus_scan` / `/research/scan` and legacy venue-bound `execution_quote`.

Regenerate the index from source, never hand-edit it:

```bash
python AI_SKILL_LIBRARY/v4/tools/build_retrieval_index.py --root .
python AI_SKILL_LIBRARY/v4/tools/build_retrieval_index.py --check --root .
```

Verify HOT Trading pointers now resolve the new scanner checkpoint/token while the handoff still exposes the separate BTC execution checkpoint.

- [ ] **Step 4: Run complete local-equivalent verification**

```bash
python AI_SKILL_LIBRARY/validate_registry.py
python AI_SKILL_LIBRARY/validate_brain.py
python AI_SKILL_LIBRARY/validate_router.py
python AI_SKILL_LIBRARY/validate_authority.py
python AI_SKILL_LIBRARY/validate_runtime.py
python AI_SKILL_LIBRARY/validate_v3.py
python AI_SKILL_LIBRARY/validate_v4.py
python AI_SKILL_LIBRARY/validate_skill_registry.py
python AI_SKILL_LIBRARY/validate_skill_gateway.py
python -m unittest discover -s AI_SKILL_LIBRARY/tests -p 'test_*.py'
python -m unittest discover -s tests -p 'test_*.py'
cd crypto-research-gateway && npm test && npm run typecheck && npm run build
```

Expected: all PASS.

- [ ] **Step 5: Run the canonical Brain CI entrypoint**

From repository root:

```bash
python AI_SKILL_LIBRARY/v4/tools/ci_validate.py --source-sha "$(git rev-parse HEAD)"
```

Expected: `CI_VALIDATE=PASS failures=0`.

- [ ] **Step 6: Commit verification/docs metadata**

```bash
git add AI_SKILL_LIBRARY/v4/index/retrieval_index.yaml crypto-research-gateway/README.md .github/workflows/zero-local-cloud-runtime.yml tests/test_zero_local_manifest.py
git commit -m "ci: validate multi-coin A+ scanner boundaries"
```

---

### Task 11: Review exact feature head and open a draft PR; stop before production deployment

**Files:** no additional behavior unless review finds a causal defect.

- [ ] Compare implementation branch against `main`; verify scope contains only approved authority/scanner/gateway/test/CI/doc changes.
- [ ] Search diff for credentials, order-write functions, live-switch expansion, and accidental removal/reset of BTC state infrastructure.
- [ ] Verify the final exact head SHA has all required GitHub-native checks green.
- [ ] Open a draft PR to `main` with explicit statements:
  - scan/research authority expanded to market-wide USDT perpetuals;
  - production order execution remains BTCUSDT Bybit under `BYBIT-BTC-STATEFLOW-2.1`;
  - no write/fund-moving tool added;
  - no guarantee of A+ profitability.
- [ ] Run review and fix only demonstrated defects with regression tests.
- [ ] Mark ready only after exact-head verification.
- [ ] **STOP before merge to `main`.** The repository documents Railway auto-deploy from `main`, so merging can cause production deployment. Ask the user for explicit production deployment approval before merge/deploy.

**Completion evidence before asking for deploy approval:**
- exact branch/head SHA;
- changed-file list;
- unit/test/typecheck/build results;
- Brain/authority/retrieval validation results;
- PR number and mergeability;
- explicit statement that production is still unchanged.

---

## Post-Approval Production Gate (not authorized by this implementation approval)

Only after the user separately approves production deployment:
1. merge with expected-head protection;
2. verify canonical `main` SHA;
3. wait for Railway exact-main deployment success;
4. verify `/health` reports the exact deployment SHA and scanner authority;
5. verify `/capabilities` is read-only and contains `market_a_plus_scan` with no write tools;
6. run a bounded production scanner smoke plus existing Bybit/Binance execution-quote smoke;
7. verify a non-BTC symbol can be evaluated without receiving live-order authority;
8. report production status with `researchOnly=true`, `productionExecutionAuthority=false` for scanner output.

No source commit, PR, or passing test by itself is sufficient to claim the scanner is deployed or LIVE.