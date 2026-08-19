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
Status: OPEN — V78 IMPLEMENTATION-FORWARD WAVE 1 SCOPING
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
Execution authority map. Claude PASS fresh against current production import/fetch/scheduled chain. Signal advisory has no order authority; Hyro is current safety-gated real-capital authority; Binance20 remains quarantined.

### V78-006 — RESOLVED
File: `docs/ai-coengineer/V78_BASELINE_VALIDATION_MATRIX.md`
Initial commit: `a6c15364b4fc97eded938a480c5d6b990b8f0af4`
Claude WARN corrections resolved at `b9f4226961e29df0d0f1d9a23954a16f15221fc7`.
Added deterministic invariants:
- G-09 AI tuning authoritative writes must pass `sanitize()`/equivalent bounded validation;
- H-16 CHALLENGE execution environment remains forced DEMO through canonical `propEnv()` proxy/equivalent;
- Section 9.1 `.github/workflows/validate-cloudflare-v77.yml` canonical-lock co-maintenance.
Zero behavior.

### V78-007 — RESOLVED
File: `docs/ai-coengineer/V78_PROVIDER_CAPABILITY_INVENTORY.md`
Commit: `27d800f452fe5476df7bac037a0d7a5f0dc76c51`
Claude review completed in Wave 0 handoff. Zero behavior.

### V78-010 — RESOLVED
Shared Bybit HMAC primitive deduplication only.
Final source commit: `bf2fee88abbf11b850758e76f1bcac6453644ebf`.
Lock release commit: `5dd75b7441a759dab72123a5ce6a8d5202abf7f6`.
Claude independently verified PASS at HEAD `5dd75b7441a759dab72123a5ce6a8d5202abf7f6`: sole `hmacHex` source is `cloudflare-worker/providers/bybit-signed-client.js`; all four Hyro consumers import it exactly once; signer/public-call semantics, credentials, mode routing, GET/POST behavior, error shapes, endpoints and KV keys unchanged.
`V78-010b` semantic signed-client unification remains explicitly DEFERRED / NOT STARTED.

### V78-011 — SELECTED / SCOPING ONLY — NO IMPLEMENTATION YET
Purpose: narrow Telegram transport deduplication without changing routing, keyboard/UI behavior, authorization, webhook verification, message text, execution authority or notification semantics.

Exact candidate scope to verify before implementation:
- `cloudflare-worker/index.js`: Telegram transport helpers `tg(...)` and `send(...)` only.
- Search current production modules for byte-/behavior-equivalent Telegram Bot API transport helpers before choosing any additional consumer.
- New shared provider, if equivalence is proven: `cloudflare-worker/providers/telegram-client.js` (transport primitive only).
- `verifyTelegram` / webhook-secret verification is OUT OF SCOPE and deferred to V78-081.

Acceptance criteria before implementation can be marked IMPLEMENTABLE:
1. Inventory every production Telegram Bot API call and classify transport vs presentation/routing/auth.
2. Extract only proven-equivalent HTTP transport; preserve exact method, URL, headers, JSON body, response parsing and thrown-error behavior per migrated caller.
3. Do not move keyboards, callback routing, command parsing, chat authorization, webhook-secret verification, notification dedupe/KV keys, or trading logic.
4. No Telegram message text or reply_markup behavior changes.
5. No Hyro execution/risk/freshness/news/SL behavior changes.
6. `verifyTelegram` remains untouched and deferred to V78-081.
7. `node --check` every changed JS file; grep/search confirms no unintended duplicate of the migrated transport remains and no production import cycle is introduced.
8. Acquire WRITE_LOCK only after Claude/ChatGPT confirms exact consumers and replacement blocks from fresh HEAD.

### Phase 2 integrity
Full verbatim Claude V78-001..V78-091 backlog/target HUB menu remains unavailable in retrievable GitHub material; do not fabricate it.

### Wave 1
OPEN with V78-011 selected for exact-scope verification only. No V78-011 source implementation has begun. V78-010b remains deferred. High-risk idempotency, cancel scoping, account-KV migration, engine split, production hard-news enforcement and multi-account live enablement remain separately scoped.
