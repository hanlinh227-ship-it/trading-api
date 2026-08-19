# AI OPEN ISSUES

## AI-001
Status: RESOLVED
Severity: CRITICAL
Owner: CHATGPT
Area: HYRO
Repair commit: `1d6db32155c06d464f4da94746df73e110b9b294`
Reviewer: CLAUDE — PASS.

## AI-002
Status: OPEN — DOC REVIEW RESULT AVAILABLE
Owner: CHATGPT
Reviewer: CLAUDE
Area: DOCS
CURRENT_HANDOFF/MASTER sync was reviewed PASS with a wording clarification only; no production-risk constant changed.

## AI-003
Status: OPEN — V78 IMPLEMENTATION-FORWARD ACTIVE
Owners: CHATGPT + CLAUDE
Area: FULL SYSTEM REDESIGN

### V78-001 through V78-007 — RESOLVED
Governance/baseline foundation complete: KV registry, DecisionEvidence schema, Hyro news-gate status, Binance20 quarantine, execution authority map, baseline validation matrix, provider capability inventory.

### V78-010 — RESOLVED / CLAUDE PASS
Shared Bybit HMAC primitive only. V78-010b remains DEFERRED / NOT STARTED.

### V78-011 — RESOLVED / CLAUDE PASS
Shared Telegram transport. `engine-v77168.js` timeout transport deferred V78-054; `verifyTelegram` deferred V78-081.

### V78-012 — RESOLVED / CLAUDE PASS
Shared ATR primitive only. EMA/RSI remain separate due real semantic divergence.

### V78-013 — RESOLVED / VALIDATED
Shared Anthropic transport only; DECISION-004 boundaries preserved.
Final source migration: `fed3556b5a01504107f84da3fd43fad5f52db0e9`.
Validation: `docs/ai-coengineer/V78-013_VALIDATION.txt`.

### CLAUDE API PAUSE — ACTIVE USER DIRECTIVE
Commit: `c61987415a3e53832a444466406df9ffe25951f9`.
Anthropic transport fail-closes before network fetch unless `CLAUDE_API_ENABLED=true`.
Do not re-enable or call Claude API until the user explicitly asks.

### V78-014 — RESOLVED / VALIDATED
DecisionEvidence shadow-populate.
Final migration: `0c3dc007433c3e9afae1990d07d23c149742500a`.
Validation: `docs/ai-coengineer/V78-014_VALIDATION.txt`.
Signal and Hyro evidence remain additive/shadow only.

### V78-015 — IMPLEMENTED / VALIDATED / AWAITING LATER CLAUDE REVIEW
Read-only Telegram Hub Evidence/Runtime view.
Source commit: `db2b48f5b96d36e411fbd2f93c0cc73e354fe213`.
Validation: `docs/ai-coengineer/V78-015_VALIDATION.txt`.
No trading behavior/KV write/threshold/execution-authority change.

### NEXT BATCH — ENTRY INTELLIGENCE FOUNDATION
Status: QUEUED FOR DESIGN/SHADOW IMPLEMENTATION
Owner: CHATGPT while Claude unavailable; Claude later optimizes/reviews from fresh HEAD.

Required scope:
- market-specific reasoning for Forex / Crypto / Metals / Index Cash;
- explicit regime + location + trigger + freshness + RR + invalidation evidence;
- preserve current production output/authority initially through shadow comparison;
- no loosening simply to increase trade count;
- later expose compact WHY NOW / BLOCK REASON / FRESHNESS / RR in Hub;
- high-risk Hyro execution hardening remains separately scoped.

Resume handoff for Claude:
`docs/ai-coengineer/CLAUDE_RESUME_HANDOFF_2026-08-19.md`.

### Hard prohibitions
Never reset `TRADING_STATE`/`v775:books`, weaken risk/freshness/structural-SL/news safeguards, restore Futures/TK2, change Binance20 quarantine, fabricate data/test output, expose secrets, or silently expand execution authority.
