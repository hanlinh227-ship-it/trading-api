# AI WRITE LOCK

LOCKED: true
OWNER: CHATGPT
SCOPE: cloudflare-worker/hyro-execution.js
STARTED: 2026-08-19T11:23:00Z
BASE_SHA: f168a449d2012e4e6b018a02f5825cc4e1b5a277
PURPOSE: AI-001 isolate optional closedPnl telemetry from critical wallet/positions/orders

Protocol:
- Before modifying production source, set `LOCKED: true`, owner and scope.
- The other AI may review but must not write files in scope.
- Re-read HEAD before every source write.
- Release lock after commit and hand off review.
