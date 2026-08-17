# LIVE SYMBOL ANALYSIS V74

Updated: 2026-08-18 UTC+7
Status: CURRENT live-analysis / execution playbook layered on frozen V73; V75 supplies fast data and V76 may add a statistically gated entry method without rewriting V74 evidence.

## Purpose

V73 remains the frozen exposed-development statistical prior. V74 converts that prior into a live decision process for 28 Forex pairs + 61 Crypto identities without re-optimizing V73.

Canonical implementation:
- `scripts/live_symbol_analysis_v74.py`
- validation: `.github/workflows/validate-live-v74.yml`

V74 prevents automatic use of `signalHourUTC`, blind `DUAL_FADE`, missing HTF context, missing news, stale/mismatched prices, and transfer of V73 development WR into a live-WR claim.

## Mandatory live-analysis order

1. Resolve exact instrument / venue / contract.
2. Refresh current data and verify what each timestamp represents.
3. Reject stale, mismatched or unverifiable execution data as `DATA_BLOCK`.
4. Refresh current symbol-specific news/context.
5. Establish D1/H4 draw-on-liquidity, regime and premium/discount.
6. Read H1 structure using only information observable at that timestamp.
7. Read frozen V73 prior/router without optimizing it from today's outcome.
8. Treat V73 `signalHourUTC` as an observation anchor, never an automatic order time.
9. Require M15 tradable location: sweep, breakout-retest, FVG/imbalance retest or clean reclaim.
10. Require a close-confirmed M5 trigger/retest for strict execution.
11. Put structural invalidation first; ATR is only a volatility floor.
12. RR1 is default. RR2 requires >=2.2R clean room after costs and no opposing HTF level before 2R.
13. Refresh final execution data immediately before MARKET.
14. Record setup/context/timestamp/spread/slippage/outcome for unchanged forward validation.

## V73 interpretation

- V73 family = historical setup prior, not standalone live entry.
- V73 entry mode = geometry prior, not automatic execution.
- `DUAL_FADE` never authorizes both directions blindly.
- V73 remains frozen and its development WR is not a future/live guarantee.

## Current data architecture — V75

### Forex / supported non-crypto

Canonical source is direct Twelve Data REST from GitHub Actions through `scripts/twelvedata_market.py` (`V4-TWELVEDATA-FAST-STRICT`). The old Cloudflare shorthand Worker is deprecated for canonical decisions.

V75 obtains D1/H4/H1/M15/M5 in parallel, uses closed candles for indicators/structure, validates exact `meta.symbol` + `meta.type`, uses `/quote.last_quote_at` as provider time, and accepts `/price` only after identity proof.

Important distinctions:
- provider quote time != our fetch time;
- latest aggregated `/price` != executable broker quote;
- Twelve Data bid/ask is not fabricated;
- hard non-crypto stale block is >65 seconds;
- Forex V74 MARKET review target remains <=30 seconds when a true provider timestamp exists;
- executable broker/venue spread still requires venue confirmation.

Fast single-symbol artifact: `data/decision.json`.
Fast Forex-universe artifact: `data/forex-fast.json`.

### Crypto

Exchange-native REST is primary for execution precision (OKX/Binance/Bybit where supported). Require exact token/instrument/venue, exchange timestamp and real bid/ask. Strict quote-age target is <=10 seconds.

Fast Crypto-universe artifact: `data/crypto-fast.json`.

Twelve Data may enrich analysis but never replaces venue-specific execution data when venue precision matters.

## Forex context

Every pair compares both currency legs independently.

- USD: Fed/FOMC, CPI/PCE/labor, Treasury yields/DXY, USD liquidity/risk.
- EUR: ECB, Eurozone CPI/PMI, Germany growth/industry, EU fiscal/political risk.
- GBP: BoE, CPI/wages/jobs, GDP/retail, gilt/fiscal risk.
- JPY: BoJ, MoF intervention, CPI/wages, JGB yields/global risk.
- CHF: SNB, CPI, safe-haven flows, European risk.
- CAD: BoC, CPI/jobs/GDP, WTI, US-Canada differential.
- AUD: RBA, CPI/jobs, China data, iron ore/global risk.
- NZD: RBNZ, CPI/jobs, China growth, dairy/commodity/global risk.

Around top-tier scheduled releases, do not enter blindly immediately before the event; refresh context after the event and require confirmed structure/retest.

## Crypto context

All 61 symbols use explicit identities and covered driver profiles; no live generic `OTHER` fallback.

A review combines, when relevant: official project announcements, unlock/supply/staking/buyback changes, spot/perp volume/OI/funding, exchange/on-chain flows, BTC-relative strength, BTC dominance/breadth and sector drivers. If a catalyst has already displaced price materially, avoid chasing and wait for a valid pullback/retest.

## V76 compatibility

V76 is an optional entry/execution research layer. It may select a statistically validated per-symbol entry archetype after V75 candidate/context, but it may not bypass any V74 integrity gate.

If a V76 method is not OOS-promoted, the method is research-only and cannot authorize a live entry. V76 historical research also cannot replace current news or execution-venue confirmation.

## Execution integrity

For MARKET distinguish:
1. latest reference/aggregated price;
2. true provider/venue timestamp;
3. executable venue bid/ask spread.

Requirements when applicable:
- exact symbol/instrument/venue;
- market-open state;
- verified timestamp;
- bid/ask/spread;
- estimated round-trip spread/slippage <=0.10R;
- Crypto quote age <=10s;
- Forex quote age <=30s when a real timestamp exists.

If required execution fields cannot be verified, return `DATA_BLOCK`/`NO_ENTRY` rather than fabricate a live order.

## 1–3 trades/day rule

- Trade #1: strongest confirmed setup in preferred active window.
- Trade #2: only after #1 is closed/risk-neutral and a new independent liquidity/structure event occurs.
- Trade #3: only in a later independent session/regime with A-grade confirmation; never revenge/averaging.
- After two losses, do not force a third recovery trade.
- Mandatory fallback remains subject to data integrity and the current entry gate; it never overrides stale/wrong-instrument protection.

## Assessment

V74 remains the live operating authority. It is not statistically proven by the V73 development WR. Any new V76 rule must carry its own DEV/validation/untouched-OOS evidence and, if changed later, must be versioned rather than rewriting historical evidence.
