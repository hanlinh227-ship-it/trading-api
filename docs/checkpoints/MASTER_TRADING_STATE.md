# MASTER TRADING STATE

Updated: 2026-08-17 (UTC+7)
Purpose: canonical handoff/checkpoint for continuing the Trading project across new ChatGPT conversations.

## 1. Cross-chat protocol
- At the start of a new Trading chat, read this file first, then `docs/checkpoints/CURRENT_HANDOFF.md`, then the market-specific checkpoint(s).
- Do not reconstruct strategy state from memory when checkpoints exist.
- When a material rule, API path, symbol universe, risk rule, or validation conclusion changes, update the relevant market checkpoint, CURRENT_HANDOFF, then this master file when high-level state changes.
- Never promote a method because of one unusually strong backtest; keep sample size/regime diversity explicit.
- Never present stale/web proxy prices as executable live prices. Refresh the exact symbol through the active feed immediately before current-price/entry/hold/cut decisions.

## 2. Canonical checkpoint files
- `docs/checkpoints/CURRENT_HANDOFF.md`
- `docs/checkpoints/FOREX_STATE.md`
- `docs/checkpoints/CRYPTO_BREAKOUT_STATE.md`
- `docs/checkpoints/METALS_STATE.md`
- `docs/checkpoints/CASH_INDICES_STATE.md`
- `docs/checkpoints/FUTURES_NQ_ES_STATE.md`
- `docs/checkpoints/DATA_INFRA_STATE.md`

## 3. User operating preferences
- Default response language: Vietnamese unless another language is requested.
- For trading code edits where the user needs to copy the result, provide the full updated file.
- Be concise and execution-oriented while preserving exact price/time/source, Entry/SL/TP/RR and validation caveats when relevant.
- Avoid redundant indicator stacking.

## 4. Universal analysis rules
- Separate market context from execution timing.
- Multi-timeframe sequence: regime/bias -> structure -> setup -> LTF trigger -> structural SL -> realistic TP/liquidity target.
- Indicators must have distinct roles.
- News/macro/event risk must be checked when relevant.
- Structure determines invalidation first; ATR/volatility is buffer/floor.
- Position sizing follows SL and allowed risk.
- Forced BUY/SELL on every symbol is allowed as a research stress test but is not automatically a live rule.
- Direction accuracy and TP/SL outcome should be evaluated separately when possible.

## 5. Market separation
- Cash indices are NOT futures. NAS100/USTEC means Nasdaq-100 cash unless futures are explicitly requested.
- Futures NQ/ES/MNQ/MES are separate instruments.
- Crypto Breakout availability must be verified; exchange availability alone is not enough.
- Forex uses a separate cross-currency framework; do not import crypto BTC breadth/order-flow logic into Forex.

## 6. Current high-level status

### Forex — active forced-blind method research
Universe: 28 liquid pairs formed from USD/EUR/GBP/JPY/CHF/CAD/AUD/NZD.

Current user-requested research mode:
- no Top-3 requirement;
- every valid pair gets BUY or SELL at each blind cutoff;
- score direction at 6h/12h/24h plus actual TP/SL;
- TP/SL may be dynamic rather than fixed RR;
- after a blind block is revealed it becomes development data forever.

Minimal technical core:
- EMA20/50 = trend/value/slope;
- RSI14 = momentum/exhaustion;
- ATR14 = volatility/SL normalization;
- ADX14 = regime/trend-vs-chop;
- 6h/24h/72h cross-currency strength.

Currency-specific live macro profiles remain required: USD Fed/PCE-CPI/labour/yields; EUR ECB/HICP/wages-services/energy-growth; GBP BoE/CPI-services/wages/growth; JPY BoJ/JGB/carry/MOF intervention; CHF SNB/inflation/risk-off/intervention; CAD BoC/jobs-CPI/oil/US trade-growth; AUD RBA/inflation/labour/China-commodities-risk; NZD RBNZ/CPI/spare-capacity/dairy-global rates.

#### F1-F3 compressed evidence
- F1 naive strongest-score Top3 rejected.
- F2 selective four-trade sample showed apparent 75% but was too small.
- F3 new holdout failed to confirm 75%; forced RR1.8 = 44 TP / 84 SL from 128 resolved, -0.037R; selective sample only 1 TP / 1 SL + timeout.

#### F4 pair-adaptive forced blind
Validation cutoffs were repo-searched absent before creation: Jul17, Jul20, Jul21, Jul22, Jul24 2026 08:00 UTC.
- every valid pair forced BUY/SELL = 140 total signals;
- each pair could choose only BALANCED / STRUCTURE / REGIME from development-only evidence with regularization;
- most remained BALANCED; EURNZD + GBPJPY chose REGIME, GBPCHF chose STRUCTURE;
- SL dynamic from recent M15 structure + ATR/realized-range geometry;
- TP dynamic from prior 24h/72h liquidity or trailing realized daily range; no fixed RR target;
- MARKET and adaptive LIMIT both tested.

F4 results:
- MARKET: 122 resolved, 49 TP / 73 SL, 18 timeout; WR 40.16%; avg planned RR 2.055; median RR 1.698; expectancy -0.081R;
- LIMIT: 126 fills (90%), 110 resolved fills, 40 TP / 70 SL; WR 36.36%; avg effective RR 2.699; expectancy -0.018R;
- direction 6h 52.14%; 12h 53.57%; 24h 53.57%.

F4 conclusion:
- method is still not stable/profitable enough;
- directional edge is only modestly above 50%;
- LIMIT improves payoff geometry but does not solve wrong bias;
- higher WR can be misleading when targets are too small: some pairs showed high TP rate while direction accuracy and RR were poor;
- next improvement must classify each SL as `bias wrong` vs `bias later right but barrier/path wrong`, then change only the failing component.

Useful F4 pair diagnostics across only five blind cutoffs (not stable WR claims):
- stronger direction: GBPUSD 80/80 at 12h/24h; USDJPY 80/80; GBPAUD 100/100; AUDCAD 100/80.
- weak direction: GBPJPY 0/0; EURUSD 40/40; USDCAD 40/40; GBPCHF 40/40; CADJPY 40/40.

Active Forex evidence:
- `scripts/blind_backtest_forex_f2.py`, `data/blind_backtest_forex_f2.json`
- `scripts/blind_backtest_forex_f3.py`, `data/blind_backtest_forex_f3.json`
- `scripts/blind_backtest_forex_f4.py`, `data/blind_backtest_forex_f4.json`
- `docs/checkpoints/FOREX_STATE.md`

### Crypto / Breakout — practical style frozen
- Direct exchange data through GitHub runner preferred over Twelve Data.
- Route: Binance -> OKX -> Bybit.
- No validated forced all-market crypto engine.
- V24 diagnostic; V25/V26/V27 rejected as documented.
- Live direction remains selective: BTC/market-quality first, D1/H4/H1 + short momentum, M15/M5, fresh order flow only when available, structure SL, realistic RR, MARKET-vs-LIMIT by setup, explicit `NO TRADE / CHAOS`.

### Metals
- XAUUSD/XAGUSD separate workflow.
- H4/H1 bias; M15/M5 setup; M1 final timing/price refresh. Use structure, EMA, RSI, VWAP/Volume Profile/SR where available plus DXY/US yields/Fed/high-impact US news.

### Cash indices
- Cash indices only by default. Never substitute futures when entitlement blocks a cash-index symbol.

### Futures NQ/ES
- Separate system, only when explicitly requested.
- Prefer MNQ/MES micros; structural SL first, then size to about USD 500 max risk and roughly USD 1,500 target when ~1:3 structure supports it.
- User/platform realtime MNQ/MES price has priority for final execution when supplied.

## 7. Twelve Data efficiency
Forex historical research architecture:
- one M15 series per 28 pairs = 28 symbol credits per full block;
- derive H1/H4, EMA/RSI/ATR/ADX and strength locally;
- model/barrier experiments on the same block should reuse cached local data where possible;
- avoid multi-timeframe provider calls for all 28 pairs.

## 8. Live execution quality gate
Before issuing a current MARKET entry:
1. exact symbol refreshed now;
2. requested symbol == returned symbol;
3. timestamp/source freshness validated;
4. relevant context/timeframes available;
5. no stale/execution-ready failure;
6. structure and invalidation identified;
7. relevant news/event risk checked;
8. Entry/SL/TP/RR calculated from refreshed price.

## 9. Handoff phrase
`Tiếp tục toàn bộ dự án Trading từ checkpoint GitHub mới nhất. Đọc docs/checkpoints/MASTER_TRADING_STATE.md và docs/checkpoints/CURRENT_HANDOFF.md trước, sau đó đọc checkpoint thị trường liên quan. Tiếp tục đúng trạng thái mới nhất, không quay lại phương pháp đã loại.`
