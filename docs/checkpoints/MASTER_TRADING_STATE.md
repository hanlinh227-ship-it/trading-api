# MASTER TRADING STATE

Updated: 2026-08-17 (UTC+7)
Purpose: canonical handoff/checkpoint for continuing the Trading project across new ChatGPT conversations.

## 1. Cross-chat protocol
- At the start of a new Trading chat, read this file first, then the market-specific checkpoint(s) below.
- Do not reconstruct strategy state from memory when a checkpoint exists.
- When a material rule, API path, symbol universe, risk rule, or validated backtest version changes, update the appropriate checkpoint and then update this master file.
- Never promote a new method only because it has one unusually strong backtest. Keep the last robust baseline until new unseen blind samples confirm improvement.
- Never present stale/web proxy prices as executable live prices. Refresh the exact requested symbol through the active API/feed immediately before any current-price/entry/hold decision.

## 2. Canonical checkpoint files
- `docs/checkpoints/FOREX_STATE.md`
- `docs/checkpoints/CRYPTO_BREAKOUT_STATE.md`
- `docs/checkpoints/METALS_STATE.md`
- `docs/checkpoints/CASH_INDICES_STATE.md`
- `docs/checkpoints/DATA_INFRA_STATE.md`

## 3. Universal analysis rules
- Separate market context from execution timing.
- Multi-timeframe sequence: HTF regime/bias -> structure -> setup -> LTF trigger -> structure-based SL -> realistic TP/liquidity target.
- Indicators must have distinct roles; avoid stacking redundant indicators.
- News/macro/event risk must be checked when relevant.
- Structure determines invalidation first. ATR/volatility is a buffer/floor, not a reason to invent an SL.
- Position sizing follows the SL and the allowed USD/% risk; never choose the SL from desired position size.
- If the user explicitly requests a forced-MARKET blind stress test, every symbol with valid data must receive BUY or SELL. This is a test condition, not automatically a live-trading rule.

## 4. Market separation
- Cash indices are NOT futures. NAS100/USTEC means Nasdaq-100 cash unless the user explicitly asks for futures.
- Futures NQ/ES/MNQ/MES are separate instruments and must never be silently substituted for cash indices.
- Crypto Breakout universe must be verified against Breakout support; exchange availability alone does not prove Breakout availability.

## 5. Current high-level status
### Forex
- Universe: 8 major currencies USD/EUR/GBP/JPY/CHF/CAD/AUD/NZD and their liquid crosses.
- Hourly Top-3 signal system exists conceptually but is paused until explicitly re-enabled.
- Primary data: Twelve Data pipeline for D1/H4/H1/M15/M5 plus M1/latest refresh.

### Crypto / Breakout
- Direct exchange data through GitHub runner is preferred over Twelve Data for crypto.
- Exchange route: Binance -> OKX -> Bybit; OKX has been the reliable source in recent tests.
- Current research direction: short-horizon momentum + H4/H1 structure + BTC-relative strength + actual taker order-flow confirmation + market breadth/regime; structural M15 SL and dynamic RR.
- V24 produced very strong unseen samples but is NOT yet promoted as a fully validated final engine; further locked unseen samples are required.

### Metals
- XAUUSD/XAGUSD are separate from crypto/index logic.
- Default workflow: H4/H1 bias; M15/M5 setup; M1 only for final timing/price refresh. Use structure, EMA, RSI, VWAP/Volume Profile/SR where data exists, plus DXY/US yields/Fed/high-impact US news.

### Cash indices
- Only cash indices by default: Nasdaq-100, S&P 500, Dow, Nikkei 225, DAX, plus other supported cash indices.
- Current Twelve Data Basic entitlement may block some index symbols such as NDX; never fake a cash-index price using futures.

## 6. Live execution quality gate
Before issuing a current MARKET entry:
1. exact symbol refreshed now;
2. requested symbol == returned symbol;
3. timestamp/source shown internally and freshness validated;
4. relevant timeframes available;
5. no stale flag / execution-ready gate passes where implemented;
6. market structure and invalidation identified;
7. news/event risk checked if relevant;
8. Entry, SL, TP and RR calculated from the refreshed price.

## 7. Handoff phrase for a new chat
User can write: `Tiếp tục dự án Trading từ checkpoint GitHub mới nhất.`
Then read this file and the required market checkpoint before answering.