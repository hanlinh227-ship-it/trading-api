# NO-CUT INTRADAY ALL-PASS V73

Updated: 2026-08-17 UTC+7

## Locked user target
- No CUT.
- No NO-TRADE day.
- 1 to 3 trades per symbol per day; current passing development maps use exactly 1/day.
- RR only 1:1 or 1:2; current passing maps use 1:1.
- Every Forex pair and every Crypto symbol must have development WR >=80%.
- Every symbol has its own method and news/context profile.

## Development result
- Forex: 28/28 PASS; minimum per-pair WR 80.00%.
- Crypto: 61/61 PASS; minimum per-coin WR 80.22%.
- H1 is canonical for Forex and 59 crypto symbols. TON/IP use their own 4H regime method because full H1 spot history was unavailable in the common source.
- All results count TIMEOUT as a non-win and same-bar TP+SL as SL.

## Canonical sources
- Forex: V64 base + V66 targeted refinement.
- Crypto: V69 static passes + V70 observable regime routers + V71 HBAR/TAO special H1 + V72 TON/IP special 4H.
- Exact frozen methods, routers, actions, statistics and news profiles are in `data/nocut_intraday_allpass_v73.json`.

## Integrity
**This is an exposed-development all-pass checkpoint, not untouched OOS validation.** May-Jul was used to search/refine the maps. The next integrity step is to freeze V73 unchanged and test on independent history before calling it robust/live-proven.
