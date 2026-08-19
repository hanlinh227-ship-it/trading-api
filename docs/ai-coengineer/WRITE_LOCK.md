# AI WRITE LOCK

LOCKED: true
OWNER: CHATGPT
SCOPE: V78-015 Hub Evidence/Runtime read-only status view + Claude API paused-state visibility
ACQUIRED: 2026-08-19
PURPOSE: Add a read-only Telegram Hub Evidence screen sourced only from V78-014 shadow DecisionEvidence, and visibly report Claude API paused/enabled state. No trading decision, risk, execution, threshold, state continuity, or existing callback semantics may change.

Protocol:
- Guard hub-v77171.js pre-patch blob SHA = 1551e0fb868a258b0b4965cef12f72c542259408.
- Do not reset TRADING_STATE/v775:books.
- Do not weaken risk/freshness/structural-SL/news safeguards.
- Do not restore Futures/TK2.
- Binance20 remains NON_PRODUCTION / QUARANTINED.
