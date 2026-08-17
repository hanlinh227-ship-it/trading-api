# LIVE SYMBOL ANALYSIS V74

Updated: 2026-08-17 UTC+7
Status: CURRENT live-analysis / execution playbook layered on frozen V73

## Purpose
V73 remains the frozen exposed-development backtest prior. V74 converts that prior into a live decision process for all 28 Forex pairs + 61 Crypto symbols without re-optimizing V73.

Canonical implementation:
- `scripts/live_symbol_analysis_v74.py`
- validation workflow: `.github/workflows/validate-live-v74.yml`
- first successful validation run: `32037184726`

## Why V74 was needed
V73 proved the requested development gate, but it was not yet a complete live-analysis method. In particular:
- `signalHourUTC` could be misread as an automatic entry time;
- `DUAL_FADE` could be misread as permission to place both sides blindly;
- live D1/H4/H1 -> M15/M5 confirmation was not encoded;
- transaction-cost/freshness gates were not encoded;
- trade #2/#3 rules were not encoded;
- 28/61 Crypto symbols could fall back to generic `OTHER` news drivers because V73 profile names did not match the original driver table;
- LIT was labeled with legacy `IDENTITY` context instead of current Lighter/perp-DEX context.

V74 fixes those live-layer issues while preserving V73's frozen statistical methods/results.

## V74 analysis order — EVERY live symbol
1. Verify exact instrument/venue, current bid/ask/price and timestamp.
2. Reject stale/mismatched data as `DATA_BLOCK`; never pretend stale data is live.
3. Refresh point-in-time symbol-specific news/context.
4. Establish D1/H4 draw-on-liquidity, trend/regime and premium/discount.
5. Read H1 structure and only observable router features.
6. Load the frozen V73 symbol action. Never optimize it with today's outcome.
7. Treat V73 `signalHourUTC` as a preferred observation anchor, not an automatic order.
8. Require M15 tradable location: sweep, breakout-retest, FVG/imbalance retest or clean reclaim.
9. Require M5 close-confirmed MSS/displacement + retest for execution.
10. Put structural invalidation/SL first; ATR is only a volatility floor.
11. RR defaults to 1:1. Promote to 1:2 only when >=2.2R clean room remains after estimated costs, HTF alignment exists and no major opposing level is before 2R.
12. Record setup, news/context, price timestamp, spread/slippage and TP/SL/TIMEOUT for forward validation.

## V73 geometry interpretation in live
- V73 family = setup archetype prior, not a standalone signal.
- V73 entryMode = geometry prior, not automatic execution.
- `DUAL_FADE` = two-sided historical geometry. In live, activate ONLY the side confirmed by D1/H4/H1 bias and M15/M5 trigger. Never place both sides blindly.
- Regime routers may only use point-in-time observable features. No future bars/news.

## Forex — per-pair live context
Every pair compares both currency legs independently.

USD: Fed/FOMC, CPI/PCE/labor, Treasury yields + DXY, global USD liquidity/risk.
EUR: ECB, Eurozone CPI/PMI, Germany growth/industry, EU fiscal/political risk.
GBP: BoE, CPI/wages/jobs, GDP/retail, gilt/fiscal risk.
JPY: BoJ, MoF intervention, CPI/wages, JGB yields/global risk.
CHF: SNB, CPI, safe-haven flows, European risk.
CAD: BoC, CPI/jobs/GDP, WTI, US-Canada rate/growth differential.
AUD: RBA, CPI/jobs, China data, iron ore/global risk.
NZD: RBNZ, CPI/jobs, China growth, dairy/commodity/global risk.

Session preference is pair-specific: Asia for JPY/AUD/NZD exposure, London for EUR/GBP/CHF, New York for USD/CAD, with London-New York overlap emphasized for USD crosses.

High-impact scheduled event rule: do not blindly enter immediately before a top-tier release. Re-score after the event and wait for the first confirmed M5 structure/retest. This delays execution; it does not secretly convert a valid market day into discretionary NO TRADE.

## Crypto — corrected per-symbol context
All 61 symbols have an explicit current identity and one of 35 covered live driver profiles. There is no `OTHER` fallback in V74.

Important identity corrections/audits:
- LIT = Lighter / Lighter Infrastructure Token; profile = PERP_DEX, not legacy Litentry identity.
- S = Sonic native token after Fantom -> Sonic migration.
- ASTER = Aster perp-DEX ecosystem.
- XPL = Plasma stablecoin-focused Layer 1.
- HBAR = Hedera enterprise/public-network context.
- NEAR = NEAR chain + chain-abstraction/AI ecosystem context.
- WLD = World/World ID/World Chain + token-distribution/regulatory context.

Every Crypto playbook combines:
- project/protocol official announcements;
- token unlock/supply/staking/buyback changes when relevant;
- fresh spot/perp volume, OI/funding, exchange and on-chain/whale flows;
- symbol/BTC relative strength;
- BTC dominance/breadth and broad crypto regime;
- sector-specific drivers (DeFi, L1, L2, meme, AI, RWA, perp-DEX, stablecoin L1, etc.).

News is confirmation/routing context. If a catalyst has already displaced price >1 ATR, wait for a pullback/retest instead of chasing.

## Freshness / execution gates
Forex:
- current quote target age <=30 seconds;
- exact pair + venue/source verified;
- market must be open;
- bid/ask and estimated costs required.

Crypto:
- current quote target age <=10 seconds;
- exact token/instrument + venue verified;
- bid/ask and estimated costs required.

Both:
- stale price forbidden;
- estimated round-trip spread/slippage target <=0.10R;
- if exact symbol/fresh price/executable spread cannot be verified, return `DATA_BLOCK` rather than fabricate a trade. `DATA_BLOCK` is a technical integrity failure, not discretionary NO TRADE.

## 1–3 trades/day rule
- Trade #1: strongest confirmed setup in the preferred active window.
- Trade #2: only after #1 is closed or risk neutralized AND a new independent liquidity event/structure occurs.
- Trade #3: only in a later independent session/regime with A-grade confirmation; never revenge/averaging.
- After two losses, do not force a third recovery trade; the daily minimum is already satisfied.
- If no A-grade setup has triggered by the final liquid window, V74 defines a mandatory fallback: frozen V73 prior + H1 close confirmation + M5 pullback/retest at 0.5x normal risk.

IMPORTANT: the fallback, trade #2/#3 logic, freshness/cost gates and M15/M5 confirmation are NEW V74 operational rules. They were not part of the V73 development WR and therefore need forward/OOS validation.

## Assessment
V74 is more logically suitable for live trading than directly executing V73 because it separates:
- statistical prior,
- live context,
- price-structure confirmation,
- execution quality,
- risk geometry.

However, V74 is NOT yet statistically proven live. The following still need validation before claiming the 80% development WR carries into live execution:
1. unchanged forward/OOS results with V73+V74 frozen;
2. real spread/slippage/fees;
3. event-delay effect around macro/news;
4. M15/M5 trigger hit-rate and missed-entry behavior;
5. mandatory fallback performance;
6. second/third trade performance by independent session.

Do not retune an untouched validation sample after seeing its result. If a live rule fails, create a later version and preserve the failed evidence.
