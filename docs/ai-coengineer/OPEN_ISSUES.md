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
Status: OPEN — V78 IMPLEMENTATION-FORWARD WAVE 0 ACTIVE
Owners: CHATGPT + CLAUDE
Area: FULL SYSTEM REDESIGN

### V78-001 — RESOLVED
KV/state registry. Zero behavior.

### V78-002 — RESOLVED
DecisionEvidence schema. Zero behavior.

### V78-003 — RESOLVED
Hyro news-gate status. Zero behavior. Funding is not hard-news clearance.

### V78-004 — BLOCKED_ON_EXACT_PATCH_TEXT
DECISION-005 Binance20 NON_PRODUCTION source annotation for four Binance files. Exact Claude patch is still not retrievable by ChatGPT; no guessed private-execution-capable source change is allowed. IMPLEMENT_NOW when exact patch is present.

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

### V78-007 — IMPLEMENTED / CLAUDE REVIEW REQUIRED
File: `docs/ai-coengineer/V78_PROVIDER_CAPABILITY_INVENTORY.md`
Commit: `27d800f452fe5476df7bac037a0d7a5f0dc76c51`
Zero behavior.
Inventory separates Twelve Data, Massive, public Bybit/OKX Signal data, Hyro public context, Hyro private execution, DEMO execution and quarantined Binance USDM capability. It also defines provider/instrument/freshness/authority requirements for expanding intelligence across more markets and symbols.

### Phase 2 integrity
Full verbatim Claude V78-001..V78-091 backlog/target HUB menu remains unavailable in retrievable GitHub/session material; do not fabricate it.

### Wave 1
NOT STARTED. Source changes require exact scope + WRITE_LOCK + independent review. High-risk idempotency, cancel scoping, account-KV migration, engine split, production hard-news enforcement and multi-account live enablement remain separately scoped.
