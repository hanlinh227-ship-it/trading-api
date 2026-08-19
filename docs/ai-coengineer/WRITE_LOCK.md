# AI WRITE LOCK

LOCKED: true
OWNER: CHATGPT
SCOPE: V78-013 shared Anthropic transport primitive — providers/anthropic-client.js + claude-reviewer.js + dual-ai-intervention.js only
ACQUIRED: 2026-08-19
PURPOSE: Extract only the proven-equivalent Anthropic Messages API HTTP transport + text extraction. Preserve DECISION-004 separation of max_tokens policy, prompts, budget/cooldown governance, lease arbiter, and review-schema parsing.

Protocol:
- Verify claude-reviewer.js blob SHA = a1b63e5cf662922e6adaff6075a2fa8299026254 before write.
- Verify dual-ai-intervention.js blob SHA = bcd17b9cce78f58428488a74cd58e8201001231f before write.
- Do not reset TRADING_STATE/v775:books.
- Do not weaken risk/freshness/structural-SL/news safeguards.
- Do not restore Futures/TK2.
- Binance20 remains NON_PRODUCTION / QUARANTINED.
