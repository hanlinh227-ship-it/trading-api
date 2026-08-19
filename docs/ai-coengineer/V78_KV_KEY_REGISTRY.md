# V78-001 — TRADING_STATE / KV KEY REGISTRY

Status: IMPLEMENTED — DOCUMENTATION ONLY / ZERO_BEHAVIOR
Owner: CHATGPT
Reviewer: CLAUDE
Recorded against production source at V78-001 implementation time.

## Purpose
Create a canonical inventory of current `TRADING_STATE` keys before any V78 state migration, account scoping, engine split, notification consolidation, or multi-account work.

This issue changes **no runtime behavior**. It does not rename, delete, copy, reset, migrate, or rewrite any production KV value.

## Hard invariants
- `TRADING_STATE` namespace must not be reset.
- `v775:books` must not be deleted/reset/recreated as part of a release.
- Existing keys remain authoritative until a separately reviewed additive migration is implemented.
- Future account-scoped migration must use dual-read/additive-write/cutover semantics; never rename-in-place while live state is needed.
- UNKNOWN/MISSING state must not be converted to fabricated zero values when meaning changes.
- NON_PRODUCTION keys are documented separately and are not authorization to activate their runtime.

---

## 1. SIGNAL / ADVISORY ENGINE

Owner source: `cloudflare-worker/engine-v77168.js`

| Key / prefix | Type | Primary owner | Purpose / lifecycle | Migration status |
|---|---|---|---|---|
| `v775:books` | singleton JSON | Signal engine | Canonical Signal live/advisory books. Protected durable state used for active/pending/watch lifecycle. | **PROTECTED — DO NOT RESET** |
| `v775:history` | singleton/history JSON | Signal engine | Signal lifecycle history. | Preserve; migration not authorized |
| `v775:last_run` | singleton JSON | Signal engine | Last scan/run metadata. | Preserve |
| `v775:run_lock` | singleton lease/lock | Signal engine | Serializes scan/run work and prevents overlapping run execution. | Preserve until explicit lock redesign |
| `v779:news_clear:{symbol}` | dynamic prefix | Signal engine | Per-symbol temporary news clearance state. | Preserve; V78 news semantics redesign pending |
| `v779:crypto_broad_cache` | singleton cache | Signal engine | Crypto broad-discovery cache. | Cache; may later be replaced additively |
| `v7712:scan:{group}` | dynamic prefix | Signal engine / Health reader | Latest per-market scan snapshots such as crypto/forex/metal/index. `system-health.js` reads this prefix for scan-memory/status. | Preserve |
| `v7712:order_history` | singleton/history JSON | Signal engine | Signal order/advisory lifecycle history. | Preserve |
| `v7713:shadow_setups` | singleton/shadow state | Signal engine | Shadow setup/evaluation state. | Preserve until explicit deprecation |
| `v77164:context:{...}` | dynamic prefix | Signal engine | Cached/current context evidence by instrument/context scope. | Preserve; candidate for future `DecisionEvidence` linkage |

Notes:
- Current Signal crypto market-data path is advisory/public-data; this registry entry does not grant execution authority.
- `system-health.js` also reads `v775:books` and `v7712:scan:*`.

---

## 2. HUB / HYRO PROFILE SETUP

Owner source: `cloudflare-worker/hub-v77171.js`, shared profile reader/writer in `hyro-execution.js`.

| Key / prefix | Type | Primary owner(s) | Purpose / lifecycle | TTL | Migration status |
|---|---|---|---|---|---|
| `v7717:hyro:profile` | singleton JSON | HUB + Hyro execution | Current Hyro program/profile configuration. Both HUB and execution currently access the same key. | none | Preserve; V78 canonical-profile refactor pending |
| `v77171:hyro:draft` | singleton temporary JSON | HUB wizard | Temporary Hyro configuration wizard draft. | 1800s | Ephemeral; safe to replace only in HUB redesign |

Important architecture note: V78 DECISION-007 requires one canonical Hyro risk/profile view; documenting the shared key here does not preserve duplicated calculation logic.

---

## 3. HYRO EXECUTION / TELEMETRY / DAILY RISK

Owner source: `cloudflare-worker/hyro-execution.js`.

| Key / prefix | Type | Purpose / lifecycle | TTL | Readers / writers | Migration status |
|---|---|---|---|---|---|
| `v77173:hyro:control` | singleton JSON | Manual pause/control state. | none | `getHyroControl`, `setHyroPaused`; runtime/HUB/health consume | **PROTECTED operational control** |
| `v7718:hyro:execution_state` | singleton JSON | Latest execution/telemetry status, connectivity, diagnostics and degraded state. | none | `getHyroTelemetry` writes; status/diagnostics consume | Preserve |
| `v7718:hyro:execution_history` | singleton/history JSON | Hyro execution history maintained by execution layer. | source-defined | Hyro execution | Preserve |
| `v7718:hyro:day:{YYYY-MM-DD}` | dynamic daily prefix | Day-start equity, peak equity, drawdown, P/L-from-day-start, realized freshness and daily risk state. | 172800s | `getHyroTelemetry` read/write | **HIGH SAFETY — additive migration only** |
| `v7718:hyro:intent:{intentKey}` | dynamic idempotency prefix | Execution intent/idempotency protection. | source-defined | `executeHyroPlan` | **HIGH SAFETY — do not change until dedicated idempotency issue** |

V78 safety rule: future account scoping must not lose day-start/peak equity or idempotency continuity during cutover.

---

## 4. HYRO RUNTIME / PORTFOLIO / POSITION MANAGEMENT

| Key / prefix | Owner source | Purpose | TTL | Migration status |
|---|---|---|---|---|
| `v7718:hyro:runtime` | `hyro-runtime.js` | Last auto-cycle result/reason/scan/execution/runtime metadata. | none | Preserve; candidate future account scope |
| `v771814:hyro:portfolio` | `hyro-portfolio-guard.js` | Last entry timing/symbol/side for portfolio spacing/diversification guard. | none | Preserve; candidate future account scope |
| `v771811:hyro:manage:{symbol}` | `hyro-position-manager.js` | Per-symbol position-management state: initial SL/qty, TP placement flags/orders, BE/trailing lifecycle. | default 604800s | **HIGH SAFETY — additive migration only** |
| `v771818:hyro:review:{symbol}` | `hyro-position-review.js` | Per-symbol HOLD/TIGHTEN/CUT review result. | default 604800s | Preserve |
| `v771818:hyro:review:last` | `hyro-position-review.js` | Last review cycle summary and cadence guard. | default 604800s | Preserve |
| `v7718:hyro:demo_test:last` | `hyro-demo-test.js` | Latest DEMO execution/full-cycle test state. | none | Test-only state; preserve while demo validator exists |

Critical note: `v771811:hyro:manage:{symbol}` currently matches state to live positions using existing logic. V78 must not rename or account-scope this key before a dedicated migration/reconciliation design proves lifecycle continuity.

---

## 5. HYRO TELEGRAM NOTIFICATION STATE

Owner source: `cloudflare-worker/index.js`.

| Key / prefix | Purpose | TTL / lifecycle | Migration status |
|---|---|---|---|
| `v7718:hyro:notify:entry:{id}` | Dedupes entry notifications by order/order-link/fallback identity. | 604800s | Preserve until NotificationBus shadow/cutover issue |
| `v7718:hyro:notify:close:{...}` | Dedupes closure notifications using closure signature. | 604800s | Preserve until NotificationBus shadow/cutover issue |
| `v7718:hyro:notify:snapshot` | Previous Hyro position/closed-PnL notification snapshot used to detect closures/delta. | persistent/latest snapshot | **Do not drop during notification migration** |

These keys are behavior state, not cosmetic UI cache. NotificationBus migration must be additive/shadow-first.

---

## 6. SYSTEM HEALTH

Owner source: `cloudflare-worker/system-health.js`.

| Key | Purpose | TTL | Migration status |
|---|---|---|---|
| `v771817:health:last` | Latest health audit result. | none | Preserve |
| `v771845:health:alert_state` | Alert signature/cooldown/reminder/dedupe state. | 604800s | Preserve; model candidate for future NotificationBus |
| `v771817:health:last_full` | Last full-health audit timestamp/version; used by cadence gate. | none | Preserve |
| `v771845:health:scan_memory` | Last-seen per-group scan timestamps when direct snapshot absent. | 604800s | Preserve |

Cross-reads:
- health reads `v775:books`;
- health reads `v7712:scan:{group}`;
- health reads `v7718:hyro:runtime`;
- full health invokes current Hyro profile/control/telemetry readers.

---

## 7. RELEASE STATE

Owner source: `cloudflare-worker/release-notifier.js`.

| Key | Purpose | Migration status |
|---|---|---|
| `v771818:release:last_announced` | Prevents repeated Telegram release announcement for the same version. | Preserve until NotificationBus/release redesign |

---

## 8. ADAPTIVE TUNING / HUB UX

| Key | Owner source | Purpose | TTL / fallback | Migration status |
|---|---|---|---|---|
| `v771824:adaptive:tuning` | `adaptive-tuning.js` | Current bounded adaptive Signal/Hyro soft tuning state. | persistent | Preserve |
| `v771823:adaptive:tuning` | `adaptive-tuning.js` | Legacy read fallback for continuity. | read fallback only | **Do not delete until explicit fallback retirement** |
| `v771826:hub:ux` | `hub-ux-tuning.js` | Current bounded HUB UX preset/density/display state. | 2592000s | Preserve until HUB redesign migration |

Hard risk is not stored/authorized by adaptive tuning; source guardrails explicitly keep Hyro risk untouched.

---

## 9. AI GOVERNANCE / ARBITER

Owner source: `cloudflare-worker/ai-arbiter.js`.

| Key | Purpose | TTL | Migration status |
|---|---|---|---|
| `v771824:ai:governance` | Durable AI governance runtime state/last action. | 2592000s when written | Preserve |
| `v771824:ai:lease` | Runtime AI lease used to serialize mutable AI action. | lease write 600s; release marker 60s | Preserve until AI runtime redesign |
| `v771824:ai:proposals` | Bounded recent AI engineering/source proposals. | 2592000s | Preserve |

This runtime lease is separate from the GitHub documentation `WRITE_LOCK.md` used by ChatGPT/Claude web co-engineering.

---

## 10. CLAUDE REVIEWER RUNTIME

Owner source: `cloudflare-worker/claude-reviewer.js`.

| Key | Purpose | TTL / lifecycle | Migration status |
|---|---|---|---|
| `v771821:claude:last` | Latest Claude reviewer run/result. | review writes use 1209600s | Preserve |
| `v771821:claude:budget` | Daily review count/token/cooldown budget. | 172800s | Preserve |
| `v771821:claude:release` | Tracks reviewed release/version to avoid duplicate release review. | 2592000s | Preserve |
| `v771821:claude:error_sig` | Health incident signature already reviewed. | 604800s | Preserve |
| `v771821:claude:daily_system_audit` | Daily system-audit cadence/result state. | source-defined | Preserve |
| `v771822:claude:overnight` | Legacy/time-bounded overnight review cadence state. | source-defined | Preserve until explicit retirement |
| `v771817:health:last` | Cross-read, not Claude-owned. | — | See Health section |
| `v775:books` | Cross-read snapshot, not Claude-owned. | — | Protected Signal state |
| `v7718:hyro:runtime` | Cross-read snapshot, not Claude-owned. | — | See Hyro Runtime section |

---

## 11. DUAL-AI INTERVENTION

Owner source: `cloudflare-worker/dual-ai-intervention.js`.

| Key | Purpose | TTL | Migration status |
|---|---|---|---|
| `v771824:dual_ai:intervention` | Latest bounded dual-AI runtime/tuning intervention state. | default 2592000s; error/missing-key paths may use 86400s | Preserve |
| `v771826:dual_ai:hub_notified` | One-time/deduped Telegram notice for intervention/HUB update. | 2592000s | Preserve until NotificationBus migration |

Cross-reads include health, Hyro runtime, Signal books, adaptive tuning and HUB UX state.

---

## 12. NON_PRODUCTION / QUARANTINED STATE

Per DECISION-005 these modules are not current production authority and must not be activated by V78-001.

| Key | Owner source | Purpose | Production authority |
|---|---|---|---|
| `v771840:binance20:state` | `binance-futures20-runtime.js` | Standalone Binance USDM $20 runtime state (day/trades/realized/loss streak/last order). | **NON_PRODUCTION / QUARANTINED** |

Documenting this key does not authorize imports, routes, scheduled execution, credentials, or live enablement.

---

## 13. OWNERSHIP / MIGRATION CLASSIFICATION

### Category A — Capital/state critical
Never rename/delete/reset in-place:
- `v775:books`
- `v77173:hyro:control`
- `v7718:hyro:day:*`
- `v7718:hyro:intent:*`
- `v771811:hyro:manage:*`
- `v7718:hyro:notify:snapshot`

### Category B — Operational durable state
Preserve through refactors; migrate additively when necessary:
- Hyro profile/execution/runtime/portfolio/review state
- Signal history/run/scan/context state
- health alert/cadence state
- adaptive/AI/Claude runtime state
- release notification state

### Category C — Ephemeral/cache/dedupe
May later be replaced only with explicit cutover/parity plan:
- broad cache
- wizard draft
- notification dedupe keys
- scan-memory cache
- temporary AI lease

### Category D — Non-production
Must remain isolated unless a future issue explicitly promotes an adapter:
- `v771840:binance20:state`

---

## 14. V78 FUTURE ACCOUNT-SCOPED TARGET — DESIGN NOTE ONLY

Potential future shape, **not implemented by V78-001**:

```text
acct:{accountId}:profile
acct:{accountId}:control
acct:{accountId}:day:{YYYY-MM-DD}
acct:{accountId}:intent:{intentId}
acct:{accountId}:position:{symbol}
acct:{accountId}:runtime
acct:{accountId}:portfolio
```

Required migration discipline:
1. introduce new keys additively;
2. dual-read with old key fallback;
3. shadow/dual-write where safe;
4. verify state parity and hard-stop continuity;
5. cut over one account at a time;
6. retain legacy read fallback for an explicit soak window;
7. retire old keys only in a separate reviewed issue.

No step above is authorized by this documentation issue.

---

## 15. V78-001 ACCEPTANCE CHECK

- [x] Registry documents Signal, HUB, Hyro execution/runtime/management/review, health, release, tuning, AI governance, Claude reviewer, dual-AI and quarantined Binance20 state.
- [x] `v775:books` is explicitly protected.
- [x] Hyro daily/idempotency/position-management state is marked high-safety/additive-only.
- [x] Readers/writers/cross-reads are identified at subsystem level.
- [x] No production key is renamed/deleted/reset.
- [x] No source behavior changed.
- [x] No Wave 1+ source work is started.

## Reviewer request
Claude should independently search current `cloudflare-worker/` for KV string literals and report any missing production key/prefix, incorrect ownership, TTL mismatch, or key whose behavior/state criticality is understated. Reviewer should return PASS/WARN/BLOCK for **V78-001 documentation accuracy only**.
