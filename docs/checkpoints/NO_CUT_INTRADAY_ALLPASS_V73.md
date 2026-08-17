# NO-CUT INTRADAY ALL-PASS V73

Updated: 2026-08-17 UTC+7
Status: CURRENT forced-daily intraday development checkpoint

## Locked target
- CUT is forbidden.
- NO TRADE day is forbidden.
- Each Forex pair / Crypto symbol must trade 1–3 times per day; the current frozen passing maps use exactly 1 trade/day.
- RR may only be 1:1 or 1:2; every current passing map uses RR1:1.
- Per-symbol development WR is TP / all simulated daily trades and must be >=80%.
- TIMEOUT is a non-win.
- If TP and SL are both touched inside the same OHLC bar, score SL conservatively.
- Each symbol owns its own entry method plus its own news/context profile.

## Final development gate
- Forex: **28/28 PASS**; minimum individual WR **80.00%**.
- Crypto: **61/61 PASS**; minimum individual WR **80.22%**.
- Forex uses H1.
- 59 Crypto symbols use H1.
- TON and IP intentionally use their own 4H method because full common-source H1 history was unavailable; this is a symbol-specific design, not an exclusion.

Last difficult Crypto symbols:
- HBAR: 87TP / 4SL / 0 timeout = 95.60%.
- TAO: 88TP / 3SL / 0 timeout = 96.70%.
- TON: 83TP / 6SL / 2 timeout = 91.21%.
- IP: 79TP / 11SL / 1 timeout = 86.81%.

## Frozen architecture
Forex:
- V64 base styles for pairs already >=80%.
- V66 targeted H1 refinement for the 11 V64 failures.

Crypto:
- V69 fixed H1 styles where a static per-coin rule already passed.
- V70 observable 00UTC regime routers for most V69 failures.
- V71 expanded H1 routers for HBAR and full-history TAO.
- V72 dedicated 4H routers for TON and IP.

Exact frozen methods, router trees, action definitions, statistics, timeframes and per-symbol news/context profiles live in:
- `data/nocut_intraday_allpass_v73.json`

Operational reader:
- `scripts/nocut_intraday_method_v73.py`

Hard-gate validator:
- `scripts/validate_nocut_v73.py`
- `.github/workflows/validate-nocut-v73.yml`

Canonical rebuild workflow:
- `.github/workflows/build-nocut-allpass-v73.yml`
- successful rebase-safe build run: `32032071403`.

Final operational validation:
- validation run: `32033371607`, job `95398145183` — PASS.
- confirmed 28 Forex + 61 Crypto, min WR 80.00% / 80.22%.
- confirmed frozen maps are exactly 1 trade/day.
- confirmed 89/89 instruments contain news/context profiles.
- confirmed 39 instruments use valid observable regime routers.
- canonical reader smoke-tested EURUSD and SOL.
- router/action smoke-tested BTC, HBAR, TAO, TON and IP with no missing action references.

## Live news/context rule
News is symbol-specific. Since a daily trade is mandatory, a news/event shock does **not** silently turn the day into NO TRADE. Instead it is used point-in-time to route/confirm the symbol's frozen execution geometry/regime. No historical news is fabricated where a point-in-time archive was unavailable.

## Integrity classification
**EXPOSED DEVELOPMENT ALL-PASS — NOT UNTOUCHED OOS.**
May–Jul 2026 was used to search/refine these maps and is therefore development data. It is correct to say the requested development target is met for 28/28 Forex + 61/61 Crypto. It is not correct to call these WR values a future/live guarantee.

Next integrity step: freeze V73 exactly as-is and test it unchanged on independent history/forward data. Do not retune that holdout before reporting it as validation.
