# MASTER TRADING STATE

Updated: 2026-08-17 UTC+7
Purpose: canonical handoff/checkpoint for the Trading project.

## Read order — CURRENT MODE
1. `CURRENT_HANDOFF.md`
2. `NO_CUT_INTRADAY_ALLPASS_V73.md`
3. `data/nocut_intraday_allpass_v73.json`
4. `scripts/nocut_intraday_method_v73.py`
5. `scripts/validate_nocut_v73.py`

# Current forced-daily intraday mode — V73
This supersedes V18/V40 for the user's current forced-daily research/live-entry workflow.

Hard rules:
- no CUT;
- no NO TRADE day;
- each symbol must trade minimum 1 and maximum 3 times/day;
- current frozen passing maps use exactly 1 trade/day;
- RR only 1:1 or 1:2; current passing maps all use RR1:1;
- every Forex pair and every Crypto symbol must have development WR >=80%;
- TIMEOUT is a non-win;
- same-bar TP+SL is scored as SL conservatively;
- each symbol has its own method and its own news/context profile.

## V73 development result
- Forex: **28/28 PASS**, minimum per-pair WR **80.00%**.
- Crypto: **61/61 PASS**, minimum per-coin WR **80.22%**.
- Forex = H1.
- 59 Crypto symbols = H1.
- TON/IP = dedicated 4H methods because full common-source H1 history was unavailable.
- canonical exact state: `data/nocut_intraday_allpass_v73.json`.
- successful canonical build run: `32032071403`.

Final architecture:
- Forex V64 base + V66 targeted H1 refinement.
- Crypto V69 static passes + V70 observable regime routers + V71 HBAR/TAO + V72 TON/IP.

Last difficult crypto confirmations:
- HBAR 95.60%.
- TAO 96.70%.
- TON 91.21%.
- IP 86.81%.

# Symbol-specific context requirement
Forex keeps separate currency-driver context for both legs: central bank, inflation/jobs/growth, rates/DXY/commodity/risk where relevant.
Crypto keeps symbol-specific project/protocol, unlock/supply, exchange/on-chain/whale context plus its sector/profile drivers and BTC regime.

Because NO TRADE is forbidden in this mode, point-in-time news does not silently veto a trading day. It routes/confirms the frozen symbol-specific execution geometry/regime.

# Integrity classification
**V73 IS EXPOSED DEVELOPMENT ALL-PASS, NOT UNTOUCHED OOS.**
May–Jul 2026 was used to search/refine the methods. Do not call the development WR a live/future guarantee. The next integrity step is to freeze V73 unchanged and test independent history/forward data without retuning the holdout.

# Legacy / comparison modes
The following remain research history and must not be mistaken for the current forced-daily V73 method:
- V18 Forex forced-daily CUT-based mode.
- V40 Crypto forced-daily CUT-based mode.
- V15 Forex selective scanner with untouched August evidence.
- V36b Crypto selective scanner with untouched August evidence.

Selective V15/V36b can still be used only if the user explicitly switches back to a selective/NO-TRADE-capable research objective. They are not the active forced-daily method.

# Live/forward requirements
Before any real signal:
- refresh exact current price;
- load the symbol from V73 only;
- use point-in-time symbol-specific news/calendar/context;
- compute only features available at the decision time;
- route to the frozen action without looking ahead;
- do not reintroduce CUT or NO TRADE;
- record TP/SL/TIMEOUT and actual R;
- never describe development WR as guaranteed live WR.

## Handoff phrase
`Tiếp tục Trading từ MASTER_TRADING_STATE.md và NO_CUT_INTRADAY_ALLPASS_V73.md. Current forced-daily mode = V73: NO CUT, NO NO-TRADE day, 1–3 lệnh/symbol/ngày (frozen maps hiện dùng 1), RR chỉ1:1/1:2 (hiện đều RR1), Forex28/28 PASS minWR80.00%, Crypto61/61 PASS minWR80.22%. Mỗi symbol có method + news/context riêng. Exact state ở data/nocut_intraday_allpass_v73.json. Đây là exposed-development all-pass May-Jul, chưa phải untouched OOS.`
