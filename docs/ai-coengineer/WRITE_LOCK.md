# AI WRITE LOCK

LOCKED: false
OWNER: NONE
SCOPE: none
STARTED: null
BASE_SHA: 123a11f88ee10250ad7fbb3d92394d1697716047
PURPOSE: V78-005 execution authority map documentation committed. V78-004 remains blocked because the exact Claude four-file patch text is not retrievable in the current GitHub/session/file context; no guessed source change was made. No Wave 1+ source change started.

Protocol:
- Before modifying production source, set `LOCKED: true`, owner and exact scope.
- The other AI may review but must not write files in scope.
- Re-read HEAD before every source write.
- For an explicitly scoped IMPLEMENTABLE / IMPLEMENT_NOW issue with exact patch material, either AI may acquire the free lock and implement immediately.
- Release lock after commit and hand off review.
