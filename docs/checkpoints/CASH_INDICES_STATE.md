# CASH INDICES STATE

Updated: 2026-08-17 UTC+7

## Hard instrument rule
Default index requests mean CASH indices unless the user explicitly asks for futures.

Never substitute NQ/ES/MNQ/MES prices for cash-index prices.

## Canonical aliases
- NAS100 / USTEC / NASDAQ100 -> Nasdaq-100 Cash -> `NDX`
- US500 / SP500 / SPX500 -> S&P 500 Cash -> `SPX`
- US30 / DJI / DOW -> Dow Jones Cash -> `DJI`
- JP225 / N225 / NIKKEI / NIKKEI225 -> Nikkei 225 Cash -> `N225`
- DAX / DEX / DE40 / GER40 -> DAX Cash -> `DAX`
- UK100 -> FTSE cash index where supported
- FR40 -> CAC cash index where supported
- HSI, VIX, RUT only when specifically requested and provider mapping is verified.

NQ/ES/MNQ/MES remain blocked in cash-index resolver paths to prevent silent cash/futures confusion.

## Data policy — Grow 55
Twelve Data Grow 55 is the primary aggregated path for supported cash indices through the Worker.

Before using a value:
- verify the exact cash-index mapping;
- verify current provider entitlement/support;
- verify market/session state;
- distinguish latest `/price` fetch time from a true exchange/venue quote timestamp;
- never invent bid/ask or spread when the feed does not provide them.

If the provider cannot deliver the exact requested cash index, return `DATA_BLOCK` or identify the limitation. Do not substitute futures, ETFs or CFDs unless the user explicitly requests that alternate instrument.

## Analysis workflow
- D1/H4: macro regime, major trend and liquidity.
- H1: intraday bias and current structural leg.
- M15: setup/location, sweep, displacement, breakout/retest, VWAP/volume context where reliable.
- M5: execution trigger/confirmation.
- latest `/price`: current aggregated price reference.
- M1: recent-candle timing/reference only; not a replacement for final `/price`.

## Macro drivers
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

## Technical stack
- structure/liquidity first;
- EMA20/50/200 as trend/pullback context;
- RSI14 for momentum/exhaustion;
- ATR14 for volatility/SL buffer;
- VWAP and Volume Profile when reliable data exists;
- SMT/correlation comparisons only when exact related instruments are correctly identified.

## Entry logic
A strong MARKET setup requires HTF/intraday alignment plus an M15 location and M5 confirmation. Avoid chasing extended displacement.

Typical triggers:
- sweep/reclaim;
- breakout/retest;
- controlled pullback to VWAP/EMA/structure;
- clear rejection from liquidity/SR.

If exact executable quote timestamp/spread is required but unavailable from the aggregated feed, obtain platform confirmation or return `DATA_BLOCK` rather than call the setup MARKET-ready.

## SL / TP
SL is defined by structural invalidation; ATR is only a buffer. TP is tied to meaningful liquidity, prior high/low, value-area boundary, VWAP extension or another defensible structural objective. Do not impose one fixed point distance/RR on every index.
