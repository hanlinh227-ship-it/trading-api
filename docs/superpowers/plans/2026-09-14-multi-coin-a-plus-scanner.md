# Multi-Coin A+ Scanner Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Replace the BTC-only opportunity-scan assumption with a research-only A+ scanner that dynamically searches liquid USDT perpetuals across Bybit, Binance, and OKX, while preserving the existing BTC/Bybit live-order boundary until a later separately approved execution migration.

**Architecture:** Keep GitHub Brain V4 and `docs/checkpoints/CURRENT_HANDOFF.md` as the single Trading authority entrypoint. Split authority explicitly into scan/research authority (`MULTI-COIN-USDT-PERP-A-PLUS-SCANNER-1.0`) and production execution authority (`BYBIT-BTC-STATEFLOW-2.1`). Extend the existing `crypto-research-gateway`: dynamic universe discovery -> cheap liquidity/freshness pruning -> structure-first pre-screen -> deep flow/L2/derivatives evidence -> cross-venue quote validation -> gate-first A+ ranking -> one best candidate/watchlist/no setup. Existing `market_execution_quote` stays read-only and backward-compatible; scanner venue recommendation never grants order authority.

**Tech Stack:** Python 3 validators/tests, YAML/Markdown authority/policy, Node.js 22, TypeScript, Fastify 5, Zod 4, Vitest 5, public Bybit/Binance/OKX APIs, GitHub Actions, Railway zero-local runtime.

**Spec:** `docs/superpowers/specs/2026-09-14-multi-coin-a-plus-scanner-design.md`

---

## Global constraints

- Default scan = all eligible USDT-margined perpetuals discoverable on Bybit, Binance, OKX. BTC gets no ranking/routing bonus.
- Every scanner output: `researchOnly: true`, `productionExecutionAuthority: false`, `executionAuthority: "none"`.
- Actual live order authority remains `BYBIT-BTC-STATEFLOW-2.1` until a later execution spec is explicitly approved and runtime-verified.
- Preserve `BYBIT_AUTO_LIVE`, `BYBIT_BTC_LIVE_ACK`, Bybit signing/private proxy, `/bybit/health`, and existing BTC state/KV.
- Never resurrect retired legacy multi-coin/V10/V11/AI-council execution, martingale, grid rescue, or add-to-loser logic.
- Do not repurpose `live_price_policy.yaml` as scanner authority. Add a separate checkpoint-resolved scanner policy and reuse live-price freshness/divergence semantics where applicable.
- Structure is mandatory. Funding/OI/book/liquidation/AI/one candle cannot independently create A+.
- No order/cancel/leverage/account/wallet/transfer/withdrawal/swap/bridge/payment capability may be added.
- Liquidation context is optional in Phase 1; unavailable data is explicit, never fabricated.
- Gate/KuCoin generic research remains intact but is outside the A+ scanner universe for v1.
- Stop before merge to `main`: the repo documents Railway auto-deploy from `main`, so production merge/deploy requires separate explicit approval.

---

## Task 1 — Split scan authority from execution authority

**Files**
- Create `docs/checkpoints/MULTI_COIN_A_PLUS_SCANNER_1_0_20260914.md`
- Create `AI_SKILL_LIBRARY/tests/test_multi_coin_scanner_authority.py`
- Modify `docs/checkpoints/CURRENT_HANDOFF.md`
- Modify `AI_SKILL_LIBRARY/projects.yaml`
- Modify `AI_SKILL_LIBRARY/validate_authority.py`
- Modify `AI_SKILL_LIBRARY/router.yaml`
- Modify `AI_SKILL_LIBRARY/skills/trading/trading_router.md`

**RED first**

Test that Trading keeps `CURRENT_HANDOFF.md` as entrypoint but now has:
- `canonical_checkpoint: docs/checkpoints/MULTI_COIN_A_PLUS_SCANNER_1_0_20260914.md`
- `authority_token: MULTI-COIN-USDT-PERP-A-PLUS-SCANNER-1.0`
- `execution_checkpoint: docs/checkpoints/BYBIT_BTC_STATEFLOW_2_1_20260904.md`
- `execution_authority_token: BYBIT-BTC-STATEFLOW-2.1`
- handoff text names both scopes and explicitly says scan/research cannot grant execution
- validator rejects collapsed/ambiguous authority.

Run:
```bash
python -m unittest AI_SKILL_LIBRARY.tests.test_multi_coin_scanner_authority -v
```
Expected RED: current project still points its canonical Trading checkpoint at BTC StateFlow.

**GREEN implementation**
- Write the new scanner checkpoint from the approved spec.
- Rewrite `CURRENT_HANDOFF.md` as umbrella authority with separate `SCAN/RESEARCH AUTHORITY` and `PRODUCTION EXECUTION AUTHORITY` sections.
- Preserve BTC live infrastructure/risk rules unchanged.
- Update `projects.yaml`, compatibility `router.yaml`, `trading_router.md`, and remove BTC-only hard-coding from `validate_authority.py` in favor of explicit dual-authority validation.
- Leave G9 `production_execution_authority: false` semantics intact.

Verify:
```bash
python -m unittest AI_SKILL_LIBRARY.tests.test_multi_coin_scanner_authority -v
python AI_SKILL_LIBRARY/validate_authority.py
python -m unittest AI_SKILL_LIBRARY.tests.test_harmonization_multimarket -v
python -m unittest discover -s AI_SKILL_LIBRARY/tests -p 'test_*.py'
```
Expected: PASS.

Commit:
```bash
git add docs/checkpoints AI_SKILL_LIBRARY/projects.yaml AI_SKILL_LIBRARY/validate_authority.py AI_SKILL_LIBRARY/router.yaml AI_SKILL_LIBRARY/skills/trading/trading_router.md AI_SKILL_LIBRARY/tests/test_multi_coin_scanner_authority.py
git commit -m "feat: separate multi-coin scan and BTC execution authority"
```

---

## Task 2 — Add scanner policy and typed contracts

**Files**
- Create `AI_SKILL_LIBRARY/skills/registry/multi_coin_scanner_policy.yaml`
- Create `tests/test_multi_coin_scanner_policy.py`
- Modify `AI_SKILL_LIBRARY/checkpoint.json`
- Modify `AI_SKILL_LIBRARY/runtime/cloud_runtime.yaml`
- Modify `AI_SKILL_LIBRARY/v4/tools/build_retrieval_index.py`
- Create `crypto-research-gateway/src/scanner/types.ts`
- Create `crypto-research-gateway/src/scanner/config.ts`
- Create `crypto-research-gateway/test/scanner-config.test.ts`

Policy must define/configure: approved venues, USDT perpetual universe, `min_venue_coverage=2`, broad/deep candidate caps, volume/spread/depth/history/RR/tie thresholds and ranking weights. No BTC preference field. Quote freshness/divergence must agree with existing live-price policy rather than silently redefine it.

RED:
```bash
python -m unittest discover -s tests -p 'test_multi_coin_scanner_policy.py' -v
cd crypto-research-gateway && npm test -- --run test/scanner-config.test.ts
```
Expected: FAIL because policy/config do not exist.

GREEN: add scanner types for market summary, candle, trade print, order book, derivatives context, structure signal, gate result, candidate evidence, venue quality, candidate state and final scan result. Final result types hard-code the research-only boundary.

Verify:
```bash
python -m unittest discover -s tests -p 'test_multi_coin_scanner_policy.py' -v
cd crypto-research-gateway && npm test -- --run test/scanner-config.test.ts && npm run typecheck
```

Commit:
```bash
git add AI_SKILL_LIBRARY/checkpoint.json AI_SKILL_LIBRARY/runtime/cloud_runtime.yaml AI_SKILL_LIBRARY/skills/registry/multi_coin_scanner_policy.yaml AI_SKILL_LIBRARY/v4/tools/build_retrieval_index.py tests/test_multi_coin_scanner_policy.py crypto-research-gateway/src/scanner crypto-research-gateway/test/scanner-config.test.ts
git commit -m "feat: define multi-coin scanner policy contract"
```

---

## Task 3 — Dynamic Bybit/Binance/OKX discovery + executed flow

**Files**
- Modify `crypto-research-gateway/src/providers/types.ts`
- Modify `crypto-research-gateway/src/providers/binance.ts`
- Modify `crypto-research-gateway/src/providers/bybit.ts`
- Modify `crypto-research-gateway/src/providers/okx.ts`
- Modify `crypto-research-gateway/test/providers.test.ts`

Extend the provider contract with optional scanner reads:
```ts
listPerpetualMarkets?(): Promise<PerpetualMarketSummary[]>;
recentTrades?(symbol: string, limit: number): Promise<TradePrint[]>;
```
Add historical OI only if a reliable public endpoint is needed for deterministic OI delta.

Provider reads:
- Binance USD-M: `exchangeInfo`, 24h ticker/book data, `aggTrades`; `m=true` => seller taker, `m=false` => buyer taker.
- Bybit V5: `instruments-info?category=linear`, linear tickers with pagination, `recent-trade`.
- OKX: `public/instruments?instType=SWAP`, `market/tickers?instType=SWAP`, `market/trades`; only USDT swaps qualify.
- Fix OKX snapshot to emit native bid/ask in addition to last/mark.

RED mocked tests must prove active USDT perpetual filtering, canonical symbol mapping, volume/spread/timestamps, normalized taker side, and OKX bid/ask semantics.

Run RED/GREEN:
```bash
cd crypto-research-gateway
npm test -- --run test/providers.test.ts
npm test
npm run typecheck
```
First targeted run must fail before implementation; final three commands must pass.

Commit:
```bash
git add crypto-research-gateway/src/providers crypto-research-gateway/test/providers.test.ts
git commit -m "feat: discover liquid perpetuals across scanner venues"
```

---

## Task 4 — Build unbiased broad universe

**Files**
- Create `crypto-research-gateway/src/scanner/universe.ts`
- Create `crypto-research-gateway/test/scanner-universe.test.ts`

Interface:
```ts
buildEligibleUniverse({ marketsByVenue, config, nowMs }): UniverseDecision
```
Return eligible symbols plus per-symbol rejection reasons.

RED cases:
- ETH/SOL qualify while BTC fails freshness/liquidity; no BTC exception.
- one-venue-only fails coverage.
- stale quote/excess spread/insufficient quote volume/inactive/non-USDT/non-perpetual fail.
- deterministic ordering uses quality/liquidity, symbol only as final stable tie-breaker.

Run:
```bash
npm test -- --run test/scanner-universe.test.ts
```
Expected RED before implementation, PASS after implementation. Broad layer must not fetch deep candles/orderbook/trades.

Commit:
```bash
git add crypto-research-gateway/src/scanner/universe.ts crypto-research-gateway/test/scanner-universe.test.ts
git commit -m "feat: add unbiased perpetual universe filter"
```

---

## Task 5 — Normalize deep data + structure-first setup engine

**Files**
- Create `crypto-research-gateway/src/scanner/normalizers.ts`
- Create `crypto-research-gateway/src/scanner/structure.ts`
- Create `crypto-research-gateway/test/scanner-normalizers.test.ts`
- Create `crypto-research-gateway/test/scanner-structure.test.ts`

Supported families: `SWEEP_RECLAIM`, `BREAK_RETEST`, `DISPLACEMENT_RETEST`, `REGIME_CONTINUATION`.

A structure signal must include direction, trigger, entry zone, invalidation, stop, target logic, RR, family, timeframe context and timestamps. No invalidation/insufficient history => cannot be A+.

RED with synthetic 5m/1h fixtures:
- sell-side sweep/reclaim => LONG candidate;
- buy-side sweep/reclaim down => SHORT;
- clean break/retest => continuation candidate;
- false break/no acceptance => no signal;
- insufficient bars => `INSUFFICIENT_HISTORY`;
- RR below policy minimum => not A+ eligible;
- provider candle normalization is deterministic.

Run:
```bash
npm test -- --run test/scanner-normalizers.test.ts test/scanner-structure.test.ts
npm run typecheck
```
First targeted run RED; final run GREEN. Use closed candles for confirmation. Indicators may be context but never independent authority.

Commit:
```bash
git add crypto-research-gateway/src/scanner/normalizers.ts crypto-research-gateway/src/scanner/structure.ts crypto-research-gateway/test/scanner-normalizers.test.ts crypto-research-gateway/test/scanner-structure.test.ts
git commit -m "feat: add structure-first A+ setup detection"
```

---

## Task 6 — Executed-flow, L2 and derivatives context

**Files**
- Create `crypto-research-gateway/src/scanner/microstructure.ts`
- Create `crypto-research-gateway/test/scanner-microstructure.test.ts`

Compute typed evidence only: taker buy/sell notional and imbalance, burst intensity, spread, 2/5/10 bps depth imbalance, distance-weighted near-touch imbalance/microprice where valid, OI change where history exists, funding/premium/crowding modifiers, and explicit liquidation availability.

RED tests:
- flow supports existing structure but flow alone cannot create setup;
- static/spoof-like wall cannot independently promote;
- crowding modifies quality but cannot create an opposite trade;
- stale/crossed order book fails its gate.

Run:
```bash
npm test -- --run test/scanner-microstructure.test.ts
npm run typecheck
```
Expected RED then GREEN.

Commit:
```bash
git add crypto-research-gateway/src/scanner/microstructure.ts crypto-research-gateway/test/scanner-microstructure.test.ts
git commit -m "feat: add scanner flow and microstructure evidence"
```

---

## Task 7 — Cross-venue quote quality + gate-first ranker

**Files**
- Create `crypto-research-gateway/src/scanner/venue-quality.ts`
- Create `crypto-research-gateway/src/scanner/ranker.ts`
- Create `crypto-research-gateway/test/scanner-venue-quality.test.ts`
- Create `crypto-research-gateway/test/scanner-ranker.test.ts`

Rules:
- Reuse existing LONG=ask / SHORT=bid freshness semantics where practical.
- Evaluate Bybit/Binance/OKX as research quote venues. Call output `selectedVenue`/`recommendedVenue`, not execution permission.
- Compare ask-vs-ask or bid-vs-bid only; unresolved divergence blocks A+.
- Mandatory gates before score. Ties/contradictions => `WATCHLIST` or `NO A+ SETUP`.

RED regressions:
- SOL can beat BTC; BTC has no fixed bonus.
- high score cannot override stale quote, divergence, missing structure or insufficient RR.
- aligned structure/flow/L2/derivatives/freshness can pass A+.
- tied finalists do not get arbitrary winner.
- OKX can be selected as best research quote venue without order authority.
- every result preserves research-only fields.

Run:
```bash
npm test -- --run test/scanner-venue-quality.test.ts test/scanner-ranker.test.ts
npm test
npm run typecheck
```
Targeted run RED before code; final suite GREEN.

Commit:
```bash
git add crypto-research-gateway/src/scanner/venue-quality.ts crypto-research-gateway/src/scanner/ranker.ts crypto-research-gateway/test/scanner-venue-quality.test.ts crypto-research-gateway/test/scanner-ranker.test.ts
git commit -m "feat: rank A+ candidates without BTC preference"
```

---

## Task 8 — Staged market-wide orchestration

**Files**
- Create `crypto-research-gateway/src/scanner/scanner.ts`
- Create `crypto-research-gateway/test/scanner-runtime.test.ts`
- Modify `crypto-research-gateway/src/research.ts`

Interface:
```ts
runAPlusScan(input?: { symbols?: string[]; maxWatchlist?: number }): Promise<ScanResult>
```
Omitted `symbols` = dynamic broad universe. `symbols` is only a bounded override for tests/smoke/manual diagnostics.

Pipeline: discover -> broad prune -> 1h/5m structure pre-screen -> cap deep finalists -> trades/orderbook/derivatives/snapshots -> cross-venue validation -> rank -> one A+/watchlist/no setup.

RED fake-provider tests must prove rejected symbols do not incur deep calls, non-BTC can win, one provider/symbol failure does not abort the scan, and no qualifying setup returns `NO A+ SETUP` rather than forced entry.

Run:
```bash
npm test -- --run test/scanner-runtime.test.ts
npm test
npm run typecheck
```
Targeted run RED first; final suite GREEN. Use bounded concurrency and per-symbol error capture.

Commit:
```bash
git add crypto-research-gateway/src/scanner/scanner.ts crypto-research-gateway/src/research.ts crypto-research-gateway/test/scanner-runtime.test.ts
git commit -m "feat: orchestrate market-wide A+ research scan"
```

---

## Task 9 — Read-only HTTP + MCP surface

**Files**
- Modify `crypto-research-gateway/src/server.ts`
- Modify `crypto-research-gateway/src/mcp/server.ts`
- Modify `crypto-research-gateway/test/http.test.ts`
- Modify `crypto-research-gateway/test/mcp.test.ts`
- Modify `crypto-research-gateway/test/gateway-contract-integration.test.ts`

Add:
- `POST /research/scan`
- read-only MCP tool `market_a_plus_scan`
- `/health` scanner authority + scan venues
- `/capabilities` remains read-only.

Response state is exactly `A+ LIVE CANDIDATE | WATCHLIST | NO A+ SETUP`; when a candidate exists include symbol, direction, selected venue, executable price/age, trigger, entry zone, stop, targets, RR, rationale, invalidation, cross-venue summary, freshness/provenance. Always include scanner authority and research-only boundary.

RED tests: no symbol required by default, optional symbol list bounded, invalid input 400, MCP adds only read-only scanner tool, data contract cannot escalate execution authority.

Run:
```bash
npm test -- --run test/http.test.ts test/mcp.test.ts test/gateway-contract-integration.test.ts
npm test
npm run typecheck
npm run build
```
Targeted run RED first; final suite/build GREEN. Existing `market_execution_quote` semantics must remain unchanged.

Commit:
```bash
git add crypto-research-gateway/src/server.ts crypto-research-gateway/src/mcp/server.ts crypto-research-gateway/test
git commit -m "feat: expose read-only multi-coin A+ scan API"
```

---

## Task 10 — Retrieval metadata, docs, CI and full verification

**Files**
- Modify generated `AI_SKILL_LIBRARY/v4/index/retrieval_index.yaml`
- Modify `crypto-research-gateway/README.md`
- Modify `.github/workflows/zero-local-cloud-runtime.yml`
- Modify `tests/test_zero_local_manifest.py` if needed for bounded scanner-smoke assertions

CI must test only a bounded sample such as BTCUSDT/ETHUSDT/SOLUSDT, not an unbounded market scan. Assert scanner response is research-only, state vocabulary is valid, no production execution permission exists, and existing venue-bound quote smoke remains intact.

If manifest assertion changes, run RED before workflow implementation:
```bash
python -m unittest discover -s tests -p 'test_zero_local_manifest.py' -v
```

Regenerate retrieval index from source, never by hand:
```bash
python AI_SKILL_LIBRARY/v4/tools/build_retrieval_index.py --write --root .
python AI_SKILL_LIBRARY/v4/tools/build_retrieval_index.py --check --root .
```
Expected: `RETRIEVAL_INDEX=WRITTEN ...` then `RETRIEVAL_INDEX=FRESH ...`.

Full verification from repo root:
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
(cd crypto-research-gateway && npm test && npm run typecheck && npm run build)
python AI_SKILL_LIBRARY/v4/tools/ci_validate.py --source-sha "$(git rev-parse HEAD)"
```
Expected: all tests/validators/build PASS and `CI_VALIDATE=PASS failures=0`.

README must clearly distinguish broad A+ research scan from legacy venue-bound quote verification and state that neither endpoint places orders.

Commit:
```bash
git add AI_SKILL_LIBRARY/v4/index/retrieval_index.yaml crypto-research-gateway/README.md .github/workflows/zero-local-cloud-runtime.yml tests/test_zero_local_manifest.py
git commit -m "ci: validate multi-coin A+ scanner boundaries"
```

---

## Task 11 — Exact-head review + draft PR; stop before production

- Compare implementation head to `main`; inspect changed-file scope.
- Search diff for credentials, write/order tools, live-switch expansion, accidental BTC state reset/removal.
- Require exact final head SHA to pass all GitHub-native checks.
- Open a draft PR to `main` documenting: broad USDT-perp scan authority, BTC/Bybit-only production order authority, no write/fund-moving tools, no profitability guarantee.
- Fix only demonstrated review defects and add regression tests.
- Mark ready only after exact-head verification.
- **STOP before merge.** `main` auto-deploys Railway; ask for explicit production deployment approval before merge/deploy.

Evidence to report before asking for deploy approval:
- exact branch/head SHA;
- changed files;
- unit/typecheck/build results;
- Brain/authority/retrieval validation;
- PR number/mergeability;
- explicit confirmation production remains unchanged.

---

## Post-approval production gate — not authorized yet

Only after separate explicit production approval:
1. merge with expected-head protection;
2. verify canonical `main` SHA;
3. wait for exact-main Railway deployment success;
4. verify `/health` exact SHA + scanner authority;
5. verify `/capabilities` includes `market_a_plus_scan` and still has no write tools;
6. run bounded production scanner smoke plus existing Bybit/Binance quote smoke;
7. prove a non-BTC symbol can be evaluated while `productionExecutionAuthority=false`;
8. report scanner as research-only unless/until a later execution migration is separately approved.

No commit, PR, test pass, or source-level change alone is sufficient to claim the scanner is deployed or LIVE.