# AI WRITE LOCK

LOCKED: false
OWNER: NONE
SCOPE: none
STARTED: null
BASE_SHA: a45b8f33672273ac0ae580bf6f6bee54a8c63893
PURPOSE: V78-001 KV key registry committed as documentation-only zero-behavior change; awaiting Claude review. No Wave 1+ source change started.

Protocol:
- Before modifying production source, set `LOCKED: true`, owner and exact scope.
- The other AI may review but must not write files in scope.
- Re-read HEAD before every source write.
- Release lock after commit and hand off review.
