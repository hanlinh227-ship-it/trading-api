# TWELVE DATA GROW 55 — MARKET DATA POLICY

Updated: 2026-08-17 UTC+7

This policy is active for current live Trading analysis. It supplements V74 and does not alter the frozen V73 statistical prior.

## PLAN CAPACITY

Current Twelve Data plan: **Grow 55**.

Operational assumptions used by the repository:
- 55 API credits per minute;
- quota resets every minute;
- paid plan has no daily API cap in the current provider policy;
- REST is the primary integration path for this plan;
- compute EMA/RSI/ATR and derived features locally from fetched OHLC whenever possible.

Provider pricing/entitlement can change; verify current provider documentation before relying on plan limits in the future.

## CORE PRINCIPLE

**Maximize decision-quality information per credit, not credits burned.**

Pipeline:
1. broad scan;
2. local ranking;
3. deep multi-timeframe analysis only on finalists;
4. final latest-price refresh;
5. venue/broker confirmation when executable spread or exact quote timestamp is required.

## FOREX — 28 PAIRS

Canonical workflow: `.github/workflows/scan-forex.yml`.

Normal Grow 55 allocation:
- 28 broad scans: ~28 credits;
- Top 3 deep D1/H4/H1/M15/M5 analyses: ~15 credits;
- Top 3 `/price` refreshes: ~3 credits;
- normal estimated total: ~46 credits;
- reserve: ~9 credits.

The old Basic-plan pattern of fixed `sleep 65` after each seven-pair group is deprecated. Waiting is used only after exceptional failures when an immediate retry would exceed the remaining minute budget.

### Forex final-price rule
Use Twelve Data `/price` as the latest aggregated price reference.

Do **not** infer information that `/price` does not provide:
- Worker `generatedAt` is our fetch time, not a broker quote-tick timestamp;
- do not fabricate bid/ask;
- do not fabricate spread;
- do not label a price MARKET-ready solely because `/price` was fetched moments ago.

For a strict MARKET order, verify broker/venue timestamp and executable spread when those fields materially affect entry integrity. V74 target quote age is <=30 seconds when a true quote timestamp exists.

M1 `/refresh` may be used as recent-candle/reference context, but its candle close is not substituted for the final `/price` value.

## SINGLE-SYMBOL NON-CRYPTO

Canonical workflow: `.github/workflows/fetch-market.yml`.

For a requested Forex/metals/index/supported non-crypto symbol the workflow fetches in parallel:
- full D1/H4/H1/M15/M5 analysis;
- latest `/price`;
- M1 reference/context.

This uses the same `twelvedata-api` concurrency lock as the Forex universe scan so the two paths cannot unintentionally collide inside the 55-credit minute budget.

## CRYPTO

For final execution precision, exchange-native data remains primary:
- Binance;
- OKX;
- Bybit fallback where appropriate.

Requirements:
- verify exact token identity;
- verify quote currency/instrument type;
- verify venue;
- use exchange bid/ask and exchange timestamp when available;
- V74 target quote age <=10 seconds.

Twelve Data may enrich or cross-check crypto history and broader market context when useful, but an aggregated quote must not replace an exchange-specific execution quote when venue precision matters.

## FUTURES / COMMODITIES

Twelve Data may be used only after exact instrument identity is verified.

Before relying on the value, resolve:
- futures versus cash/spot;
- contract/front-month/continuous identity;
- exchange/venue mapping;
- market state;
- timestamp semantics.

For the NQ/ES system:
- execution preference is MNQ/MES;
- compare Nasdaq and S&P structure/SMT as needed;
- structural SL first, then contract sizing;
- if Twelve Data/Worker cannot prove the exact CME contract/feed, use a more authoritative futures feed or the user's platform price.

Never proxy NDX/SPX cash as NQ/ES futures.

## CASH INDICES

Cash indices remain separate from futures.

Examples:
- NAS100/USTEC/NASDAQ100 -> NDX cash;
- US500/SP500/SPX500 -> SPX cash;
- US30/DOW -> DJI cash;
- JP225/NIKKEI -> N225 cash.

Only use a cash value after symbol mapping and provider entitlement are verified. Never silently substitute a futures/CFD value.

## METALS

- XAUUSD/XAGUSD spot remain separate from GC/SI futures.
- use structure-first analysis;
- incorporate DXY, Treasury yields/rates, inflation/labor data and geopolitical risk as relevant;
- exact instrument identity is required before calling a value live.

## NEWS / CONTEXT

Twelve Data is a market-data source, not the sole news source.

Every live analysis also refreshes relevant current context, including as applicable:
- central banks and rates;
- CPI/PCE/jobs/growth;
- Treasury yields/DXY;
- commodity drivers;
- geopolitical risk;
- official crypto project/regulatory catalysts;
- exchange/session state.

## DATA INTEGRITY

If exact symbol/venue/contract, market state, required quote freshness or executable spread cannot be verified, return `DATA_BLOCK` rather than fabricate a MARKET-ready order.

A current aggregated price, a true quote timestamp and an executable bid/ask spread are three different things and must remain separate in all outputs.
