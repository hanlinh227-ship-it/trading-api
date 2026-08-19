# AI WRITE LOCK

LOCKED: false
OWNER: NONE
SCOPE: none
STARTED: null
BASE_SHA: ba85bd2b7fac3fe02cd066565f25b510730dad88
PURPOSE: V78-005 marked RESOLVED after Claude PASS. V78-004 remains blocked because exact Claude patch text is not retrievable. Ready for next scoped Wave 0 documentation issue.

Protocol:
- Before modifying production source, set `LOCKED: true`, owner and exact scope.
- The other AI may review but must not write files in scope.
- Re-read HEAD before every source write.
- For explicitly scoped IMPLEMENTABLE issues, implementation-forward mode applies.
- Release lock after commit and hand off review.
