# CURRENT HANDOFF — TRADING PROJECT

Updated: 2026-08-17 11:19 UTC+7

This is the immediate continuation state for the next ChatGPT conversation. Read `MASTER_TRADING_STATE.md` first, then this file, then the relevant market checkpoint(s).

## User operating preferences
- Respond in Vietnamese unless the user asks for another language.
- For trading code changes, when a file is modified and the user needs to copy it, provide the full updated file rather than only a patch/snippet.
- Do not call a stale/web proxy price “live”. Current entry/hold/cut decisions require an exact fresh symbol refresh through the active data route or a user-provided platform price when that is the designated execution source.
- Keep cash indices separate from NQ/ES futures.
- Structure defines SL first; size/RR comes after.

## Immediate active research task
The active task at handoff is Crypto / Breakout method development.
User’s current goal: continue improving the best method so both win rate and RR rise, while preserving strict blind-test integrity.
For forced blind tests:
- all valid Breakout-universe coins must receive MARKET BUY or MARKET SELL;
- no WAIT, NO TRADE or LIMIT;
- decision, entry, SL and TP must be frozen before future candles are revealed;
- TP/SL must be coin/setup-specific and structure/volatility-aware, not identical across all coins;
- report TP/SL outcome after the blind reveal;
- never optimize on a timestamp and then label that same timestamp true blind.

## Current best crypto research direction
Do NOT restart from generic indicator stacking.
The most promising architecture is **V24-Core**:
1. 6h / 24h / 72h short-horizon momentum;
2. H4/H1 market structure;
3. H4 EMA bias/context;
4. relative strength vs BTC;
5. M15 location, anti-chase and structural context;
6. observe the first 5 minutes after the quarter-hour for the microflow variant;
7. actual OKX public taker BUY/SELL trade imbalance (OFI) as micro confirmation;
8. market-wide price breadth + flow breadth/median as regime context;
9. structural SL from M15/H1 with ATR/profile floor/buffer;
10. dynamic TP/RR, generally around 1.6R–2.0R only when alignment/liquidity room justifies it.

## Why V24-Core is current leader
V22 showed actual taker flow added information relative to the same price-core baseline on two blind dates:
- Jul12: price-only 32.73% WR / -0.135R vs flow 38.18% / -0.007R.
- Jul10: price-only 33.33% / -0.121R vs flow 36.73% / -0.041R.
V23 proved that merely raising RR does not fix directional errors and was rejected.
V24 retained the V22 core and added a market-level price/flow regime guard. Two previously untouched samples were very strong:
- 2026-07-04 12:00 UTC: 56 resolved, 41 TP / 15 SL = 73.21% WR, avg planned RR 1.679, expectancy +0.956R.
- 2026-07-02 12:00 UTC: 34 resolved, 24 TP / 10 SL = 70.59% resolved WR, 22 unresolved, avg planned RR 1.641, expectancy +0.865R.
Important caveat: both V24 samples were classified `normal`, so they support the core but do NOT yet validate the new regime guard itself. Do not claim a proven 70%+ system yet.

## Locked V24 validation now in progress
V24-Core itself remains unchanged and frozen. A separate validation harness was added so Jul04/Jul02 cannot be used to tune the engine:
- `scripts/blind_backtest_crypto_v24_validation.py`
- `.github/workflows/blind-backtest-v24-validation.yml`
- target result: `data/blind_backtest_v24_validation.json`

Five cutoffs were locked before outcomes were inspected:
- `BLIND_JUN30` = 2026-06-30 12:00 UTC
- `BLIND_JUN27` = 2026-06-27 12:00 UTC
- `BLIND_JUN24` = 2026-06-24 12:00 UTC
- `BLIND_JUN21` = 2026-06-21 12:00 UTC
- `BLIND_JUN18` = 2026-06-18 12:00 UTC

These dates are outside the retained August/July development/blind sequence and were selected before seeing their outcomes. The validation script calls the existing `v24.run()` directly and changes no V24 scoring weights, regime thresholds, first-5m flow logic, structural SL logic or dynamic RR rules.

GitHub Actions run at this handoff:
- run id: `31993455685`
- workflow: `Blind Crypto Backtest V24 Validation`
- status at 2026-08-17 11:19 UTC+7: `in_progress`

The validation output is designed to aggregate:
- resolved/unresolved, TP/SL, WR, average planned RR and expectancy R;
- flow coverage;
- each sample’s price breadth, flow breadth/median and market regime;
- performance by coin profile;
- performance when microflow agrees/conflicts with macro direction.
MFE/MAE are not currently emitted by V22/V24 evaluate(), so do not fabricate them.

## Exact crypto files at handoff
Active dependency chain after cleanup plus the temporary locked validation harness:
- `scripts/blind_backtest_crypto.py`
- `scripts/blind_backtest_crypto_v17.py`
- `scripts/blind_backtest_crypto_v22.py`
- `scripts/blind_backtest_crypto_v24.py`
- `scripts/blind_backtest_crypto_v24_validation.py`
- `data/blind_backtest_v17.json`
- `data/blind_backtest_v22.json`
- `data/blind_backtest_v24.json`
- expected after current run: `data/blind_backtest_v24_validation.json`
- `.github/workflows/blind-backtest-v24.yml`
- `.github/workflows/blind-backtest-v24-validation.yml`
- `docs/checkpoints/CRYPTO_BREAKOUT_STATE.md`
- `docs/checkpoints/CRYPTO_RESEARCH_ARCHIVE.md`
Latest confirmed original V24 result file generation timestamp: 2026-08-17T02:38:50.403710Z.

Historical rejected crypto workflows/scripts/results and the standalone OKX tradeflow probe were removed from the active tree after their conclusions were summarized. They remain recoverable from Git history if ever necessary. Do not recreate them unless a specific historical experiment must be reproduced.

## Next correct crypto step
First inspect the current validation run/result. Do NOT alter V24 while the locked June batch is unresolved.
When `data/blind_backtest_v24_validation.json` exists:
1. evaluate aggregate WR, planned RR and expectancy across all five cutoffs;
2. inspect each cutoff separately so one exceptional day cannot hide weak days;
3. inspect performance by coin profile and microflow agreement/conflict;
4. inspect whether any non-`normal` market regime occurred, because Jul04/Jul02 did not validate the regime guard;
5. only then decide whether V24-Core deserves promotion, needs one more untouched batch, or should remain research-only.
Do not tune on these June outcomes and then call the same June dates blind again.

## Forex state at handoff
- Universe: USD/EUR/GBP/JPY/CHF/CAD/AUD/NZD and liquid crosses.
- Hourly Top-3 concept is PAUSED until explicitly re-enabled.
- Data: Twelve Data via project pipeline, D1/H4/H1/M15/M5 + M1/latest execution refresh.
- Macro + multi-timeframe structure + M15 setup + M5 trigger; exact current price must be refreshed before live entry.
- See `FOREX_STATE.md`.

## Metals state at handoff
- Primary: XAUUSD and XAGUSD.
- H4/H1 bias; M15 setup; M5 trigger; M1 live timing only.
- Structure + EMA/RSI/ATR + VWAP/Volume Profile/SR where available.
- Gold context must include DXY, US yields/Fed and major US macro/geopolitical events where relevant.
- TP/SL must be structure-specific, not fixed across setups.
- See `METALS_STATE.md`.

## Cash indices state at handoff
- Default index requests mean CASH indices, not futures.
- NAS100/USTEC/NASDAQ100 -> NDX cash; US500 -> SPX cash; US30 -> DJI; JP225 -> N225; DAX/DE40 -> DAX.
- Twelve Data Basic may block some cash indices such as NDX. Never substitute NQ futures to fake a live cash price.
- See `CASH_INDICES_STATE.md`.

## NQ/ES futures state at handoff
- Separate system only when futures are explicitly requested.
- Execution preference is MNQ/MES micro futures.
- Risk target: structural SL first, then size contracts to keep total SL approximately <= USD 500; target approximately USD 1,500 when structure genuinely supports about 1:3.
- User/platform realtime MNQ/MES price takes priority for final execution when supplied.
- See `FUTURES_NQ_ES_STATE.md`.

## Data / infrastructure state
Repo: `hanlinh227-ship-it/trading-api`.
- `request.json` triggers symbol refresh by changing symbol + incrementing id.
- `.github/workflows/fetch-market.yml` = main data workflow.
- `data/status.json` = validated current output.
- `data/latest.json` = fuller/raw output.
- Crypto direct REST route: Binance -> OKX -> Bybit, with OKX currently the reliable source in recent work.
- Twelve Data mainly serves Forex/metals/cash indices, subject to plan entitlement; do not spend its credits on crypto when exchange REST works.
- Research retention rule: keep current engine/dependency chain + key validation results + summaries; remove concluded one-off probes/grids/rejected raw outputs from the active tree.
- See `DATA_INFRA_STATE.md`.

## New-chat instruction
Recommended first message from user:
`Tiếp tục toàn bộ dự án Trading từ checkpoint GitHub mới nhất. Đọc docs/checkpoints/MASTER_TRADING_STATE.md và docs/checkpoints/CURRENT_HANDOFF.md trước, sau đó đọc checkpoint thị trường liên quan. Tiếp tục đúng trạng thái mới nhất, không quay lại phương pháp đã loại.`

If the next request is about crypto research, immediately inspect `CRYPTO_BREAKOUT_STATE.md`, `CRYPTO_RESEARCH_ARCHIVE.md`, `scripts/blind_backtest_crypto_v24.py`, `scripts/blind_backtest_crypto_v24_validation.py`, `data/blind_backtest_v24.json`, and `data/blind_backtest_v24_validation.json` if it exists before changing the method.
