# CRYPTO V36B — PRE-AUGUST LOCK

Locked: 2026-08-17 before any August crypto snapshot is fetched for this lineage.

## Integrity
- Scanner universe: all 61 configured crypto symbols.
- Development/walk-forward snapshot: `data/provider_snapshots/crypto_4h_feb_jul_2026.json` only.
- Snapshot coverage: 61/61 symbols (OKX + Gate + Kraken fallbacks).
- August data is NOT present in that snapshot and has NOT been evaluated by V36b at lock time.
- NO TRADE is allowed; new/listing-young symbols are scanned but cannot become candidates before required indicator warm-up exists.
- CUT is excluded from TP/SL WR but included in managed expectancy.

## Frozen execution
- mode: LIMIT
- planned RR: **1.0**
- structural SL + ATR floor: 0.65 ATR
- swing lookback: 5 x 4H bars
- max hold: 4 x 4H bars
- limit offset: 0.70 ATR
- limit expiry: 1 x 4H bar
- no management CUT before normal timeout in this locked candidate (`cutAfterBars4H = 0`)

## Frozen meta-label selector
- model: HistGradientBoosting
- depth: 3
- min samples leaf: 8
- probability threshold: 0.66
- BUY-vs-SELL probability margin: 0.16
- portfolio: Top 1 qualifying setup per UTC day across the full 61-symbol scan

## Pre-Aug expanding walk-forward
May 2026:
- 31 selected
- 22 TP / 6 SL / 3 CUT
- TP/SL WR 78.57%
- mean managed R +0.499

June 2026:
- 30 selected
- 23 TP / 5 SL / 2 CUT
- TP/SL WR 82.14%
- mean managed R +0.586

July 2026:
- 31 selected
- 21 TP / 4 SL / 6 CUT
- TP/SL WR 84.00%
- mean managed R +0.576

Combined May-Jul:
- **92 selected**
- **66 TP / 15 SL / 11 CUT**
- **TP/SL WR 81.48%**
- **mean managed R +0.553**
- CUT rate 11.96%
- 40 distinct symbols actually traded; all 61 were loaded/scanned, with NO TRADE for non-qualified or not-yet-warmed symbols.

## Promotion state
PRE-AUG TARGET PASSED. This is NOT final promotion. Parameters above are frozen before untouched August testing. If the untouched holdout fails, this lock is rejected and may not be changed and re-labelled as blind on the same exposed holdout.
