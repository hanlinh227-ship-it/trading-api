# V78-006 — DETERMINISTIC BASELINE VALIDATION MATRIX

Status: IMPLEMENTED — DOCUMENTATION ONLY / ZERO_BEHAVIOR
Owner: CHATGPT
Reviewer: CLAUDE

## Purpose
Define the minimum deterministic/static baseline that every later V78 mechanical refactor must preserve before behavior-changing cutovers are considered.

V78-006 does not execute trades, change risk, alter providers, mutate KV, change Telegram routing or modify production JavaScript. It establishes explicit invariants and acceptance checks so later source work can prove parity instead of relying on visual inspection or AI opinion.

---

## 1. Global safety invariants

| ID | Baseline invariant | Deterministic evidence required before/after refactor | Failure class |
|---|---|---|---|
| G-01 | `TRADING_STATE` is never reset as part of a release/refactor. | Diff/source inspection shows no namespace reset/delete/recreate logic. | BLOCK |
| G-02 | `v775:books` is never deleted/reset/reinitialized destructively. | Search changed files for key writes/deletes; compare lifecycle semantics. | BLOCK |
| G-03 | No secret/API key/private key/token is committed. | Diff scan + source search for credential literals/new secret material. | BLOCK |
| G-04 | UNKNOWN/MISSING financial state is not silently converted into fabricated PASS/0/LIVE when meaning changes. | Fixture/static path inspection of missing-data branches. | BLOCK |
| G-05 | HTTP success does not imply order fill unless exchange order state proves it. | Execution-path inspection; verify acknowledgement/fill/reconciliation semantics. | BLOCK |
| G-06 | Timeout does not imply failed order. | Timeout/retry path must preserve ambiguous state and reconcile before re-submit. | BLOCK |
| G-07 | One-writer WRITE_LOCK protocol is respected for each implementation issue. | Lock/commit/handoff history. | BLOCK |
| G-08 | Legacy Futures Signal and Hyro TK2 are not restored. | Import/route/source diff inspection. | BLOCK |

---

## 2. Signal advisory baseline

Current execution-authority source of truth: `V78_EXECUTION_AUTHORITY_MAP.md`.

| ID | Expected current behavior | Validation |
|---|---|---|
| S-01 | Signal outputs such as `MARKET_PLAN` and `LIMIT_PLAN` are advisory labels, not exchange orders. | `engine-v77168.js` must not gain private order-create wiring during zero-behavior refactors. |
| S-02 | Current Signal crypto path may use public Bybit/OKX market data but has no production order authority. | Search changed Signal files/import chain for private execution client/order endpoints. |
| S-03 | `DATA_BLOCK` remains distinguishable from strategy-level `NO_TRADE`. | Decision/action schema and decision branches preserve separate reason/action semantics. |
| S-04 | Freshness remains explicit; stale/missing analysis data cannot be relabeled LIVE. | Provider timestamp/age/freshness branches preserved. |
| S-05 | Structural SL and hard-news/freshness safeguards are not weakened to create more plans. | Compare thresholds/gate call sites in behavior-preserving changes. |
| S-06 | Signal notification dedupe remains intact while legacy notification code exists. | Preserve `v771816:signal:auto_notify:{sig}` semantics/1800s window until separately migrated. |

Minimum regression evidence for a Signal mechanical refactor:
- no new private-order endpoint/import;
- existing plan/action labels preserved;
- existing hard gate calls remain reachable;
- existing protected state keys remain unchanged;
- any future DecisionEvidence shadow output must not alter the original decision result.

---

## 3. Hyro execution baseline

Current real-capital execution authority: Hyro private Bybit stack.

### 3.1 Critical telemetry

| ID | Expected baseline | Validation |
|---|---|---|
| H-01 | wallet, positions and orders are critical telemetry for execution connectivity. | Failure of any critical probe must keep new execution fail-closed. |
| H-02 | `closedPnl` is optional/degradable telemetry. | `closedPnl`-only failure must not force account `connected:false`. |
| H-03 | Degraded optional telemetry remains visible. | diagnostics/reason/freshness show degradation instead of pretending healthy data. |
| H-04 | Missing/stale closed-PnL data does not fabricate realized P/L. | null/last-known/freshness semantics preserved. |

### 3.2 New-order safety

| ID | Expected baseline | Validation |
|---|---|---|
| H-05 | Manual pause / auto-execution controls remain effective. | New-order path checks current control state before submission. |
| H-06 | Daily hard-stop/target/risk caps remain based on current authoritative account/equity state. | Risk-gate call order and inputs preserved. |
| H-07 | Structural SL/sizing remains mandatory. | No code path submits a new order with required structural protection bypassed. |
| H-08 | Portfolio guard remains in new-entry path. | `evaluateHyroPortfolio` or canonical successor remains before order submission. |
| H-09 | Idempotency remains active. | Intent/order identity protection persists; timeout/retry cannot blindly duplicate. |
| H-10 | Real execution requires private exchange authority. | Public scanner/context data alone cannot submit an order. |
| H-11 | Funding/carry is not represented as hard-news clearance. | Funding state remains separate from NEWS evidence. |

### 3.3 Open-position management

| ID | Expected baseline | Validation |
|---|---|---|
| H-12 | Open positions remain manageable when only optional `closedPnl` is degraded. | Position-manager path uses critical telemetry, not optional closure history as connectivity gate. |
| H-13 | Position-management durable state is preserved. | `v771811:hyro:manage:{symbol}` lifecycle remains intact until additive migration issue. |
| H-14 | Partial TP / BE / trailing state cannot silently reset after Worker restart. | KV-backed lifecycle state preserved through refactors. |
| H-15 | Protection orders are not indiscriminately cancelled by new-entry cleanup. | Future cancel-scoping changes must prove reduce-only/protection order safety. |

---

## 4. Execution ambiguity / reconciliation cases

Every later execution-client or runtime refactor must reason through at least these deterministic scenarios:

| Scenario | Required safe outcome |
|---|---|
| Exchange accepts order, HTTP response times out | State becomes ambiguous/reconciling; no blind duplicate submit. |
| Order rejected | No false POSITION_OPEN; rejection reason exposed. |
| Partial fill | Local quantity/state reconciles to exchange truth before management sizing. |
| Position exists at exchange but local intent/state missing | Reconciliation discovers position; new duplicate entry stays blocked until reconciled. |
| Local state says open but exchange position is gone | Reconciliation transitions/cleans safely without fabricating closure P/L. |
| Worker restarts after submit before persistence finishes | Order/position query + idempotency must recover authoritative state. |
| Critical telemetry down | New entries fail closed. |
| Optional closed-PnL endpoint down | Existing positions remain manageable; realized stats show degraded/unavailable. |

---

## 5. Telegram/HUB baseline

| ID | Expected current invariant | Validation |
|---|---|---|
| T-01 | Telegram transport/router refactors do not create duplicate sends/callback execution. | Compare callback ownership and dedupe behavior at each migrated call site. |
| T-02 | Automatic entry/closure notifications keep dedupe state until NotificationBus cutover proves parity. | Preserve `v7718:hyro:notify:*` keys/snapshot semantics. |
| T-03 | Health alert cooldown/signature semantics remain intact until separately generalized. | Preserve `v771845:health:alert_state` behavior. |
| T-04 | HUB status cannot label critical Hyro telemetry failure as healthy/connected. | UI derives status from canonical telemetry diagnostics. |
| T-05 | Optional Hyro degradation is visible as degraded rather than full OFF when critical telemetry is healthy. | HUB/system status parity with telemetry semantics. |
| T-06 | Menu/router cleanup cannot restore legacy misleading callbacks. | New canonical router must own callbacks before legacy fallback removal. |

---

## 6. Provider/data-integrity baseline

| ID | Expected invariant | Validation |
|---|---|---|
| D-01 | Requested symbol and provider symbol mapping remain explicit. | Mapping tests/static fixtures per provider. |
| D-02 | Spot/cash/futures are not silently substituted across instrument classes. | Provider/instrument metadata preserved. |
| D-03 | Freshness classification remains evidence-based. | Timestamp/age source preserved; no default LIVE. |
| D-04 | Provider disagreement is not averaged into a fabricated authoritative quote. | Preserve separate source evidence/explicit disagreement. |
| D-05 | Analysis-only quote is not promoted to execution-authoritative quote. | DecisionEvidence/execution path keeps authority flag separate. |
| D-06 | Provider failure cannot create a fake zero quote/spread/P&L. | Missing/error branches return UNKNOWN/MISSING/BLOCK/DEGRADED as appropriate. |

---

## 7. KV/state continuity baseline

Canonical registry: `V78_KV_KEY_REGISTRY.md`.

Before any state-related source refactor, compare touched keys against the registry.

### Protected/high-safety examples
- `v775:books`
- `v77173:hyro:control`
- `v7718:hyro:day:*`
- `v7718:hyro:intent:*`
- `v771811:hyro:manage:*`
- `v7718:hyro:notify:snapshot`

Required migration discipline for future account scoping:
1. additive new key;
2. dual-read/fallback where required;
3. shadow/dual-write only when explicitly reviewed;
4. parity verification;
5. cut over one account at a time;
6. soak window;
7. legacy retirement in a separate issue.

No V78-006 step authorizes a migration.

---

## 8. Binance20 quarantine baseline

Per DECISION-005 and V78-005:
- four Binance20/USDM modules contain execution capability but remain NON_PRODUCTION / QUARANTINED;
- zero-behavior annotations must not add imports/routes/scheduled handlers;
- no Binance credentials become production requirements;
- no current production execution authority is granted;
- V78-004 source annotation must remain behavior-neutral.

A future AccountAdapter promotion requires a separate issue and fresh authority/risk review.

---

## 9. Static/syntax validation baseline for JavaScript changes

For each changed `.js` file in a mechanical V78 issue:

```bash
node --check <file>
```

For a multi-file issue, run it on **every changed JavaScript file**.

Additional source checks should be chosen by blast radius, including:
- import/export names still resolve;
- endpoint path + HTTP verb + body/query semantics are unchanged for zero-behavior client extraction;
- KV key literals/TTLs unchanged unless the issue explicitly changes them;
- no new route/scheduled wiring;
- no secret literal;
- no accidental private-order authority added to advisory paths.

A syntax PASS alone is not sufficient to mark an execution/risk change safe.

---

## 10. Issue acceptance matrix

A later issue may be marked behavior-parity PASS only when all applicable columns have evidence:

| Area | Required evidence |
|---|---|
| Syntax/module | all changed JS passes syntax/static import review |
| Execution authority | no accidental authority promotion |
| State | protected keys/lifecycle preserved or explicitly migrated |
| Risk | hard risk, SL, sizing and fail-closed semantics preserved |
| Data | freshness/missing/provider authority semantics preserved |
| Idempotency | duplicate/retry/restart behavior preserved |
| Reconciliation | exchange truth remains authoritative |
| Telegram/HUB | no duplicate/misrouted callback or misleading status |
| Secrets | no credentials committed/exposed |
| Deployment | do not call production healthy without deployment/runtime evidence |

If an applicable category is UNKNOWN, verdict cannot be unconditional PASS for a production-risk change.

---

## 11. V78-006 acceptance criteria

- [x] Baseline explicitly protects `TRADING_STATE` and `v775:books`.
- [x] Signal advisory authority is separated from order authority.
- [x] Hyro critical vs optional telemetry behavior is covered.
- [x] New-order, open-position, timeout/retry/reconciliation edge cases are covered.
- [x] Telegram/HUB dedupe and status invariants are covered.
- [x] Provider freshness/missing/authority invariants are covered.
- [x] KV/account-migration continuity discipline is documented.
- [x] Binance20 quarantine baseline is documented.
- [x] `node --check` requirement is explicit for every later changed JS file.
- [x] No production source/state/risk/provider/order behavior changed by V78-006.

## Reviewer request
Claude should review this matrix against current V78-001..V78-005 evidence and current production entrypoint/execution paths. Return PASS/WARN/BLOCK for baseline completeness. If WARN, provide deterministic missing scenarios/checks rather than general suggestions. No Wave 1 source implementation is authorized by this document.
