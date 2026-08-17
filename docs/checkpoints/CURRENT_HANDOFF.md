# CURRENT HANDOFF — TRADING PROJECT

Updated: 2026-08-17 13:05 UTC+7

Read `MASTER_TRADING_STATE.md` first, then this file, then the relevant market checkpoint. Do not reconstruct strategy state from memory when checkpoints exist.

## User operating preferences
- Respond in Vietnamese unless another language is requested.
- For trading code edits where the user needs to copy the result, provide the full updated file.
- Never call stale/web proxy prices executable/live. Refresh exact symbol before current entry/hold/cut decisions.
- Keep cash indices separate from NQ/ES futures.
- Structure defines SL first; size/RR follows.

## Immediate active task
Forex analysis quality and selective live execution.

Crypto research style is now considered frozen at the current practical framework. Do not restart rejected crypto V25/V26/V27 ideas or force every coin into a live trade. Detailed crypto state remains in `CRYPTO_BREAKOUT_STATE.md` and `CRYPTO_RESEARCH_ARCHIVE.md`.

## Forex current conclusion
Universe: 28 liquid pairs formed from USD/EUR/GBP/JPY/CHF/CAD/AUD/NZD.

### F1 diagnostic
Fully covered July evidence at RR 1.5:
- forced all pairs: 140 signals, 136 resolved, 55 TP / 81 SL, 40.44% WR, +0.011R;
- naive Top3 strongest-score MARKET: 4 TP / 11 SL, 26.67% WR, -0.333R;
- Top3 fixed LIMIT: 13 fills, 2 TP / 11 SL, -0.451R.
Conclusion: highest raw strength/trend score is not the best Forex entry; clustered/crowded currency exposure is dangerous.

### F2 anti-crowding quality gate
Development = revealed July block only.
Blind validation was locked before outcomes on Aug04, Aug05, Aug06, Aug10, Aug11 at 08:00 UTC.

F2 ingredients:
- one cached M15 history per pair;
- derive 6h/24h/72h cross-currency strength + H1/H4 locally;
- require multi-horizon agreement, H4/H1 alignment and H1 EMA slope;
- moderate RSI and M15 momentum, anti-chase and structural-risk gates;
- penalize extreme score rather than automatically rewarding it;
- no repeated currency factor across selected trades;
- structural SL first;
- up to 3 signals, but `NO TRADE` is valid.

Blind validation:
- forced all 28 pairs at development-selected RR 2.1: 126 resolved, 38 TP / 88 SL, 30.16% WR, -0.065R;
- selective MARKET: only 4 signals passed across 5 cutoffs, 3 TP / 1 SL, 75.0% WR, +1.325R at test RR 2.1;
- selective LIMIT 0.25R: 3 fills, 2 TP / 1 SL, avg effective RR 3.133, +1.756R among resolved fills; one MARKET winner reached target before LIMIT filled;
- sample size 4 is far too small to claim a stable 75% WR. F2 is a promising quality gate, not a fully validated profit engine.

Critical date evidence:
- Aug04 EURNZD SELL MARKET TP; LIMIT missed continuation.
- Aug05 forced benchmark = 0 TP / 25 SL among resolved, while F2 selected ZERO trades.
- Aug06 EURJPY BUY TP.
- Aug10 GBPUSD BUY TP; LIMIT also TP.
- Aug11 GBPAUD BUY SL.

## Forex practical style from now on
1. Build currency-level 6h/24h/72h strength across all 28 pairs.
2. Check live macro/news regime for the two currencies.
3. H4/H1 structure + slope decide tradable direction; raw extreme score is not enough.
4. M15 determines setup/anti-chase and structural invalidation.
5. M5 confirms actual execution trigger.
6. Rank quality with correlation control; return 0–3 trades, never manufacture exactly 3.
7. MARKET for clean continuation; LIMIT only for a structurally expected pullback with explicit expiry/cancel condition.
8. Structure defines SL first.
9. RR is dynamic: require roughly >=1.5R room and prefer ~1.8–2.1R only when real liquidity/structure supports it. Do not hard-code 2.1 universally.
10. M1/latest is fetched only immediately before an executable entry.

Retained Forex research evidence:
- `scripts/blind_backtest_forex_f2.py`
- `data/blind_backtest_forex_f2.json`
- `docs/checkpoints/FOREX_STATE.md`

## Twelve Data efficiency
Preferred research/live-scan architecture:
- 28-pair universe: one M15 time-series per pair = 28 symbol credits;
- derive H1/H4 and 6h/24h/72h strength locally;
- fetch M5 only for up to 3 finalists;
- fetch M1/latest only for up to 3 executable finalists;
- target about 34 symbol credits for a full scan with three finalists, instead of multi-timeframe requests for every pair.

## Crypto state — frozen, not deleted
Keep the current selective crypto framework:
- BTC/market regime and breadth first;
- D1/H4/H1 + 6h/24h/72h momentum;
- M15/M5 setup;
- fresh order flow only when available;
- structural SL;
- MARKET vs LIMIT chosen by setup;
- `NO TRADE / CHAOS` allowed;
- no forced all-coin live engine.

## Other markets
- Metals remain separate XAUUSD/XAGUSD workflow.
- Cash indices are never silently substituted with futures.
- NQ/ES futures remain a separate MNQ/MES workflow.

## Infrastructure
Repo: `hanlinh227-ship-it/trading-api`.
Crypto live route: Binance -> OKX -> Bybit.
Forex/metals/cash indices: Twelve Data/Worker route subject to entitlement.

## New-chat instruction
`Tiếp tục toàn bộ dự án Trading từ checkpoint GitHub mới nhất. Đọc docs/checkpoints/MASTER_TRADING_STATE.md và docs/checkpoints/CURRENT_HANDOFF.md trước, sau đó đọc checkpoint thị trường liên quan. Tiếp tục đúng trạng thái mới nhất, không quay lại phương pháp đã loại.`