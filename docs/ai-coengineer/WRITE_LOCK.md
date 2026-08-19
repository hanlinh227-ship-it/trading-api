# AI WRITE LOCK

LOCKED: true
OWNER: CHATGPT
SCOPE: V78-020 production live verification
ACQUIRED: 2026-08-20
PURPOSE: Deploy current main containing V78-020 fix, run exactly one production /run-now per forex/crypto/metal/index, compare immediately-prior snapshots, verify rescue-plan promotion evidence, persist exact evidence only if checks pass.

Protocol:
- One writer at a time.
- Never reset TRADING_STATE or delete/reset v775:books.
- Never weaken hard risk/freshness/structural-SL/news safeguards.
- Never restore Futures/TK2.
- Binance20 remains NON_PRODUCTION / QUARANTINED.
- Production Claude API remains paused; Claude.ai Web remains full co-engineer.
- No Hyro execution-authority change.
- Do not fabricate live evidence or retry-hide RATE_BUDGET_WAIT/BUSY.
