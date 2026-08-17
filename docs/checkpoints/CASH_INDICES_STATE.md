# CASH INDICES STATE

Updated: 2026-08-17 UTC+7

## HARD INSTRUMENT RULE

Default index requests mean **cash indices** unless the user explicitly asks for futures.

Never substitute NQ/ES/MNQ/MES, ETFs or CFDs for the requested cash index without explicit user instruction.

## CURRENT TWELVE DATA STATUS

The 2026-08-17 strict audit proved that the current Grow55/core-endpoint combination does **not** safely expose the requested cash indices through shorthand symbols:
- `NAS100 -> NDX` produced an unrelated value around `19.4`;
- `SPX` produced an unrelated value around `0.085`;
- `N225` did not provide a usable 5-timeframe/current quote path;
- exact DAX cash access was not proven through the current core endpoints.

These values must never be called NAS100/SPX/Nikkei/DAX live prices.

Canonical strict client `scripts/twelvedata_market.py` therefore deliberately returns `DATA_BLOCK` for the current cash-index alias family until exact provider entitlement/instrument identity can be proven.

## CANONICAL ALIASES — IDENTITY ONLY

- NAS100 / USTEC / NASDAQ100 / NDX -> Nasdaq-100 cash index
- US500 / SP500 / SPX500 / SPX -> S&P 500 cash index
- US30 / DJI / DOW -> Dow Jones cash index
- JP225 / N225 / NIKKEI / NIKKEI225 -> Nikkei 225 cash index
- DAX / GDAXI / DE40 / GER40 -> DAX cash index
- UK100 -> FTSE cash index
- FR40 -> CAC cash index
- HSI / VIX / RUT only after exact provider mapping is proven

These aliases describe the **requested identity**; they do not authorize blindly calling a same-text provider ticker.

## LIVE DATA POLICY

For cash index analysis:
1. exact index identity must be verified;
2. quote timestamp must be attributable to that index/feed;
3. market/session state must be known;
4. futures/ETF/CFD proxies are forbidden unless explicitly selected;
5. if no exact feed is available, return `DATA_BLOCK` and use an authoritative cash-index source rather than fabricate data.

The old Cloudflare Worker shorthand mapping is not a trusted execution source for cash indices after the NDX/SPX collision audit.

## ANALYSIS WORKFLOW WHEN AN EXACT FEED EXISTS

- D1/H4: macro regime, major trend and liquidity;
- H1: intraday bias/current structural leg;
- M15: setup/location, sweep, displacement, breakout/retest, VWAP/volume context where reliable;
- M5: execution trigger/confirmation;
- final exact cash quote: refresh immediately before any MARKET decision.

## MACRO DRIVERS

US indices:
- Fed/rate expectations;
- US Treasury yields, especially US10Y;
- CPI/PCE/NFP/jobs/growth;
- major tech/earnings context for Nasdaq when material;
- risk sentiment/geopolitical shocks.

Nikkei:
- JPY;
- BoJ/MoF policy;
- Japan inflation/wages/growth;
- global risk and US-tech linkage where material.

European indices:
- ECB/euro-area macro;
- regional fiscal/political risk;
- global risk conditions.

## TECHNICAL / RISK RULES

Use structure/liquidity first, EMA20/50/200, RSI14, ATR14 and VWAP/Volume Profile only when reliable exact-instrument data exists. SL follows structural invalidation; TP follows defensible liquidity/structure. Do not impose one fixed point distance on every index.

A MARKET setup still requires HTF/intraday alignment + M15 location + M5 confirmation + exact execution quote integrity.
