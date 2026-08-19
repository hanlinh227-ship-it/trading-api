# AI WRITE LOCK

LOCKED: false
OWNER: NONE
SCOPE: none
STARTED: null
BASE_SHA: null
PURPOSE: none

Protocol:
- Before modifying production source, set `LOCKED: true`, owner and scope.
- The other AI may review but must not write files in scope.
- Re-read HEAD before every source write.
- Release lock after commit and hand off review.
