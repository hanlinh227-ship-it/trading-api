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

Claude reported PASS in chat, with one clarification request around legacy `profit lock/target ~1.20%` wording versus current dynamic target math. No production-risk constant is changed by this issue.

## AI-003
Status: OPEN — V78 IMPLEMENTATION-FORWARD WAVE 0 ACTIVE
Severity: STRATEGIC
Owners: CHATGPT + CLAUDE
Primary integrator: CHATGPT
Claude role: CO-ARCHITECT / REVIEWER / SECOND_ENGINEER / IMPLEMENTER
Area: FULL SYSTEM REDESIGN / V78

Mandate:
`docs/ai-coengineer/V78_SYSTEM_REDESIGN_MANDATE.md`

Phase 1 blueprint:
`docs/ai-coengineer/V78_CLAUDE_PHASE1_BLUEPRINT.md`

Phase 2 canonical ingest path:
`docs/ai-coengineer/V78_CLAUDE_PHASE2_BACKLOG.md`

Integrity status:
The complete verbatim target HUB menu and full V78-001..V78-091 body are still not available in the current GitHub bus/retrievable session context. ChatGPT will not fabricate missing Claude-authored content. Known mapping constraints remain preserved separately.

### Implemented Wave 0 items

#### V78-001 — RESOLVED
KV/state registry documentation.
- initial commit `a45b8f33672273ac0ae580bf6f6bee54a8c63893`
- Claude WARN corrections commit `b451a086336bb9a6e59dc84031a1866e46e591da`
- zero behavior change.

#### V78-002 — RESOLVED
DecisionEvidence schema documentation.
- initial commit `0bbe2b0c0fccda112820cad1f8f65121ba0d8fce`
- Claude DecisionAction correction incorporated in commit `e432a62cac0031223fda889a9b1a28dfe34ff18c`
- canonical action enum now preserves `MARKET_PLAN`, `LIMIT_PLAN`, `DATA_BLOCK`.
- zero behavior change.

#### V78-003 — IMPLEMENTED / CLAUDE REVIEW REQUIRED
Hyro news-gate status documentation.
- file: `docs/ai-coengineer/V78_HYRO_NEWS_GATE_STATUS.md`
- commit `b31aa8f364ba1fc7b210d0a1289bccd0f4df2125`
- documents that funding/carry and OI/ratio/orderbook/spread context exist, but current reviewed Hyro path does not prove an authoritative hard-news clearance gate.
- zero behavior change; production news enforcement remains a separate future issue.

### Current architecture evidence
- Signal crypto analysis path uses public unsigned market-data calls and is not current real-capital execution authority.
- Hyro is current real-capital execution authority; Binance20 remains NON_PRODUCTION.
- DECISION-009: funding cannot substitute for news/event evidence.

### Implementation-forward policy now active
`PROTOCOL.md`, `CLAUDE.md`, and `AGENTS.md` authorize both AIs to implement immediately when an issue is explicitly scoped as IMPLEMENTABLE / IMPLEMENT_NOW (or exact objective+scope+acceptance are already provided), WRITE_LOCK is free, no BLOCK applies, and hard prohibitions are respected.

Claude may self-acquire WRITE_LOCK and commit directly if its GitHub connector allows write. If connector returns 403, Claude must return exact patch/change material and ChatGPT should implement it immediately rather than restart design-only discussion.

### Wave 1
NOT STARTED by V78-001..V78-003. Every source issue requires its own exact WRITE_LOCK and independent review.

High-risk idempotency, cancel scoping, account-KV migration, engine split, hard-news production enforcement and multi-account live enablement remain separately scoped/deferred.
