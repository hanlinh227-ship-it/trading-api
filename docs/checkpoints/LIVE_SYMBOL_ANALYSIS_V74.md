# LIVE SYMBOL ANALYSIS V74

Updated: 2026-08-17 UTC+7
Status: CURRENT live-analysis / execution playbook layered on frozen V73

## Purpose
V73 remains the frozen exposed-development statistical prior. V74 converts that prior into a live decision process for all 28 Forex pairs + 61 Crypto symbols without re-optimizing V73.

Canonical implementation:
- `scripts/live_symbol_analysis_v74.py`
- validation workflow: `.github/workflows/validate-live-v74.yml`
- first successful validation run: `32037184726`

## Why V74 exists
V73 is not a standalone live-entry engine. V74 prevents these errors:
- treating `signalHourUTC` as an automatic order time;
- treating `DUAL_FADE` as permission to place both sides;
- omitting D1/H4/H1 -> M15/M5 confirmation;
- omitting current symbol-specific news/context;
- ignoring price freshness and execution costs;
- confusing historical development WR with live expectancy;
- using old crypto identity/profile mappings in live analysis.

## Mandatory live-analysis order
1. Resolve exact instrument / venue / contract.
2. Refresh current market data and identify what the timestamp actually represents.
3. Reject mismatched/stale/unverifiable execution data as `DATA_BLOCK`.
4. Refresh current symbol-specific news/context.
5. Establish D1/H4 draw-on-liquidity, trend/regime and premium/discount.
6. Read H1 structure and only point-in-time observable router features.
7. Load the frozen V73 action without optimizing it from today's outcome.
8. Treat V73 `signalHourUTC` as a preferred observation anchor only.
9. Require M15 tradable location: sweep, breakout-retest, FVG/imbalance retest or clean reclaim.
10. Require M5 close-confirmed MSS/displacement + retest for strict execution.
11. Put structural invalidation/SL first; ATR is only a volatility floor.
12. Default RR1. Promote to RR2 only with >=2.2R clean room after estimated costs, HTF alignment and no major opposing level before 2R.
13. Refresh final execution data immediately before MARKET.
14. Record setup/context/timestamp/spread/slippage/outcome for unchanged forward validation.

## V73 interpretation
- V73 family = setup-archetype prior, not a standalone signal.
- V73 entryMode = historical geometry prior, not automatic execution.
- `DUAL_FADE` = two-sided historical geometry; live execution activates only the side confirmed by current bias + trigger.
- observable routers must use only data available at the decision timestamp.

## Current data architecture

### Forex / supported non-crypto
Twelve Data Grow 55 is the primary aggregated market-data path through the Cloudflare Worker.

For a deep symbol review the current pipeline can retrieve:
- D1/H4/H1/M15/M5 OHLC and locally derived indicators;
- latest Twelve Data `/price`;
- M1 recent-candle reference.

**Important:** a freshly fetched `/price` value is not automatically an executable broker quote. In this integration:
- Worker `generatedAt` is fetch time;
- it is not treated as a verified broker quote-tick timestamp;
- bid/ask must not be invented;
- spread must not be invented.

Therefore Forex target quote age <=30 seconds applies only when a true quote/venue timestamp is available. If broker/venue spread or timestamp is required and unavailable, obtain platform confirmation or return `DATA_BLOCK` for MARKET execution.

### Crypto
Exchange-native REST is primary for execution precision:
- Binance;
- OKX;
- Bybit fallback where appropriate.

Require exact token/instrument/venue, exchange timestamp, bid/ask and spread when available. Strict V74 target quote age <=10 seconds.

Twelve Data may be used as enrichment/cross-check, not as a replacement for exchange-specific execution data when venue precision matters.

## Forex context
Every pair compares both currency legs independently.

- USD: Fed/FOMC, CPI/PCE/labor, Treasury yields/DXY, global USD liquidity/risk.
- EUR: ECB, Eurozone CPI/PMI, Germany growth/industry, EU fiscal/political risk.
- GBP: BoE, CPI/wages/jobs, GDP/retail, gilt/fiscal risk.
- JPY: BoJ, MoF intervention, CPI/wages, JGB yields/global risk.
- CHF: SNB, CPI, safe-haven flows, European risk.
- CAD: BoC, CPI/jobs/GDP, WTI, US-Canada rate/growth differential.
- AUD: RBA, CPI/jobs, China data, iron ore/global risk.
- NZD: RBNZ, CPI/jobs, China growth, dairy/commodity/global risk.

Session preference remains pair-specific. Around top-tier scheduled releases, do not blindly enter immediately before the event; re-evaluate after the event and require confirmed structure/retest.

## Crypto context
All 61 symbols use current explicit identities and covered live driver profiles; no live `OTHER` fallback.

Important mappings include:
- LIT = Lighter / Lighter Infrastructure Token, PERP_DEX;
- S = Sonic native token after FTM -> S migration;
- ASTER = Aster perp-DEX;
- XPL = Plasma stablecoin-focused Layer 1;
- HBAR = Hedera enterprise/public-network context;
- NEAR = NEAR chain-abstraction/AI ecosystem;
- WLD = World/World ID/World Chain + distribution/regulatory context.

Every crypto review combines, when relevant:
- official project/protocol announcements;
- unlock/supply/staking/buyback changes;
- spot/perp volume, OI/funding and exchange/on-chain flows;
- symbol/BTC relative strength;
- BTC dominance/breadth and broad risk regime;
- sector-specific drivers.

If a catalyst has already displaced price materially, avoid chasing and wait for a structurally valid pullback/retest.

## Execution integrity
For MARKET execution distinguish:
1. latest aggregated/reference price;
2. true market quote timestamp;
3. executable venue bid/ask spread.

Do not merge these concepts.

Requirements when available/applicable:
- exact symbol/instrument/venue;
- market open state;
- verified quote timestamp;
- bid/ask/spread;
- estimated round-trip spread/slippage target <=0.10R;
- crypto quote age target <=10s;
- Forex quote age target <=30s when true quote timestamp exists.

If required execution fields cannot be verified, return `DATA_BLOCK` rather than fabricate a live order. `DATA_BLOCK` is a technical integrity failure, not a discretionary trading opinion.

## 1–3 trades/day rule
- Trade #1: strongest confirmed setup in the preferred active window.
- Trade #2: only after #1 is closed or risk-neutral and a new independent liquidity/structure event occurs.
- Trade #3: only in a later independent session/regime with A-grade confirmation; never revenge/averaging.
- After two losses, do not force a third recovery trade.
- If no A-grade setup has triggered by the final liquid window, V74 defines a mandatory fallback: frozen V73 prior + H1 close confirmation + M5 pullback/retest at 0.5x normal risk, **subject to data-integrity gates**.

The fallback, trade #2/#3 logic, freshness/cost gates and M15/M5 confirmation are V74 operational rules and were not part of V73's development WR.

## Assessment
V74 is the current live operating layer, but it is not yet statistically forward-proven. The historical >=80% V73 development result cannot be transferred as a live WR claim.

Required evidence remains unchanged forward/OOS collection with real spread/slippage, event delays, M15/M5 trigger behavior, fallback behavior and independent later-session trades. If a live rule later changes, create a new version rather than rewriting V74 evidence retrospectively.
