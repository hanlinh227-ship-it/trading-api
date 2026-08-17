# MASTER TRADING STATE

Updated: 2026-08-17 (UTC+7)
Purpose: canonical handoff/checkpoint for continuing the Trading project across new ChatGPT conversations.

## 1. Cross-chat protocol
- At the start of a new Trading chat, read this file first, then `docs/checkpoints/CURRENT_HANDOFF.md`, then the market-specific checkpoint(s) below.
- `CURRENT_HANDOFF.md` contains the immediate active task, exact latest research state and next step. Market files contain longer-lived rules.
- Do not reconstruct strategy state from memory when a checkpoint exists.
- When a material rule, API path, symbol universe, risk rule, or validated backtest version changes, update the appropriate checkpoint, `CURRENT_HANDOFF.md`, and then this master file if the high-level state changed.
- Never promote a new method only because it has one unusually strong backtest. Keep validation sample size and regime diversity explicit.
- Never present stale/web proxy prices as executable live prices. Refresh the exact requested symbol through the active API/feed immediately before any current-price/entry/hold decision.

## 2. Canonical checkpoint files
- `docs/checkpoints/CURRENT_HANDOFF.md`
- `docs/checkpoints/FOREX_STATE.md`
- `docs/checkpoints/CRYPTO_BREAKOUT_STATE.md`
- `docs/checkpoints/METALS_STATE.md`
- `docs/checkpoints/CASH_INDICES_STATE.md`
- `docs/checkpoints/FUTURES_NQ_ES_STATE.md`
- `docs/checkpoints/DATA_INFRA_STATE.md`

## 3. User operating preferences
- Default response language: Vietnamese unless the user asks for another language.
- For trading code edits where the user needs to copy the result, provide the full updated file, not only a diff/snippet.
- Be concise and execution-oriented, but preserve exact prices, timestamps, sources, Entry/SL/TP/RR and validation caveats when they matter.

## 4. Universal analysis rules
- Separate market context from execution timing.
- Multi-timeframe sequence: HTF regime/bias -> structure -> setup -> LTF trigger -> structure-based SL -> realistic TP/liquidity target.
- Indicators must have distinct roles; avoid stacking redundant indicators.
- News/macro/event risk must be checked when relevant.
- Structure determines invalidation first. ATR/volatility is a buffer/floor, not a reason to invent an SL.
- Position sizing follows the SL and the allowed USD/% risk; never choose the SL from desired position size.
- Forced BUY/SELL on every symbol is a diagnostic stress test only, never automatically a live rule.
- `NO TRADE` is valid when market quality or execution quality is insufficient.

## 5. Market separation
- Cash indices are NOT futures. NAS100/USTEC means Nasdaq-100 cash unless the user explicitly asks for futures.
- Futures NQ/ES/MNQ/MES are separate instruments and must never be silently substituted for cash indices.
- Crypto Breakout universe must be verified against Breakout support; exchange availability alone does not prove Breakout availability.
- Forex has a separate cross-currency strength framework; do not import crypto-specific BTC breadth/order-flow rules into Forex.

## 6. Current high-level status

### Forex — active research / selective live framework
Universe: the 28 liquid pairs formed by USD/EUR/GBP/JPY/CHF/CAD/AUD/NZD.

F1 July diagnostic:
- forced all-pair RR1.5: 55 TP / 81 SL from 136 resolved, 40.44% WR, +0.011R;
- naive Top3 strongest-score: 4 TP / 11 SL, -0.333R;
- conclusion: raw highest trend/strength score and clustered currency exposure are rejected as selection rules.

F2 blind holdout used untouched Aug04/05/06/10/11:
- forced all-pair at dev-selected RR2.1: 38 TP / 88 SL from 126 resolved, 30.16% WR, -0.065R;
- strict selective gate produced only 4 signals: 3 TP / 1 SL, 75% WR, +1.325R at test RR2.1;
- LIMIT filled 3/4: 2 TP / 1 SL, avg effective RR 3.133, +1.756R among resolved fills; one continuation winner hit target before LIMIT filled;
- four trades are far too few to claim a stable 75% WR. F2 is a promising quality gate, not a fully validated profit engine.
- Aug05 is key evidence: forced benchmark had 0 TP / 25 SL while F2 selected zero trades.

Preferred Forex live style:
- 6h/24h/72h cross-currency strength first;
- live macro/news context for both currencies;
- H4/H1 structure and slope;
- M15 setup/anti-chase;
- M5 execution confirmation;
- correlation control and maximum 3 trades, but 0–2 is valid;
- MARKET for clean continuation, LIMIT only for structurally expected pullback;
- structural SL first;
- dynamic RR: require roughly >=1.5R room, prefer ~1.8–2.1R only when real structure/liquidity supports it;
- exact M1/latest refresh immediately before executable entry.

Primary retained evidence: `scripts/blind_backtest_forex_f2.py`, `data/blind_backtest_forex_f2.json`, `docs/checkpoints/FOREX_STATE.md`.

### Crypto / Breakout — style frozen at current practical framework
- Direct exchange data through GitHub runner is preferred over Twelve Data for crypto.
- Exchange route: Binance -> OKX -> Bybit.
- No validated forced all-market crypto engine.
- V24 remains diagnostic; V25/V26/V27 rejected for the reasons documented in crypto checkpoints.
- Preferred live direction remains selective: BTC/market-quality first, D1/H4/H1 structure + short momentum, M15/M5 setup, fresh order flow only when available, structure-based SL, realistic RR, MARKET-vs-LIMIT by setup, explicit `NO TRADE / CHAOS` when poor.
- Do not restart rejected crypto version churn unless a genuinely new hypothesis is supplied.

### Metals
- XAUUSD/XAGUSD are separate from crypto/index logic.
- Default workflow: H4/H1 bias; M15/M5 setup; M1 only for final timing/price refresh. Use structure, EMA, RSI, VWAP/Volume Profile/SR where data exists, plus DXY/US yields/Fed/high-impact US news.

### Cash indices
- Only cash indices by default: Nasdaq-100, S&P 500, Dow, Nikkei 225, DAX, plus other supported cash indices.
- Current Twelve Data entitlement may block some symbols; never fake a cash-index price using futures.

### Futures NQ/ES
- Separate system, only when explicitly requested.
- Execution preference: MNQ/MES micros; structural SL first, then size contracts to approximately USD 500 maximum risk and roughly USD 1,500 target when structure supports ~1:3.
- User/platform realtime MNQ/MES price takes priority at final execution when supplied.

## 7. Live execution quality gate
Before issuing a current MARKET entry:
1. exact symbol refreshed now;
2. requested symbol == returned symbol;
3. timestamp/source shown internally and freshness validated;
4. relevant timeframes/context available;
5. no stale flag / execution-ready gate passes where implemented;
6. market structure and invalidation identified;
7. news/event risk checked if relevant;
8. Entry, SL, TP and RR calculated from the refreshed price.

## 8. Handoff phrase for a new chat
Preferred full message:
`Tiếp tục toàn bộ dự án Trading từ checkpoint GitHub mới nhất. Đọc docs/checkpoints/MASTER_TRADING_STATE.md và docs/checkpoints/CURRENT_HANDOFF.md trước, sau đó đọc checkpoint thị trường liên quan. Tiếp tục đúng trạng thái mới nhất, không quay lại phương pháp đã loại.`

Short form also works:
`Tiếp tục dự án Trading từ checkpoint GitHub mới nhất.`