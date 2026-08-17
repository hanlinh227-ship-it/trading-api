# CURRENT HANDOFF — TRADING PROJECT

Updated: 2026-08-17 11:47 UTC+7

Read `MASTER_TRADING_STATE.md` first, then this file, then the relevant market checkpoint(s). Do not reconstruct strategy state from memory when checkpoints exist.

## User operating preferences
- Respond in Vietnamese unless another language is requested.
- For trading code edits where the user needs to copy the result, provide the full updated file, not only a diff/snippet.
- Never call a stale/web proxy price executable/live. Refresh the exact requested symbol through the active feed immediately before current entry/hold/cut decisions.
- Keep cash indices separate from NQ/ES futures.
- Structure defines SL first; position size/RR follows.

## Immediate active task
Crypto / Breakout method research. Goal: improve win rate and RR while preserving strict blind-test integrity.

Forced blind rules:
- every valid Breakout-universe coin gets MARKET BUY or MARKET SELL;
- no WAIT / NO TRADE / LIMIT in the stress test;
- decision, entry, SL and TP are frozen before future candles are revealed;
- SL/TP are coin/setup-specific and structure/volatility-aware;
- never tune on a timestamp and then call the same timestamp true blind.

## V24-Core — retained diagnostic baseline, not live engine
V24-Core = 6h/24h/72h momentum + H4/H1 structure + H4 EMA + BTC relative strength + M15 location/anti-chase + first-5m OKX taker flow + market breadth/flow regime context + structural SL + dynamic ~1.6R–1.95R.

Initial unseen samples were exceptionally strong:
- Jul04: 41 TP / 15 SL = 73.21% WR, avg RR 1.679, +0.956R.
- Jul02: 24 TP / 10 SL among resolved = 70.59%, avg RR 1.641, +0.865R, 22 unresolved.

Locked five-date June validation on the unchanged V24 engine disproved stable generalization:
- aggregate: 278 trades, 262 resolved, 112 TP / 150 SL, 42.75% resolved WR, avg RR 1.647, +0.132R;
- Jun30: 7.27% WR / -0.807R;
- Jun27: 33.33% / -0.126R (`distribution_reversal`);
- Jun24: 83.33% / +1.228R;
- Jun21: 50.91% / +0.338R;
- Jun18: 38.64% / +0.018R.
Result: `data/blind_backtest_v24_validation.json`.

## Row-level V24 failure diagnosis — completed
Jun30:
- 51/56 V24 decisions were SELL;
- BUY 0/5; SELL 4 TP / 46 SL among resolved;
- every profile was poor; internal `trend` = 0/13 and `transition` = 4/37;
- macro/flow agreement still only 8% WR;
- |score| >=4 = 1 TP / 23 SL;
- therefore this was not a low-confidence or isolated-profile failure.

Jun27:
- macro/flow agreement = 46.15% WR / +0.231R;
- macro/flow conflict = 21.43% / -0.443R;
- V24 regime logic changed raw side on only 3 trades and all 3 lost.
This supports treating microflow as confirmation rather than allowing it/regime context to own direction.

## V25 development — rejected
V25 hypothesis was tested only on already-revealed June development dates:
- macro anchors direction;
- flow confirms confidence/RR;
- synchronized extreme same-direction price breadth + OFI was treated as a `sell_climax`/`buy_climax` allowed to reverse the whole market.

June development result:
- aggregate 278 trades, 263 resolved, 111 TP / 152 SL;
- 42.21% WR, avg RR 1.624, +0.114R — worse than V24 June +0.132R.
- Jun30 `sell_climax`: 0 TP / 56 SL = -1.0R.
- Jun27 improved to 38.89% / +0.019R.
- Jun24/Jun21/Jun18 stayed close to V24.

Conclusion: **reject the synchronized-climax direction reversal.** Do not carry it into future versions.

### Direct V24-vs-V25 barrier comparison
Jun30, among 51 symbols whose side changed from V24 to V25:
- 46 were SL in BOTH directions;
- 0 changed from V24-SL to V25-TP;
- 4 changed from V24-TP to V25-SL;
- 1 changed from V24-unresolved to V25-SL.
The other 5 stayed BUY and also remained SL.
Therefore Jun30 is primarily a **barrier/market-quality/whipsaw failure**, not a simple wrong-direction failure. Do not try to fix it by blindly reversing bias.

Jun27, among 5 symbols whose side changed:
- 3 changed from V24-SL to V25-TP;
- 2 remained SL;
- 0 changed from TP to SL.
This is the strongest current evidence for keeping the macro-anchor concept while discarding climax reversal.

## V26 — locked TRUE-BLIND May test now in progress
May had no `2026-05-*` cutoff references in the repository search before V26 was created.
V26 changes exactly one conceptual rule from V24:
- BUY/SELL direction = sign of the macro momentum/structure score;
- microflow and V24 market-regime transform remain confidence/RR context only and may not independently flip direction;
- V24 RR ladder and V22 structural SL remain;
- rejected V25 climax-reversal rule is NOT included.

Locked untouched cutoffs:
- `BLIND_MAY30` = 2026-05-30 12:00 UTC
- `BLIND_MAY27` = 2026-05-27 12:00 UTC
- `BLIND_MAY24` = 2026-05-24 12:00 UTC
- `BLIND_MAY21` = 2026-05-21 12:00 UTC
- `BLIND_MAY18` = 2026-05-18 12:00 UTC

Files:
- `scripts/blind_backtest_crypto_v26.py`
- `.github/workflows/blind-backtest-v26.yml`
- expected result: `data/blind_backtest_v26.json`

GitHub Actions:
- workflow: `Blind Crypto Backtest V26`
- run id: `31995597625`
- status at this checkpoint: queued/in progress; do not alter V26 before the locked May result completes.

## Decision rule after V26 result
Do not promote based on aggregate alone. Compare:
1. aggregate WR / avg RR / expectancy versus V24 June and earlier evidence;
2. all five May dates separately to detect one-day domination;
3. unresolved count;
4. regime-by-regime behavior;
5. whether macro anchoring helps without introducing new catastrophic dates.

If V26 is not materially more stable, reject it and keep V24 only as diagnostic baseline. Do not tune V26 on May and reuse May as blind evidence.

## Important live-vs-stress distinction
Jun30 strongly suggests a live engine should eventually have a `CHAOS / NO TRADE` quality gate when market conditions make both sides structurally poor. However, the forced-MARKET research stress test must still issue BUY/SELL and must not use NO TRADE to inflate statistics. Any live chaos gate must be built/tested separately with only pre-entry information.

## Crypto files currently relevant
Core/retained:
- `scripts/blind_backtest_crypto.py`
- `scripts/blind_backtest_crypto_v17.py`
- `scripts/blind_backtest_crypto_v22.py`
- `scripts/blind_backtest_crypto_v24.py`
- `data/blind_backtest_v17.json`
- `data/blind_backtest_v22.json`
- `data/blind_backtest_v24.json`
- `data/blind_backtest_v24_validation.json`
- `.github/workflows/blind-backtest-v24.yml`

Temporary/research artifacts currently present until V26 conclusion is fully checkpointed:
- rejected V25 script/workflow/result and V24-vs-V25 comparison diagnostic;
- V26 script/workflow and eventual result.
After conclusions are recorded, remove concluded one-off/rejected artifacts according to retention policy; keep key evidence needed for the surviving lineage.

## Other markets
- Forex Top-3 remains PAUSED until explicitly re-enabled; see `FOREX_STATE.md`.
- Metals: XAUUSD/XAGUSD separate workflow; see `METALS_STATE.md`.
- Cash indices are cash, never silently replaced by NQ/ES futures; see `CASH_INDICES_STATE.md`.
- NQ/ES futures are separate and use MNQ/MES execution preference with structural SL first; see `FUTURES_NQ_ES_STATE.md`.

## Infrastructure
Repo: `hanlinh227-ship-it/trading-api`.
Crypto route: Binance -> OKX -> Bybit, with OKX reliable in recent research. Do not spend Twelve Data credits on crypto when direct exchange REST works.

## New-chat instruction
`Tiếp tục toàn bộ dự án Trading từ checkpoint GitHub mới nhất. Đọc docs/checkpoints/MASTER_TRADING_STATE.md và docs/checkpoints/CURRENT_HANDOFF.md trước, sau đó đọc checkpoint thị trường liên quan. Tiếp tục đúng trạng thái mới nhất, không quay lại phương pháp đã loại.`