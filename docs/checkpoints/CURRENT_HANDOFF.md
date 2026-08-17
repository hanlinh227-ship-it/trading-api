# CURRENT HANDOFF — TRADING PROJECT

Updated: 2026-08-17 UTC+7

Read `MASTER_TRADING_STATE.md` first, then `NO_CUT_INTRADAY_ALLPASS_V73.md`, then `data/nocut_intraday_allpass_v73.json`.

# CURRENT USER-REQUIRED MODE — NO-CUT FORCED-DAILY V73
Rules are locked:
- no CUT;
- no NO TRADE day;
- 1–3 trades per Forex pair / Crypto symbol per day;
- frozen passing development maps currently use exactly 1/day;
- RR only 1:1 or 1:2; current passing methods use RR1:1;
- per-symbol WR must be >=80%;
- TIMEOUT is non-win;
- same-bar TP+SL = SL;
- every symbol must have its own analysis/entry method and its own news/context profile.

# Completed development target
## Forex
- **28/28 PASS**.
- Minimum individual WR: **80.00%**.
- H1 methods.
- V64 base + V66 targeted refinement for 11 original V64 failures.

## Crypto
- **61/61 PASS**.
- Minimum individual WR: **80.22%**.
- 59 symbols use H1.
- HBAR and full-history TAO use V71 special H1 routers.
- TON and IP use V72 dedicated 4H routers.
- HBAR 95.60%; TAO 96.70%; TON 91.21%; IP 86.81%.

# Canonical state
- `data/nocut_intraday_allpass_v73.json` — exact method/router/action/stat/news profile for all 89 instruments.
- `scripts/nocut_intraday_method_v73.py` — operational method reader/router.
- `scripts/validate_nocut_v73.py` — strict hard-gate validator.
- `.github/workflows/validate-nocut-v73.yml` — validation gate.
- `.github/workflows/build-nocut-allpass-v73.yml` — deterministic canonical rebuild from final component engines.
- successful canonical build run: `32032071403`.

# News/context behavior
Forex: analyze both currencies separately with their own central-bank, inflation/jobs/growth, yield/DXY/commodity/risk drivers.
Crypto: analyze the specific token's project/protocol, unlock/supply, exchange/on-chain/whale flow and sector/profile drivers plus BTC regime.

In forced-daily V73, point-in-time news is a **router/confirmation input**, not a hidden NO-TRADE veto.

# Critical integrity caveat
**V73 is DEVELOPMENT-OPTIMIZED / EXPOSED ALL-PASS, not untouched blind/OOS validation.**
May–Jul 2026 was used to develop/refine the maps. The exact V73 state must now be frozen and tested unchanged on independent data before it can be called robust or live-proven.

# Legacy
V18/V40 are old CUT-based forced-daily research and are no longer the active method. V15/V36b are separate selective scanner research with untouched August evidence; only use them if the user explicitly switches back to selective/NO-TRADE-capable mode.

## New-chat instruction
`Current forced-daily Trading method = V73. Read MASTER_TRADING_STATE.md + NO_CUT_INTRADAY_ALLPASS_V73.md. No CUT, no NO TRADE, 1–3 lệnh/symbol/ngày (frozen development maps hiện dùng 1), RR only1:1/1:2 (current RR1), Forex28/28 PASS min80.00%, Crypto61/61 PASS min80.22%. Each symbol has its own method + news/context. Exact state is data/nocut_intraday_allpass_v73.json. Treat all pass numbers as exposed development, not untouched OOS.`
