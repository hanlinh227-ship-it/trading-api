# AI WRITE LOCK

LOCKED: false
OWNER: NONE
SCOPE: none
STARTED: null
BASE_SHA: 965e74435a70e60790419bda15627eb3d1089b82
PURPOSE: AI-002 documentation sync committed; awaiting Claude review

Protocol:
- Before modifying production source, set `LOCKED: true`, owner and scope.
- The other AI may review but must not write files in scope.
- Re-read HEAD before every source write.
- Release lock after commit and hand off review.
