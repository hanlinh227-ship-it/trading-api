# AI WRITE LOCK

LOCKED: false
OWNER: NONE
SCOPE: none
STARTED: null
BASE_SHA: 6cd6e34824e2259d3c7482e7f41980c46ae656bc
PURPOSE: V78-007 resolved after Claude-confirmed six-provider inventory correction. Wave 0 documentation foundation is complete except V78-004 remains blocked on exact four-file patch text. Wave 1 may open only as a separately locked issue with exact scope and acceptance criteria.

Protocol:
- Before modifying production source, set `LOCKED: true`, owner and exact scope.
- The other AI may review but must not write files in scope.
- Re-read HEAD before every source write.
- For explicitly scoped IMPLEMENTABLE issues, implementation-forward mode applies.
- Release lock after commit and hand off review.
