# AI WRITE LOCK

LOCKED: true
OWNER: CHATGPT
SCOPE: V78-026 H1 deterministic order identity + intent state machine ONLY
ACQUIRED: 2026-08-20

Protocol:
- One writer at a time.
- H1 ONLY: deterministic order identity + intent state machine + reconcile-by-orderLinkId before resubmit.
- Do not begin H2-H6 in this round.
- Never reset TRADING_STATE or delete/reset v775:books.
- Never weaken hard risk/freshness/structural-SL/news safeguards.
- Never restore Futures/TK2.
- Binance20 remains NON_PRODUCTION / QUARANTINED.
- No multi-account fan-out.
- Production Claude API remains paused; Claude.ai Web remains full co-engineer.
