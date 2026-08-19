# AI WRITE LOCK

LOCKED: false
OWNER: NONE
SCOPE: none
STARTED: null
BASE_SHA: 040e8331a844343291abd84c6992c8bb38ba52b8
PURPOSE: Implementation-forward co-engineering policy committed to PROTOCOL.md, CLAUDE.md and AGENTS.md. Claude may self-acquire WRITE_LOCK for explicitly scoped IMPLEMENTABLE issues when connector permissions allow. No production behavior changed.

Protocol:
- Before modifying production source, set `LOCKED: true`, owner and exact scope.
- The other AI may review but must not write files in scope.
- Re-read HEAD before every source write.
- Release lock after commit and hand off review.
