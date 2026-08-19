# AI WRITE LOCK

LOCKED: false
OWNER: NONE
SCOPE: none
STARTED: null
BASE_SHA: 1d6db32155c06d464f4da94746df73e110b9b294
PURPOSE: AI-001 repair committed; awaiting Claude review

Protocol:
- Before modifying production source, set `LOCKED: true`, owner and scope.
- The other AI may review but must not write files in scope.
- Re-read HEAD before every source write.
- Release lock after commit and hand off review.
