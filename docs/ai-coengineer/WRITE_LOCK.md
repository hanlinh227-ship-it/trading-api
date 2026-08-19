# AI WRITE LOCK

LOCKED: true
OWNER: CHATGPT
SCOPE:
- docs/ai-coengineer/CLAUDE_TO_CHATGPT.md
- docs/checkpoints/CURRENT_HANDOFF.md
- docs/checkpoints/MASTER_TRADING_STATE.md
- docs/ai-coengineer/CHATGPT_TO_CLAUDE.md
- docs/ai-coengineer/OPEN_ISSUES.md
STARTED: 2026-08-19T11:55:00Z
BASE_SHA: 0ba80d2abefe7c8f835627eddb549993dae086c6
PURPOSE: Persist Claude AI-001 review, synchronize AI-002 checkpoints, and hand off docs review to Claude

Protocol:
- Before modifying production source, set `LOCKED: true`, owner and scope.
- The other AI may review but must not write files in scope.
- Re-read HEAD before every source write.
- Release lock after commit and hand off review.
