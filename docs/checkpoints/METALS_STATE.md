# METALS STATE — XAUUSD / XAGUSD

Updated: 2026-08-17 UTC+7

## Scope and identity
Primary discretionary metal symbols:
- XAUUSD = spot gold versus USD;
- XAGUSD = spot silver versus USD.

Keep spot metals separate from futures:
- XAUUSD is not automatically GC futures;
- XAGUSD is not automatically SI futures.

Never silently substitute COMEX futures, ETFs or broker CFDs for the requested spot instrument.

## Data policy — Grow 55
Twelve Data Grow 55 is the primary aggregated path for supported spot/commodity analysis through the Worker.

For a deep symbol review the current single-symbol pipeline retrieves:
- D1/H4/H1/M15/M5 analysis;
- latest `/price`;
- M1 recent-candle reference.

The latest `/price` is an aggregated reference. Worker fetch time is not treated as a verified broker quote-tick timestamp, and bid/ask/spread must not be invented when the feed does not provide them.

If strict MARKET execution requires exact broker spread/timestamp, obtain platform/venue confirmation or return `DATA_BLOCK`.

## Timeframe workflow
- D1/H4: macro regime, major structure/liquidity and premium/discount.
- H1: intraday bias and structural leg.
- M15: setup construction and key intraday location.
- M5: trigger/confirmation.
- M1: recent timing/reference only.

## Technical toolkit
Use structure first, indicators second:
- support/resistance and swing structure;
- liquidity sweeps;
- displacement / MSS;
- FVG / imbalance and breakout-retest/reclaim;
- EMA20/50/200 for trend/pullback context;
- RSI14 for momentum/exhaustion;
- ATR14 for volatility and SL floor;
- VWAP when reliable intraday data exists;
- Volume Profile / POC / VAH / VAL when a reliable volume source exists.

## Gold-specific context
For XAUUSD always consider:
- DXY;
- US Treasury yields, especially US10Y and real-yield direction when available;
- Fed/rate expectations;
- US CPI/PCE/NFP/jobs/retail/growth;
- geopolitical safe-haven demand;
- major risk-on/risk-off shifts.

Do not infer direction from one macro variable alone; require price-structure confirmation.

## Silver-specific context
XAGUSD shares precious-metal drivers with gold but has stronger industrial/cyclical sensitivity and often higher volatility. Use structure/ATR appropriate to silver rather than copying gold distances. Gold/silver relative behavior is context, not a standalone signal.

## MARKET setup standard
A strong setup normally requires:
1. exact spot instrument identity;
2. D1/H4/H1 bias not materially conflicting;
3. meaningful M15 location rather than an extended chase;
4. M5 sweep/reclaim, rejection, breakout-retest or displacement-pullback confirmation;
5. no unresolved top-tier event directly invalidating timing;
6. final current price refresh;
7. venue/platform execution confirmation when exact spread/timestamp is required.

## SL / TP
- structural invalidation defines SL;
- ATR is only a minimum volatility buffer;
- TP targets meaningful liquidity/SR/VAH-VAL/POC or another defensible structural objective;
- calculate RR only after SL and target are structurally defined.

For prop-firm trading, firm-specific daily/max-drawdown constraints override generic sizing guidance.
