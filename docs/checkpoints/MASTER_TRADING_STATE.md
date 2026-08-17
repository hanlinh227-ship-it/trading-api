# MASTER TRADING STATE

Updated: 2026-08-17 (UTC+7)
Purpose: canonical handoff/checkpoint for continuing the Trading project across new ChatGPT conversations.

## 1. Cross-chat protocol
- At the start of a new Trading chat, read this file first, then `docs/checkpoints/CURRENT_HANDOFF.md`, then the market-specific checkpoint(s) below.
- `CURRENT_HANDOFF.md` contains the immediate active task, exact latest research state and next step. Market files contain longer-lived rules.
- Do not reconstruct strategy state from memory when a checkpoint exists.
- When a material rule, API path, symbol universe, risk rule, or validated backtest version changes, update the appropriate checkpoint, `CURRENT_HANDOFF.md`, and then this master file if the high-level state changed.
- Never promote a new method only because it has one unusually strong backtest. Keep the last robust baseline until new unseen blind samples confirm improvement.
- Never present stale/web proxy prices as executable live prices. Refresh the exact requested symbol through the active API/feed immediately before any current-price/entry/hold decision.

## 2. Canonical checkpoint files
- `docs/checkpoints/CURRENT_HANDOFF.md` — read immediately after this master file.
- `docs/checkpoints/FOREX_STATE.md`
- `docs/checkpoints/CRYPTO_BREAKOUT_STATE.md`
- `docs/checkpoints/METALS_STATE.md`
- `docs/checkpoints/CASH_INDICES_STATE.md`
- `docs/checkpoints/FUTURES_NQ_ES_STATE.md` — separate, only when futures are explicitly requested.
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
- If the user explicitly requests a forced-MARKET blind stress test, every symbol with valid data must receive BUY or SELL. This is a test condition, not automatically a live-trading rule.

## 5. Market separation
- Cash indices are NOT futures. NAS100/USTEC means Nasdaq-100 cash unless the user explicitly asks for futures.
- Futures NQ/ES/MNQ/MES are separate instruments and must never be silently substituted for cash indices.
- Crypto Breakout universe must be verified against Breakout support; exchange availability alone does not prove Breakout availability.

## 6. Current high-level status
### Forex
- Universe: 8 major currencies USD/EUR/GBP/JPY/CHF/CAD/AUD/NZD and their liquid crosses.
- Hourly Top-3 signal system exists conceptually but is paused until explicitly re-enabled.
- Primary data: Twelve Data pipeline for D1/H4/H1/M15/M5 plus M1/latest refresh.

### Crypto / Breakout
- Direct exchange data through GitHub runner is preferred over Twelve Data for crypto.
- Exchange route: Binance -> OKX -> Bybit.
- Useful research ingredients remain short-horizon momentum + H4/H1 structure + BTC-relative strength + taker-flow/market-breadth context + structural SL/dynamic RR, but **no version is validated as a main/live all-market engine**.
- V24 unchanged June validation: 42.75% resolved WR, avg RR 1.647, +0.132R but extreme date instability; V24 remains diagnostic only.
- V25 synchronized whole-market climax reversal is rejected.
- V26 macro-always-owns-direction failed true-blind May: 79 TP / 193 SL, 29.04% WR, -0.235R.
- V27 final random blind used untouched April 9, 2026 and delayed entry to a completed M15. Of 55 symbols with valid historical frames: 11 TP / 43 SL / 1 unresolved, 20.37% WR, 1.60R avg, -0.470R; 6h direction accuracy 21.82%, 24h accuracy 25.45%. Six universe symbols lacked usable historical frames. Historical OKX taker-flow coverage at that old timestamp was 0%.
- Do not rerun another random date just to seek a better result. The forced-position-on-every-coin idea is not robust enough for live use.
- **Preferred live direction is selective ranking:** BTC/market-quality first, D1/H4/H1 structure + short momentum, M15/M5 setup, fresh order flow only when available, structure-based SL, realistic RR, and explicit `NO TRADE / CHAOS` when market quality is poor. Rank only the strongest few setups rather than forcing every coin.

### Metals
- XAUUSD/XAGUSD are separate from crypto/index logic.
- Default workflow: H4/H1 bias; M15/M5 setup; M1 only for final timing/price refresh. Use structure, EMA, RSI, VWAP/Volume Profile/SR where data exists, plus DXY/US yields/Fed/high-impact US news.

### Cash indices
- Only cash indices by default: Nasdaq-100, S&P 500, Dow, Nikkei 225, DAX, plus other supported cash indices.
- Current Twelve Data Basic entitlement may block some index symbols such as NDX; never fake a cash-index price using futures.

### Futures NQ/ES
- Separate system, only when explicitly requested.
- Execution preference: MNQ/MES micros; structural SL first, then size contracts to approximately USD 500 maximum risk and roughly USD 1,500 target when structure supports ~1:3.
- User/platform realtime MNQ/MES price takes priority at final execution when supplied.

## 7. Live execution quality gate
Before issuing a current MARKET entry:
1. exact symbol refreshed now;
2. requested symbol == returned symbol;
3. timestamp/source shown internally and freshness validated;
4. relevant timeframes available;
5. no stale flag / execution-ready gate passes where implemented;
6. market structure and invalidation identified;
7. news/event risk checked if relevant;
8. Entry, SL, TP and RR calculated from the refreshed price.

## 8. Handoff phrase for a new chat
Preferred full message:
`Tiếp tục toàn bộ dự án Trading từ checkpoint GitHub mới nhất. Đọc docs/checkpoints/MASTER_TRADING_STATE.md và docs/checkpoints/CURRENT_HANDOFF.md trước, sau đó đọc checkpoint thị trường liên quan. Tiếp tục đúng trạng thái mới nhất, không quay lại phương pháp đã loại.`

Short form also works:
`Tiếp tục dự án Trading từ checkpoint GitHub mới nhất.`