# EURUSD V32 — PRE-2024 LOCK

Locked before any EURUSD 2024 validation data is fetched.

## Daily intraday requirement
- Symbol: EURUSD only.
- One filled trade every Forex weekday.
- This pair does not compete against other Forex symbols.
- If LIMIT does not fill within expiry, same-day MARKET fallback is compulsory.

## Frozen method
- Analysis family: BREAKOUT from EURUSD's own recent H1 range/price path.
- Decision observation: 08:00 UTC.
- Planned RR: 1:1.
- Initial entry: pullback LIMIT at 0.70 ATR from signal close in predicted direction.
- LIMIT expiry: 3 H1 bars; if not filled, MARKET fallback at expiry close.
- Structural swing lookback: 12 H1 bars.
- ATR risk floor: 3.0 ATR.
- Maximum hold: 30 H1 bars.
- Management review starts H+3.
- CUT when current R <= -0.25, or price closes through EMA20 against thesis while current R < +0.10, or favorable progress remains below +0.25R by the review condition.
- CUT is excluded from TP/(TP+SL) WR, but included in total managed expectancy.

## Development-only evidence used to select this method
Jan-Jun 2025 block was already development data. The frozen candidate showed on the four subsequent month blocks:
- March: 9 TP / 1 SL / 11 CUT = 90.00% TP/SL WR, +0.263R mean.
- April: 4 TP / 0 SL / 18 CUT = 100.00% TP/SL WR, +0.041R mean.
- May: 5 TP / 1 SL / 16 CUT = 83.33% TP/SL WR, +0.042R mean.
- June: 4 TP / 0 SL / 17 CUT = 100.00% TP/SL WR, +0.076R mean.
These are NOT final validation because they were inspected during development.

## Untouched validation rule
Only after this file is committed may a new 2024 EURUSD H1 month be fetched.
PASS requires:
- every Forex weekday has one filled trade;
- TP/(TP+SL) >=80%;
- at least 5 TP+SL resolved trades in the month;
- positive mean managed R including CUT;
- planned RR remains 1:1;
- no parameter changes after the 2024 data is fetched.
