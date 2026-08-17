# TWELVE DATA GROW 55 — MARKET DATA POLICY

Updated: 2026-08-17 UTC+7

This policy is active for all future live market analysis in the Trading project. It supplements V74 and does not change or optimize the frozen V73 backtest prior.

## PLAN CAPACITY

Current Twelve Data plan: **Grow 55**.

Operational assumptions:
- 55 API credits per minute;
- API quota resets each minute;
- paid plans have no daily API limit;
- 8 trial WebSocket credits on Grow;
- full WebSocket access is a Pro-level capability;
- standard `/time_series` usage is 1 API credit per symbol;
- batch requests reduce request overhead but credits still follow the requested work.

Do not design the live system around WebSocket while the account remains Grow 55. Use REST efficiently and preserve a small execution-refresh reserve.

## CORE PRINCIPLE

**Maximize information per credit, not credits burned.**

Use a staged pipeline:
1. broad universe scan;
2. rank candidates;
3. deep multi-timeframe analysis only on finalists;
4. refresh latest executable data immediately before any MARKET decision.

Compute EMA/RSI/ATR and derived features locally from OHLC whenever possible rather than spending separate indicator endpoint credits.

## FOREX

Universe: 28 crosses formed from USD, EUR, GBP, JPY, CHF, CAD, AUD and NZD.

Grow 55 normal scan budget:
- 28 broad scan calls: ~28 credits;
- Top 3 deep analysis, D1/H4/H1/M15/M5: ~15 credits;
- Top 3 final refresh: ~3 credits;
- normal estimated total: ~46 credits;
- reserve: ~9 credits for retries/live overlap.

The old Basic-plan fixed `sleep 65` after every group is deprecated. Only wait for quota reset after exceptional failures that would exceed the reserve.

Final Forex MARKET decision still follows V74: exact pair, fresh quote <=30s, bid/ask/spread when available, both-currency macro/news, D1/H4/H1 structure, M15 location, M5 close-confirmed MSS/displacement + retest, structural SL, RR 1:1 default and 1:2 only with clean room.

## CRYPTO

For live execution price, exchange-native data remains primary. Use Binance / OKX / Bybit as appropriate and verify token, quote currency, instrument type, venue, bid/ask and timestamp. Target freshness <=10s.

Twelve Data is an enrichment/cross-check source for crypto history, additional OHLC and multi-market context when useful. Never replace an exchange-specific execution quote with an aggregated quote when venue precision matters.

## FUTURES / COMMODITIES

Grow includes commodities market data. Use Twelve Data when the exact requested futures/commodity instrument is available and verified.

Before use, resolve exact symbol/contract or continuous-contract identity, exchange mapping, timestamp and market state. Never substitute cash index and futures instruments for each other.

For MNQ/MES keep the dedicated Futures workflow: compare both contracts, structural SL first, then micro-contract sizing. User risk framework remains approximately $500 SL / $1,500 TP unless changed.

If the exact CME contract/feed cannot be verified with Twelve Data, use a more authoritative futures source rather than a proxy.

## CASH INDICES

Cash indices remain separate from futures. Use actual cash-index data only after symbol identity is verified. Never silently proxy NAS100/US500 cash with NQ/ES futures.

Use D1/H4/H1 structure, M15 location, M5 trigger, current cash price/timestamp, session state and index-specific news/macro context.

## METALS

XAUUSD/XAGUSD remain in the structure-first metals module. Grow commodity data may enrich spot/commodity history and current data when identity is verified. Do not conflate spot gold with COMEX futures.

## NEWS / CONTEXT

Twelve Data is a market-data source, not the sole news source. Every live analysis also refreshes relevant current context: central banks, macro releases, yields/rates/DXY, commodity drivers, regulatory/project-specific crypto news, geopolitical risk and session/exchange state.

## DATA INTEGRITY

If exact symbol, venue/contract, timestamp, market state or sufficiently fresh executable price cannot be verified, return `DATA_BLOCK`. Never label stale/cached data as live.

## CURRENT IMPLEMENTATION

Canonical Forex workflow: `.github/workflows/scan-forex.yml`

Grow 55 implementation:
- Stage A: parallel broad scan of 28 pairs;
- Stage B: D1/H4/H1/M15/M5 deep analysis of Top 3;
- Stage C: refresh all Top 3 before final V74 review;
- routine Basic-plan 65-second waits removed;
- conditional quota-reset wait retained only for exceptional failure counts.

This workflow produces candidates for V74 review. It never bypasses required M15/M5 execution confirmation.
