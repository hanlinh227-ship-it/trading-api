# AI WRITE LOCK

LOCKED: true
OWNER: CHATGPT
SCOPE:
- CLAUDE.md
- AGENTS.md
- docs/ai-coengineer/PROTOCOL.md
STARTED: 2026-08-19T13:06:00Z
BASE_SHA: ae2849350d27ba7c714c8e787e665e43af505718
PURPOSE: Documentation-only governance update: authorize implementation-forward co-engineering so Claude may self-acquire WRITE_LOCK for explicitly IMPLEMENTABLE scoped issues and commit directly when connector permissions allow. No production source modification authorized by this governance lock.

Protocol:
- Claude may READ/REVIEW but must not write the declared governance scope while this lock is active.
- No production source or trading-state change is authorized.
- Release after governance commits.
