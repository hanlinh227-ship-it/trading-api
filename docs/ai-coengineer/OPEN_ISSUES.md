# AI OPEN ISSUES

## AI-001
Status: RESOLVED
Severity: CRITICAL
Owner: CHATGPT
Area: HYRO

Description:
`cloudflare-worker/hyro-execution.js` previously treated failure of any telemetry probe as full telemetry failure. `closedPnl` is non-critical for live position/risk management but could force `connected:false`.

Repair commit:
`1d6db32155c06d464f4da94746df73e110b9b294`

Reviewer: CLAUDE
Review result: PASS — 2026-08-19T11:40:00Z

## AI-002
Status: OPEN — REVIEW RESULT AVAILABLE IN CLAUDE CHAT / PERSISTENCE PENDING IF NEEDED
Severity: HIGH
Owner: CHATGPT
Reviewer: CLAUDE
Area: DOCS

Documentation commits:
- CURRENT_HANDOFF: `55651b19680da2ee1b63d9d980fde0ae131f0870`
- MASTER_TRADING_STATE: `9b50647940e0542df8a98461b9dc70488e8adc7c`

Claude reported PASS in chat, with one clarification request around legacy `profit lock/target ~1.20%` wording versus current dynamic target math. ChatGPT must resolve the wording/source evidence separately; no production-risk constant is changed by this issue.

## AI-003
Status: OPEN — PHASE 1 BLUEPRINT RECEIVED / CHATGPT INTEGRATION ACTIVE
Severity: STRATEGIC
Owners: CHATGPT + CLAUDE
Primary integrator: CHATGPT
Claude role: CO-ARCHITECT
Area: FULL SYSTEM REDESIGN / V78

Mandate:
`docs/ai-coengineer/V78_SYSTEM_REDESIGN_MANDATE.md`

Claude Phase 1 blueprint persisted at:
`docs/ai-coengineer/V78_CLAUDE_PHASE1_BLUEPRINT.md`

Phase 1 findings include:
- overlapping Telegram routers/verification/dedupe;
- duplicated Hyro risk/profile display logic;
- Signal vs Hyro analysis-pipeline duplication;
- provider/client duplication;
- Hyro idempotency/reconciliation/cancel-scope/state-machine weaknesses;
- lack of account/provider abstractions for future multi-account;
- orphaned non-production Binance20 path;
- AI runtime duplication requiring deliberate separation/shared primitives.

ChatGPT architecture decisions are recorded in `DECISIONS.md` (DECISION-004 through DECISION-008).

Next design step:
Claude should review ChatGPT decisions, challenge them where source evidence disagrees, then produce a Phase 2 implementation decomposition with atomic issues ordered by risk. Phase 2 remains DESIGN ONLY until ChatGPT creates scoped write issues.

No production source write is authorized by AI-003 yet.
