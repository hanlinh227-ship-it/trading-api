# CASH INDICES STATE

Updated: 2026-08-17 (UTC+7)

## Hard instrument rule
Default index requests mean CASH indices, not futures.
Never substitute NQ/ES/MNQ/MES prices for cash-index prices.

## Canonical aliases
- NAS100 / USTEC / NASDAQ100 -> Nasdaq-100 Cash -> `NDX`
- US500 / SP500 / SPX500 -> S&P 500 Cash -> `SPX`
- US30 / DJI / DOW -> Dow Jones Cash -> `DJI`
- JP225 / N225 / NIKKEI / NIKKEI225 -> Nikkei 225 Cash -> `N225`
- DAX / DEX / DE40 / GER40 -> DAX Cash -> `DAX`
- UK100 -> FTSE cash index where supported
- FR40 -> CAC cash index where supported
- HSI, VIX, RUT when specifically requested and supported.

NQ/ES/MNQ/MES must remain blocked in cash-index resolver paths to prevent silent cash/futures confusion.

## Data status
The project Twelve Data mappings support major cash-index aliases, but Twelve Data Basic entitlement has blocked some index data. Example: NDX/NAS100 returned an entitlement message requiring Grow/Venture. If the provider cannot deliver the requested cash index, report the limitation instead of fabricating a price from futures or CFDs.

## Analysis workflow
- D1/H4: macro regime, major trend and liquidity.
- H1: intraday bias and current structural leg.
- M15: setup, sweep, displacement, breakout/retest, VWAP/volume context where available.
- M5: entry confirmation/timing.
- M1/latest: execution refresh only.

## Macro drivers
For US indices, incorporate:
- Fed/rate expectations;
- US10Y/yield moves;
- CPI/PCE/NFP/jobs/growth data;
- major tech/earnings context for Nasdaq when material;
- risk sentiment and geopolitical shocks.
For Nikkei, incorporate JPY/BoJ/Japan policy and global risk sentiment.
For DAX/European indices, incorporate ECB/euro-area macro and regional/global risk conditions.

## Technical stack
- structure/liquidity first;
- EMA20/50/200 for trend/pullback context;
- RSI14 for momentum/exhaustion;
- ATR14 for volatility/SL buffer;
- VWAP and Volume Profile when reliable data exists;
- SMT/correlation comparison among related indices may be used when feed quality supports it.

## Entry logic
Preferred MARKET entry requires HTF/intraday alignment plus an M15/M5 trigger. Avoid chasing after extended displacement. Strong triggers include sweep/reclaim, breakout/retest, controlled pullback to VWAP/EMA/structure, and clear rejection from liquidity/SR.

## SL / TP
SL is defined by structural invalidation, with ATR only as a buffer. TP should be tied to the next liquidity pool, prior high/low, value-area boundary, VWAP extension or other defensible structural objective. Do not force the same points/RR on all indices.

## Existing E8/EA context
An earlier E8 index-bot foundation referenced broker symbols such as ASX.c, DAX.c, DOW.c, NIKKEI.c, NSDQ.c, SP.c and used separate prop-firm risk management. Treat those as broker/EA symbols and do not mix them with the canonical cash-index API aliases unless mapping is explicitly verified.

## Cross-chat continuation
Read `MASTER_TRADING_STATE.md`, this file, and `DATA_INFRA_STATE.md`. Verify exact cash symbol/provider entitlement before issuing any live price or MARKET entry.