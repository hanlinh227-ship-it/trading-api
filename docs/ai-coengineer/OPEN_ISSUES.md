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
Status: OPEN — V78 IMPLEMENTATION-FORWARD WAVE 1 ACTIVE
Owners: CHATGPT + CLAUDE
Area: FULL SYSTEM REDESIGN

### V78-001 — RESOLVED
KV/state registry. Zero behavior.

### V78-002 — RESOLVED
DecisionEvidence schema. Zero behavior.

### V78-003 — RESOLVED
Hyro news-gate status. Zero behavior. Funding is not hard-news clearance.

### V78-004 — RESOLVED
DECISION-005 Binance20 NON_PRODUCTION source annotation applied. Claude reconfirmed quarantine intact: no production import in `index.js`, `hub-v77171.js`, or `engine-v77168.js`.

### V78-005 — RESOLVED
Execution authority map. Signal advisory has no order authority; Hyro is current safety-gated real-capital authority; Binance20 remains quarantined.

### V78-006 — RESOLVED
Baseline validation matrix including AI-tuning sanitize-only writes, CHALLENGE forced-DEMO propEnv invariant, and CI canonical-lock co-maintenance.

### V78-007 — RESOLVED
Provider capability inventory including market-data, execution, AI, GitHub and Telegram capability classes.

### V78-010 — RESOLVED / CLAUDE PASS
Shared Bybit HMAC primitive only.
Source: `bf2fee88abbf11b850758e76f1bcac6453644ebf`.
`V78-010b` signed-client semantic unification remains DEFERRED / NOT STARTED because current clients differ in credentials/mode, error shape and GET/POST behavior.

### V78-011 — RESOLVED / CLAUDE PASS
Shared Telegram transport across the seven proven-equivalent consumers plus `providers/telegram-client.js`.
Final migration HEAD in chain: `a27bd47c720476410a76ba78161ebc68b0a7aef2`.
`engine-v77168.js` Telegram `fetchTimeout` path intentionally excluded and deferred to V78-054.
`verifyTelegram` / webhook-secret handling intentionally untouched and deferred to V78-081.

### V78-012 — RESOLVED / CLAUDE PASS
Shared ATR primitive only: `providers/indicators.js:atrFromHLC` backs `engine-v77168.js` and `hyro-scanner.js`.
Source commit: `c60cfe8532fdd10b9eca1f7bbefe5024b1d3da70`.
Claude executed equivalence tests across multiple candle lengths/periods and confirmed byte-equivalent outputs to both originals.
EMA and RSI intentionally remain local because their implementations are genuinely non-equivalent.

### V78-013 — RESOLVED / AWAITING CLAUDE FRESH-HEAD REVIEW
Shared Anthropic Messages API transport only.
Source chain:
- provider: `60d0e37f833b02e51ceee6c2a6c467ca3f76d9f8`
- dual AI migration: `22a872e0ed9a945f68f97a505182a28b930a0738`
- reviewer + final source migration: `fed3556b5a01504107f84da3fd43fad5f52db0e9`
- deterministic validation evidence: `88e2fc617f3ae1103296267e3b3ade89ca2c987f`
New shared primitive: `cloudflare-worker/providers/anthropic-client.js` with `anthropicMessagesRequest` + `extractAnthropicText`.
DECISION-004 boundaries preserved: reviewer max_tokens policy, budget/cooldown, prompts and rich review parser remain separate from dual-ai fixed-token policy, lease arbiter, BUG_HUNT prompt and its different parser.
Validation file: `docs/ai-coengineer/V78-013_VALIDATION.txt` = PASS.

### V78-014 — NEXT / NOT STARTED
DecisionEvidence shadow-populate. Requires fresh Claude scope/patch after V78-013 independent verification. No production execution-authority change is allowed; initial population must be shadow/observability-first.

### Phase 2 integrity
Full verbatim Claude V78-001..V78-091 backlog/target HUB menu remains unavailable in retrievable GitHub material; do not fabricate it.

### Wave 1
ACTIVE. V78-010 through V78-013 have real source implementations. Next is V78-014 shadow DecisionEvidence. High-risk idempotency, cancel scoping, account-KV migration, engine split, production hard-news enforcement and multi-account live enablement remain separately scoped and must not be bundled into low-risk refactors.
