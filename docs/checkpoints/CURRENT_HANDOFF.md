# CURRENT HANDOFF — TRADING PROJECT

Updated: 2026-08-17 13:38 UTC+7

Read `MASTER_TRADING_STATE.md` first, then this file, then the relevant market checkpoint. Do not reconstruct strategy state from memory when checkpoints exist.

## User operating preferences
- Respond in Vietnamese unless another language is requested.
- For trading code edits where the user needs to copy the result, provide the full updated file.
- Never call stale/web proxy prices executable/live. Refresh exact symbol before current entry/hold/cut decisions.
- Keep cash indices separate from NQ/ES futures.
- Structure defines SL first; size/RR follows.
- Avoid excessive indicators; every indicator must have a distinct role.

## Immediate active task
Forex method development via forced blind testing across all 28 liquid pairs. The current research objective is NOT Top-3 selection: every valid pair is forced BUY or SELL at each blind cutoff so pair-level bias accuracy and TP/SL geometry can be diagnosed.

Crypto research style remains frozen at its current practical framework.

## Forex current state — F4
Universe: 28 pairs formed from USD/EUR/GBP/JPY/CHF/CAD/AUD/NZD.

Minimal technical core remains:
- EMA20/50 = trend/value/slope;
- RSI14 = momentum/exhaustion;
- ATR14 = volatility/SL normalization;
- ADX14 = regime/trend-vs-chop;
- 6h/24h/72h cross-currency strength.

Historical research fetches one Twelve Data M15 series per pair and derives H1/H4 + indicators locally.

### F4 method
- exact blind validation cutoffs were absent from repo before creation: Jul17, Jul20, Jul21, Jul22, Jul24 2026 at 08:00 UTC;
- every valid pair forced BUY or SELL;
- no Top3 selection;
- each pair chooses one of only three predeclared models from development-only evidence: BALANCED / STRUCTURE / REGIME;
- most pairs stayed BALANCED; EURNZD + GBPJPY chose REGIME; GBPCHF chose STRUCTURE;
- SL dynamic from recent M15 structural swing + ATR/realized-range buffer;
- TP dynamic from prior 24h/72h directional liquidity or trailing realized daily-range projection;
- no fixed RR target;
- MARKET and adaptive LIMIT both tested;
- direction separately scored at 6h/12h/24h.

### F4 blind result — 140 signals
MARKET:
- 122 resolved;
- 49 TP / 73 SL;
- 18 timeout;
- WR resolved 40.16%;
- avg planned RR 2.055;
- median RR 1.698;
- expectancy -0.081R.

LIMIT:
- 126/140 fills = 90.0%;
- 110 resolved fills;
- 40 TP / 70 SL;
- 6 no-fill;
- 8 target-before-fill;
- 16 timeouts after fill;
- WR resolved fills 36.36%;
- avg effective RR 2.699;
- expectancy -0.018R.

Direction accuracy:
- 6h 52.14%;
- 12h 53.57%;
- 24h 53.57%.

### Important interpretation
- F4 is still NOT profitable/stable enough to promote.
- Pair-adaptive direction only achieved a modest directional edge slightly above 50%.
- LIMIT improved payoff geometry and brought expectancy close to break-even, but did not fix hit rate.
- Higher WR alone is misleading: AUDUSD had 75% MARKET WR but 0% direction12h and median RR ~0.436R; EURAUD had 100% MARKET WR with median RR ~0.578R.
- The next research must separate `SL but 24h direction correct` from `SL and direction wrong` before changing anything.

Pair examples across the five blind cutoffs:
- stronger: GBPUSD dir12/24 80/80; USDJPY 80/80; GBPAUD 100/100; AUDCAD 100/80.
- weak: GBPJPY 0/0; EURUSD 40/40; USDCAD 40/40; GBPCHF 40/40; CADJPY 40/40.
Do not claim pair-specific stable WR from only five observations.

## Next Forex improvement path
1. Keep indicator count unchanged.
2. Diagnose each F4 SL into bias failure vs barrier/path failure.
3. Improve weak-pair direction with a small number of interpretable pair archetypes; do not create dozens of pair-specific parameters.
4. Require evaluation by direction + expectancy + RR together, not WR alone.
5. Continue blind testing only on timestamps not used for tuning; once a block is revealed it becomes development data forever.
6. MARKET vs LIMIT remains secondary to direction quality.

Retained Forex evidence:
- `scripts/blind_backtest_forex_f2.py`
- `data/blind_backtest_forex_f2.json`
- `scripts/blind_backtest_forex_f3.py`
- `data/blind_backtest_forex_f3.json`
- `scripts/blind_backtest_forex_f4.py`
- `data/blind_backtest_forex_f4.json`
- `docs/checkpoints/FOREX_STATE.md`

## Twelve Data efficiency
- full historical 28-pair block targets 28 symbol credits by fetching only M15;
- H1/H4/EMA/RSI/ATR/ADX/strength derived locally;
- model revisions on the same downloaded block should reuse cached local data where possible.

## Other markets
- Crypto selective practical framework remains frozen.
- Metals remain separate XAUUSD/XAGUSD workflow.
- Cash indices are never silently substituted with futures.
- NQ/ES futures remain separate MNQ/MES workflow.

## Infrastructure
Repo: `hanlinh227-ship-it/trading-api`.
Crypto live route: Binance -> OKX -> Bybit.
Forex/metals/cash indices: Twelve Data/Worker route subject to entitlement.

## New-chat instruction
`Tiếp tục toàn bộ dự án Trading từ checkpoint GitHub mới nhất. Đọc docs/checkpoints/MASTER_TRADING_STATE.md và docs/checkpoints/CURRENT_HANDOFF.md trước, sau đó đọc checkpoint thị trường liên quan. Tiếp tục đúng trạng thái mới nhất, không quay lại phương pháp đã loại.`
