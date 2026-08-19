# AI WRITE LOCK

LOCKED: false
OWNER: NONE
SCOPE: none
STARTED: null
BASE_SHA: 0bbe2b0c0fccda112820cad1f8f65121ba0d8fce
PURPOSE: V78-002 DecisionEvidence schema documentation committed. No production behavior changed; awaiting Claude field-level review against exact Phase 2 schema.

Protocol:
- Before modifying production source, set `LOCKED: true`, owner and exact scope.
- The other AI may review but must not write files in scope.
- Re-read HEAD before every source write.
- Release lock after commit and hand off review.
