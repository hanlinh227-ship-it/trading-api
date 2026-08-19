# V78-006 — DETERMINISTIC BASELINE VALIDATION MATRIX

Status: RESOLVED — DOCUMENTATION ONLY / ZERO_BEHAVIOR
Owner: CHATGPT
Reviewer: CLAUDE

## Purpose
Define deterministic/static invariants every later V78 refactor must preserve. V78-006 changes no production JavaScript, trading behavior, provider, KV, risk, order or Telegram route.

---

## 1. Global safety invariants

| ID | Baseline invariant | Deterministic evidence | Failure |
|---|---|---|---|
| G-01 | `TRADING_STATE` is never reset by release/refactor. | No namespace reset/delete/recreate logic. | BLOCK |
| G-02 | `v775:books` is never destructively deleted/reset/reinitialized. | Inspect changed readers/writers/deletes. | BLOCK |
| G-03 | No secret/API key/private key/token is committed. | Diff/source secret scan. | BLOCK |
| G-04 | UNKNOWN/MISSING financial state is not silently fabricated as PASS/0/LIVE. | Missing-data branch inspection. | BLOCK |
| G-05 | HTTP success does not imply fill without authoritative exchange state. | Ack/fill/reconciliation inspection. | BLOCK |
| G-06 | Timeout does not imply failed order. | Preserve ambiguous/reconciling state before retry. | BLOCK |
| G-07 | One-writer WRITE_LOCK applies per implementation issue. | Lock/commit/handoff history. | BLOCK |
| G-08 | Legacy Futures Signal and Hyro TK2 are not restored. | Import/route/source inspection. | BLOCK |
| G-09 | AI tuning may persist only sanitized output; raw/unbounded AI proposal must never become authoritative tuning state. | Verify the canonical tuning write path passes proposed tuning through `sanitize()` (or canonical successor with equivalent bounded validation) before KV/state write; direct unsanitized write is BLOCK. | BLOCK |

---

## 2. Signal advisory baseline

Current authority source: `V78_EXECUTION_AUTHORITY_MAP.md`.

| ID | Expected behavior | Validation |
|---|---|---|
| S-01 | `MARKET_PLAN` / `LIMIT_PLAN` are advisory labels, not orders. | Signal refactor must not gain private order-create authority accidentally. |
| S-02 | Signal crypto public Bybit/OKX data has no production order authority. | Inspect import chain/private endpoints. |
| S-03 | `DATA_BLOCK` remains distinct from strategy `NO_TRADE`. | Preserve action/reason semantics. |
| S-04 | STALE/MISSING cannot be relabeled LIVE. | Preserve timestamp/age evidence. |
| S-05 | Structural SL and freshness/news safeguards are not weakened to increase plans. | Compare gate call sites/thresholds. |
| S-06 | Existing signal notification dedupe remains until separately migrated. | Preserve `v771816:signal:auto_notify:{sig}` / 1800s semantics. |

---

## 3. Hyro execution baseline

Current real-capital execution authority: Hyro private Bybit stack.

### 3.1 Critical telemetry

| ID | Baseline | Validation |
|---|---|---|
| H-01 | wallet, positions, orders are critical. | Critical failure keeps new execution fail-closed. |
| H-02 | `closedPnl` is optional/degradable. | closedPnl-only failure does not force disconnected. |
| H-03 | Optional degradation remains visible. | diagnostics/freshness expose it. |
| H-04 | Missing/stale closed P/L never fabricates realized P/L. | Preserve null/last-known/freshness semantics. |

### 3.2 New-order safety

| ID | Baseline | Validation |
|---|---|---|
| H-05 | Manual pause/auto controls remain effective. | Check before submit. |
| H-06 | Hard-stop/target/risk caps use authoritative account/equity state. | Preserve risk gate order/inputs. |
| H-07 | Structural SL/sizing remains mandatory. | No bypass submit path. |
| H-08 | Portfolio guard remains before entry. | Preserve canonical portfolio evaluation. |
| H-09 | Idempotency remains active. | Retry/timeout cannot blindly duplicate. |
| H-10 | Real execution requires private exchange authority. | Public context cannot submit alone. |
| H-11 | Funding/carry is not hard-news clearance. | Keep NEWS evidence separate. |
| H-16 | CHALLENGE-phase environment resolution must remain forced-DEMO through the canonical `propEnv()` proxy/invariant; refactors must not allow CHALLENGE execution to escape to LIVE/private-production routing through direct env access or bypass of the proxy. | Trace CHALLENGE callers through `propEnv()` (or canonical successor) and prove returned execution environment remains DEMO; any direct bypass that can promote CHALLENGE to LIVE is BLOCK. |

### 3.3 Open-position management

| ID | Baseline | Validation |
|---|---|---|
| H-12 | Positions remain manageable with optional closedPnl degraded. | Management depends on critical telemetry. |
| H-13 | `v771811:hyro:manage:{symbol}` lifecycle persists until reviewed migration. | State continuity inspection. |
| H-14 | TP/BE/trailing state cannot silently reset after Worker restart. | Durable lifecycle state preserved. |
| H-15 | New-entry cleanup cannot indiscriminately cancel protection orders. | Prove reduce-only/protection safety. |

---

## 4. Execution ambiguity / reconciliation

Required scenarios: accepted order + HTTP timeout => ambiguous/reconcile, never blind duplicate; rejected order => no false POSITION_OPEN; partial fill => reconcile quantity before management; exchange position with missing local intent => discover and block duplicate; local open with no exchange position => safe reconciliation without fabricated P/L; restart after submit => recover through order/position query + idempotency; critical telemetry down => fail closed; optional closedPnl down => manage positions while realized stats show degraded/unavailable.

---

## 5. Telegram/HUB baseline

Preserve single-delivery/callback ownership, notification dedupe (`v7718:hyro:notify:*`), health alert state (`v771845:health:alert_state`), critical-vs-optional Hyro status semantics, and do not restore misleading legacy callbacks before canonical router ownership is proven.

---

## 6. Provider/data-integrity baseline

Requested/provider symbol mapping must remain explicit; spot/cash/futures cannot be silently substituted; freshness requires timestamp/age evidence; provider disagreement cannot be averaged into fabricated authority; analysis quote cannot become execution-authoritative merely by refactor; provider failure cannot create fake zero quote/spread/P&L.

---

## 7. KV/state continuity baseline

Canonical registry: `V78_KV_KEY_REGISTRY.md`. Protected examples include `v775:books`, `v77173:hyro:control`, `v7718:hyro:day:*`, `v7718:hyro:intent:*`, `v771811:hyro:manage:*`, `v7718:hyro:notify:snapshot`.

Future account-scoped migration discipline: additive key -> dual-read/fallback if required -> explicitly reviewed shadow/dual-write -> parity -> one-account cutover -> soak -> separate legacy retirement. V78-006 authorizes no migration.

---

## 8. Binance20 quarantine baseline

Per DECISION-005/V78-005, Binance20/USDM code remains NON_PRODUCTION / QUARANTINED. Annotation must not add imports/routes/scheduled handlers, production credential requirements or execution authority. Future AccountAdapter promotion requires a separate issue.

---

## 9. Static/syntax validation baseline

Every changed JavaScript file in a mechanical V78 issue must pass:

```bash
node --check <file>
```

Also verify import/export resolution, endpoint verb/path/body parity for zero-behavior extraction, KV key/TTL parity unless explicitly changed, no new route/scheduled wiring, no secrets and no accidental order authority promotion. Syntax PASS alone is insufficient for execution/risk changes.

### 9.1 CI canonical-lock co-maintenance

`.github/workflows/validate-cloudflare-v77.yml` is part of the deterministic release guard and must be co-maintained whenever a canonical version/entrypoint lock changes.

Invariant:
- a canonical source/version migration is incomplete if production source is updated but the CI canonical-lock assertion still pins an obsolete canonical value;
- conversely, CI must not be advanced ahead of the reviewed canonical source cutover;
- any issue that intentionally changes the canonical lock must include both source and `validate-cloudflare-v77.yml` in its declared scope/validation evidence, or explicitly prove why the workflow no longer owns that invariant;
- stale CI lock or source/CI disagreement is BLOCK for declaring the migration complete.

---

## 10. Issue acceptance matrix

Applicable production-risk categories require evidence: syntax/module, execution authority, protected state, hard risk/SL/sizing, data freshness/authority, idempotency, reconciliation, Telegram/HUB routing, secrets and deployment/runtime evidence. If an applicable category is UNKNOWN, verdict cannot be unconditional PASS.

---

## 11. Resolution

Claude review WARN additions incorporated:
- G-09 AI-tuning `sanitize()`-only authoritative write path invariant;
- H-16 CHALLENGE-phase forced-DEMO `propEnv()` proxy invariant;
- Section 9.1 CI canonical-lock co-maintenance for `.github/workflows/validate-cloudflare-v77.yml`.

V78-006 is RESOLVED after these documentation-only corrections. No production source/state/risk/provider/order behavior changed.
