# AI WRITE LOCK

LOCKED: true
OWNER: CHATGPT
SCOPE: V78-026 H1 deterministic order identity + intent state machine ONLY
ACQUIRED: 2026-08-20
BLOCKED: PRE-DEPLOY DEMO ACCEPTANCE — GitHub Actions is missing HYRO_BYBIT_API_KEY / HYRO_BYBIT_API_SECRET. Cloudflare preview inherited the Worker secrets but Bybit private DEMO requests from Cloudflare egress returned HTTP 403, so this does not satisfy the required real DEMO acceptance test.

Protocol:
- One writer at a time.
- H1 ONLY: deterministic order identity + intent state machine + reconcile-by-orderLinkId before resubmit.
- Do not merge/deploy H1 until the real DEMO order + ambiguous-response-loss retry test pass from a permitted network path.
- Do not begin H2-H6 in this round.
- Never reset TRADING_STATE or delete/reset v775:books.
- Never weaken hard risk/freshness/structural-SL/news safeguards.
- Never restore Futures/TK2.
- Binance20 remains NON_PRODUCTION / QUARANTINED.
- No multi-account fan-out.
- Production Claude API remains paused; Claude.ai Web remains full co-engineer.
