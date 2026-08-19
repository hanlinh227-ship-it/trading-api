# AI WRITE LOCK

LOCKED: true
OWNER: CHATGPT
SCOPE:
- docs/ai-coengineer/V78_DECISION_EVIDENCE_SCHEMA.md
STARTED: 2026-08-19T12:55:00Z
BASE_SHA: 3e582aa0b34b8beaa97dda01f70b48a579cfff9a
PURPOSE: V78-002 only — document DecisionEvidence schema. Documentation-only / ZERO_BEHAVIOR. No production source modification authorized.

Protocol:
- Claude may READ/REVIEW but must not write the declared scope while this lock is active.
- No Wave 1+ source change is authorized.
- Re-read HEAD before every future production source write.
- Release lock after V78-002 documentation commit and hand off review.
