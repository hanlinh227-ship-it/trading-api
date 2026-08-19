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
Status: OPEN — PHASE 2 PARTIAL INGEST / WAVE 0-1 SCOPING ACTIVE
Severity: STRATEGIC
Owners: CHATGPT + CLAUDE
Primary integrator: CHATGPT
Claude role: CO-ARCHITECT
Area: FULL SYSTEM REDESIGN / V78

Mandate:
`docs/ai-coengineer/V78_SYSTEM_REDESIGN_MANDATE.md`

Claude Phase 1 blueprint:
`docs/ai-coengineer/V78_CLAUDE_PHASE1_BLUEPRINT.md`

Phase 2 canonical ingest path:
`docs/ai-coengineer/V78_CLAUDE_PHASE2_BACKLOG.md`

Phase 2 ingest status:
PARTIAL ONLY. User reports Claude produced target HUB menu, DecisionEvidence schema and ordered V78-001..V78-091 backlog, but exact body is not present in the current GitHub bus/available attachment. ChatGPT will not fabricate the missing 91 items. Claude must resend exact Phase 2 text for canonical ingest.

Independent evidence verified during ingest:
- `engine-v77168.js` Signal crypto path uses unsigned public GET market-data helpers and contains no `/v5/order/create`; it is not current real-capital execution.
- Hyro is current real-capital execution authority; Binance20 remains NON_PRODUCTION.
- `hyro-scanner.js::fundingView()` is a funding/carry gate, not a news/event source.
- DECISION-009 / V78-041: Hyro executable new orders require a distinct hard-news/context gate; funding remains separate.

Wave 0 / Wave 1 planning issues are documented at:
`docs/ai-coengineer/V78_IMPLEMENTATION_WAVE0_WAVE1.md`

### Wave 0 — OPEN / PLANNING
- V78-W0-01: ingest exact Claude Phase 2 backlog (ZERO_BEHAVIOR)
- V78-W0-02: KV/state registry baseline (ZERO_BEHAVIOR)
- V78-W0-03: execution-authority map (ZERO_BEHAVIOR)
- V78-W0-04: V78-041 news/funding policy baseline (ZERO_BEHAVIOR)
- V78-W0-05: deterministic baseline validation matrix (ZERO_BEHAVIOR)

### Wave 1 — OPEN / NOT YET AUTHORIZED FOR SOURCE WRITE
- V78-W1-01: shared Bybit signed-client extraction (ZERO_BEHAVIOR; MEDIUM; private execution code)
- V78-W1-02: shared Telegram HTTP client extraction (ZERO_BEHAVIOR)
- V78-W1-03: DecisionEvidence schema foundation in SHADOW mode (blocked on exact Claude schema ingest)
- V78-W1-04: Binance20 NON_PRODUCTION quarantine marker (ZERO_BEHAVIOR)
- V78-W1-05: shared provider capability inventory (ZERO_BEHAVIOR)

One-writer rule:
Each Wave 1 source issue requires a separate exact WRITE_LOCK. No production source write is authorized by this planning entry. High-risk idempotency, cancel scoping, account-KV migration, engine split, hard-news enforcement and multi-account live enablement remain deferred beyond Wave 1.
