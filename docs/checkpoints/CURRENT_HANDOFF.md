# CURRENT HANDOFF — TRADING PROJECT

Updated: 2026-08-17 11:27 UTC+7

Read `MASTER_TRADING_STATE.md` first, then this file, then the relevant market checkpoint(s). Do not reconstruct strategy state from memory when these files exist.

## User operating preferences
- Respond in Vietnamese unless the user asks for another language.
- For trading code changes, when a file is modified and the user needs to copy it, provide the full updated file rather than only a patch/snippet.
- Do not call a stale/web proxy price “live”. Current entry/hold/cut decisions require an exact fresh symbol refresh through the active data route or a user-provided platform price when that is the designated execution source.
- Keep cash indices separate from NQ/ES futures.
- Structure defines SL first; size/RR comes after.

## Immediate active research task
Active task: Crypto / Breakout method development.
Goal: improve both win rate and RR without violating strict blind-test integrity.

Forced blind-test rules remain:
- every valid Breakout-universe coin receives MARKET BUY or MARKET SELL;
- no WAIT / NO TRADE / LIMIT;
- decision, entry, SL and TP are frozen before future candles are revealed;
- SL/TP are coin/setup-specific and structure/volatility-aware;
- never optimize on a timestamp and then call that same timestamp true blind.

## V24-Core status — validation completed
V24-Core architecture remains:
1. 6h / 24h / 72h momentum;
2. H4/H1 structure;
3. H4 EMA context;
4. BTC relative strength;
5. M15 location / anti-chase;
6. first 5 minutes after quarter-hour;
7. actual OKX taker BUY/SELL imbalance;
8. market price breadth + flow breadth/median regime context;
9. structural M15/H1 SL + ATR/profile floor;
10. dynamic RR roughly 1.6R–2.0R.

Initial locked evidence had been unusually strong:
- Jul04: 41 TP / 15 SL = 73.21% WR, avg RR 1.679, +0.956R.
- Jul02: 24 TP / 10 SL among resolved = 70.59% WR, avg RR 1.641, +0.865R, with 22 unresolved.
Both were `normal` regime.

A separate locked validation harness then ran the exact unchanged V24 engine on five previously uninspected June dates. GitHub Actions run `31993455685` completed successfully and committed `data/blind_backtest_v24_validation.json`.

### Five-date June aggregate
- 278 trades;
- 262 resolved;
- 112 TP / 150 SL;
- 16 unresolved;
- 42.75% resolved WR;
- average planned RR 1.647;
- expectancy +0.132R;
- flow coverage 62.2%.

### Per-date result
- Jun30: 55 resolved, 4 TP / 51 SL = 7.27% WR, avg RR 1.687, expectancy -0.807R, `normal`, price breadth 0.214, flow breadth 0.317, flow median -0.374.
- Jun27: 54 resolved, 18 TP / 36 SL = 33.33% WR, avg RR 1.632, expectancy -0.126R, `distribution_reversal`, price breadth 0.946, flow breadth 0.400, flow median -0.105.
- Jun24: 54 resolved, 45 TP / 9 SL = 83.33% WR, avg RR 1.668, expectancy +1.228R, `normal`.
- Jun21: 55 resolved, 28 TP / 27 SL = 50.91% WR, avg RR 1.622, expectancy +0.338R, `normal`.
- Jun18: 44 resolved, 17 TP / 27 SL = 38.64% WR, 11 unresolved, avg RR 1.623, expectancy +0.018R, `normal`.

### Diagnostic aggregates
By flow relation:
- macro/micro agree: 44.87% WR, avg RR 1.759, expectancy +0.235R;
- macro/micro conflict: 38.55% WR, avg RR 1.600, expectancy +0.002R;
- flow unavailable: 45.0% WR, expectancy +0.170R.

By profile:
- major: 50.0% WR, +0.321R;
- meme: 55.1%, +0.456R;
- alt: 60.0%, +0.600R on only 10 resolved;
- L1/L2: 41.11%, +0.091R;
- new/high-beta: 44.44%, +0.200R;
- AI/high-beta: 33.33%, -0.133R;
- DeFi: 23.08%, -0.395R.

## Decision after validation
**Do not promote V24-Core as a main/final/live engine.**
The June batch shows a small positive aggregate edge but unacceptable date-to-date instability. The Jul04/Jul02 70%+ results do not generalize reliably.

The V24 regime guard is also not validated: its first locked `distribution_reversal` sample (Jun27) remained negative at -0.126R.

Do not discard actual taker flow. It still adds information, especially when aligned with macro direction, but it is not enough by itself to solve the directional regime failure.

Do not repair this by:
- raising/lowering RR cosmetically;
- generic indicator stacking;
- moving V24 regime thresholds just to fit Jun30/Jun27;
- filtering bad June profiles and then reusing June as blind evidence.

The five June dates are now **development/diagnostic data**, never again unseen validation data for a successor.

## Immediate next correct experiment
Before V25, diagnose Jun30 and Jun27 at row level from `data/blind_backtest_v24_validation.json`:
- side and outcome distribution;
- macro/micro agreement vs conflict;
- coin profiles and internal trend/transition regimes concentrating losses;
- score-confidence buckets;
- flow availability/OFI direction;
- whether the failure represents trend continuation, exhaustion/capitulation, or incorrect reversal handling.

From that diagnosis, formulate the smallest theory-driven V25 change. Freeze it before opening outcomes on the next true-blind block. Prefer untouched May 2026 dates for V25 validation.

## Exact crypto files to preserve
- `scripts/blind_backtest_crypto.py`
- `scripts/blind_backtest_crypto_v17.py`
- `scripts/blind_backtest_crypto_v22.py`
- `scripts/blind_backtest_crypto_v24.py`
- `data/blind_backtest_v17.json`
- `data/blind_backtest_v22.json`
- `data/blind_backtest_v24.json`
- `data/blind_backtest_v24_validation.json`
- `.github/workflows/blind-backtest-v24.yml`
- `docs/checkpoints/CRYPTO_BREAKOUT_STATE.md`
- `docs/checkpoints/CRYPTO_RESEARCH_ARCHIVE.md`

The completed five-date validation harness/workflow are one-off research artifacts and should be removed from the active tree after their conclusions are checkpointed; Git history preserves them.

## Other market states
### Forex
- USD/EUR/GBP/JPY/CHF/CAD/AUD/NZD and liquid crosses.
- Hourly Top-3 concept remains PAUSED until explicitly re-enabled.
- Twelve Data D1/H4/H1/M15/M5 + M1/latest refresh.
- See `FOREX_STATE.md`.

### Metals
- XAUUSD/XAGUSD: H4/H1 bias, M15 setup, M5 trigger, M1 final timing only.
- Include DXY, US yields/Fed and major US macro/geopolitical context when relevant.
- See `METALS_STATE.md`.

### Cash indices
- Default index requests mean CASH indices, not futures.
- Never substitute NQ futures for unavailable NDX cash prices.
- See `CASH_INDICES_STATE.md`.

### NQ/ES futures
- Separate system only when explicitly requested.
- MNQ/MES execution; structural SL first, then contracts sized to approximately <= USD 500 risk; approximately USD 1,500 target only when structure supports ~1:3.
- User/platform realtime price takes priority when supplied.
- See `FUTURES_NQ_ES_STATE.md`.

## Data / infrastructure
Repo: `hanlinh227-ship-it/trading-api`.
- `request.json` increments id to trigger symbol refresh.
- `.github/workflows/fetch-market.yml` = main data workflow.
- `data/status.json` = validated current output; `data/latest.json` = fuller/raw output.
- Crypto direct REST route: Binance -> OKX -> Bybit; OKX has been reliable in recent research.
- Do not spend Twelve Data credits on crypto when exchange REST works.

## New-chat instruction
`Tiếp tục toàn bộ dự án Trading từ checkpoint GitHub mới nhất. Đọc docs/checkpoints/MASTER_TRADING_STATE.md và docs/checkpoints/CURRENT_HANDOFF.md trước, sau đó đọc checkpoint thị trường liên quan. Tiếp tục đúng trạng thái mới nhất, không quay lại phương pháp đã loại.`

For crypto research specifically, inspect `CRYPTO_BREAKOUT_STATE.md`, `CRYPTO_RESEARCH_ARCHIVE.md`, `scripts/blind_backtest_crypto_v24.py`, `data/blind_backtest_v24.json`, and `data/blind_backtest_v24_validation.json` before changing the method.