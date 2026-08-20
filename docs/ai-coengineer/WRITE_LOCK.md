# AI WRITE LOCK

LOCKED: true
OWNER: CHATGPT
SCOPE: V78-027 signal-only production cleanup and Hub simplification
ACQUIRED: 2026-08-20
SUPERSEDES: V78-026 H1 cancelled by explicit user direction.

Protocol:
- One writer at a time.
- Production direction is Signal-only.
- Remove Hyro execution/runtime and Hyro Telegram surfaces from active production wiring.
- Preserve Signal engine, market data, entry intelligence, ranking and all existing risk/freshness/structural-SL/news protections.
- Preserve TRADING_STATE and v775:books Signal data.
- Never restore Futures/TK2.
- Binance20 remains NON_PRODUCTION / QUARANTINED.
- Production Claude API remains paused; Claude.ai Web remains co-engineer for Signal-only optimization.
