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
Owners: CHATGPT + CLAUDE.AI WEB
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

### CLAUDE PRODUCTION API PAUSE — ACTIVE USER DIRECTIVE
Commit: `c61987415a3e53832a444466406df9ffe25951f9`.
Anthropic transport fail-closes before network fetch unless `CLAUDE_API_ENABLED=true`.
Do not re-enable or call the integrated Claude/Anthropic production API until the user explicitly asks.
This restriction does NOT apply to Claude.ai Web: Claude.ai Web remains a full co-engineer/optimizer/auditor/patch designer and may write through GitHub if its connector later has permission, subject to WRITE_LOCK.

### V78-014 — RESOLVED / VALIDATED
DecisionEvidence shadow-populate.
Final migration: `0c3dc007433c3e9afae1990d07d23c149742500a`.
Validation: `docs/ai-coengineer/V78-014_VALIDATION.txt`.
Signal and Hyro evidence remain additive/shadow only.

### V78-015 — RESOLVED / VALIDATED
Read-only Telegram Hub Evidence/Runtime view.
Source commit: `db2b48f5b96d36e411fbd2f93c0cc73e354fe213`.
Validation: `docs/ai-coengineer/V78-015_VALIDATION.txt`.
No trading behavior/KV write/threshold/execution-authority change.

### V78-016 — RESOLVED / VALIDATED
Entry Intelligence Foundation — shadow-only.
Source commit: `892f7fa8a77c75346c1d522ef93bf9fdf749dc7c`.
New `cloudflare-worker/providers/entry-intelligence.js` records market-specific reasoning from already-finalized Signal decisions to isolated key `v78016:entry_intelligence:signal`.
Read-only endpoint: `/evidence/entry-intelligence`.
Telegram Hub `••• Thêm` now exposes `🧭 Entry Intel` with WHY NOW / WHY PRICE / WHY SL / WHY TP-RR / INVALIDATION / freshness / evidence completeness / existing block reason.
No new score, threshold, ranking authority, execution authority, provider fetch, or trade gate was introduced.

### V78-017 — RESOLVED / VALIDATED
Manual analysis observability completion.
Source commit: `c6edbaba4ad393af79dbaabed05a2d26195d3c1d`.
Manual `/analyze` and Telegram single-symbol `runSymbol()` decisions now populate V78-002 DecisionEvidence and V78-016 Entry Intelligence only after the existing decision is finalized; writes are try/catch isolated and the returned decision object remains the original `a`.
Hub visible UI revision: `HUB-R11-ENTRY-INTEL-SHADOW`.
Validation: `docs/ai-coengineer/V78-017_VALIDATION.txt`.

### NEXT OPTIMIZATION BATCH
Status: READY FOR CHATGPT IMPLEMENTATION + LATER CLAUDE.AI WEB OPTIMIZATION

Priority work:
- shadow-compare Entry Intelligence against current decisions across Forex/Crypto/Metal/Index before granting any authority;
- quantify which evidence dimensions are systematically missing by market/session;
- improve Hub top-setup explanation from existing validated evidence;
- design market-specific policy adapters only after shadow evidence demonstrates gaps;
- keep high-risk Hyro execution hardening (idempotency, partial fills, restart/reconciliation, cancel scoping, multi-account foundation) separately scoped and reviewed.

Resume handoff for Claude.ai Web:
`docs/ai-coengineer/CLAUDE_RESUME_HANDOFF_2026-08-19.md`.

### Hard prohibitions
Never reset `TRADING_STATE`/`v775:books`, weaken risk/freshness/structural-SL/news safeguards, restore Futures/TK2, change Binance20 quarantine, fabricate data/test output, expose secrets, or silently expand execution authority.
