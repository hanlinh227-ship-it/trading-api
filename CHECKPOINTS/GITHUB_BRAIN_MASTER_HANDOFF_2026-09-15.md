# GITHUB BRAIN — MASTER HANDOFF (2026-09-15)

> Cross-session handoff for the GitHub Brain / Model Mesh work stream.
> Written to be sufficient on its own: a new ChatGPT / Claude / Codex session
> can take over from this file plus the repository, without any prior
> conversation history.

---

## START HERE — SUCCESSOR

1. **Repository:** `hanlinh227-ship-it/trading-api`, canonical branch `main`.
2. **Production-verified baseline:** `99359b1720a28614749d53615fe2b740044de40e` — the revision at which the full production contract was verified (run 34987419682).
3. **`main` and production advance together** on every merge through the gated deploy. Documentation-only merges after the baseline advance `main` without changing runtime behaviour, so `main` may legitimately be ahead of the SHA above. **Always re-verify current parity per §12.7 — trust the repository, not this number.**
4. **Release:** `4.9.1`, `KNOWN_GOOD = YES` (`AI_SKILL_LIBRARY/v4/releases/history.yaml`).
5. **Worker:** `trading-v77-scanner` on Cloudflare Workers.
6. **Model Mesh state:** PRODUCTION VERIFIED. FREE_ONLY, 5 eligible providers, **3 ACTIVE**. STANDARD→2 workers, DEEP→3.
7. **Model Mesh Production Stabilization is COMPLETE.** Do not re-open or redesign it without regression evidence.
8. **Two unresolved, non-blocking items** (§6): `gemini_developer_api` 404, and the `*/10` health-refresh schedule that has never fired.
9. **Architecture you must not break** (§13): GitHub Brain is the single authority; external models are workers only; no majority vote; family dedupe; FAST external = 0; SECRET external = 0; FREE_ONLY core, no paid fallback; provider failure must never become Brain failure; TinyFish optional.
10. **Next phase:** ADAPTIVE GENERALIST BRAIN vNext (§10) — **DO NOT IMPLEMENT** in your first session. A separate planning file will be supplied by the user, plus `GITHUB_BRAIN_PLUGIN_OMNIROUTE_INTEGRATION_PLAN.md` for plugin audit (§11).
11. **Read in this order:** `AGENTS.md` → `AI_SKILL_LIBRARY/checkpoint.json` → `AI_SKILL_LIBRARY/AI_GLOBAL_CHECKPOINT.md` → this file → `CHECKPOINTS/MODEL_MESH_PRODUCTION_VERIFICATION.md` → the user's planning file.
12. **Your first action:** sync `main`, re-verify §2 of this report still matches the repo, then perform Gap Analysis for Generalist Brain vNext and produce a design/spec for user approval. **No implementation before approval** (§12).

---

## 1. This file and canonical pointers

| Item | Path |
|---|---|
| This master handoff | `CHECKPOINTS/GITHUB_BRAIN_MASTER_HANDOFF_2026-09-15.md` |
| Production verification evidence | `CHECKPOINTS/MODEL_MESH_PRODUCTION_VERIFICATION.md` |
| Canonical Brain checkpoint (cross-chat) | `AI_SKILL_LIBRARY/AI_GLOBAL_CHECKPOINT.md` → points here |
| Checkpoint discovery root | `AI_SKILL_LIBRARY/checkpoint.json` (`master_handoff_path`) |

**Not modified, and not to be confused with this file:**
`docs/checkpoints/CURRENT_HANDOFF.md` is the **trading execution authority**
(BTCUSDT Bybit), referenced by `router.yaml`, `v4/skills/trading/manifest.yaml`
and `v4/mesh/domains/trading.yaml`. It has nothing to do with Brain handoff and
was deliberately left untouched. No prior checkpoint or history was removed.

---

## 2. Current production truth

Verification vocabulary used throughout this document:

| Label | Meaning |
|---|---|
| **SOURCE VERIFIED** | Read directly from repository source at the stated SHA |
| **CI VERIFIED** | Asserted by a CI job that passed |
| **PRODUCTION VERIFIED** | Asserted against the running Worker by the exact-SHA gated deploy |
| **NOT VERIFIED** | Not established by any of the above |

### Identity

| Field | Value | Status |
|---|---|---|
| Repository | `hanlinh227-ship-it/trading-api` | SOURCE VERIFIED |
| Canonical branch | `main` | SOURCE VERIFIED |
| Production-verified baseline SHA | `99359b1720a28614749d53615fe2b740044de40e` | PRODUCTION VERIFIED |
| `main` when this document was written | `99359b1720a28614749d53615fe2b740044de40e` | SOURCE VERIFIED |
| `main` after this document was merged | advances by the handoff merge commit — documentation only, no runtime change | SOURCE VERIFIED |
| Release / version | `4.9.1` | SOURCE VERIFIED |
| `KNOWN_GOOD` | **YES** | PRODUCTION VERIFIED |
| Cloudflare Worker | `trading-v77-scanner` | SOURCE VERIFIED |
| Worker base URL | `https://trading-v77-scanner.hanlinh227.workers.dev` | CI VERIFIED |
| Brain endpoints | `/brain/health`, `/brain/route` | PRODUCTION VERIFIED |
| Mesh endpoints | `/brain/mesh/health`, `/brain/mesh/plan`, `/brain/mesh/probe`, `/brain/mesh/execute` | PRODUCTION VERIFIED |
| Evidence endpoints | `/brain/evidence/health`, `/brain/evidence/probe`, `/brain/evidence/query` | PRODUCTION VERIFIED |
| Deployment authority | `deploy-skill-mandatory-fast-gateway.yml` (**sole**) | SOURCE VERIFIED + CI VERIFIED |

### Verifying workflow run

Run **34987419682**, event `push`, head `99359b1720a28614749d53615fe2b740044de40e`, conclusion **success**.

```
FINAL_EXACT_SHA_GATE=PASS revision=99359b1720a28614749d53615fe2b740044de40e
PRODUCTION_LIVE_REVISION=99359b1720a28614749d53615fe2b740044de40e
ATTEMPTED_REVISION=99359b1720a28614749d53615fe2b740044de40e
SKILL_MANDATORY_FAST_GATEWAY_DEPLOY=PASS
ROLLBACK_TARGET=7db95e6d8c5c767125d180120afef56ce0a57fbe
MODEL_MESH_MODE=FREE_ONLY
MODEL_MESH_MAX_PARALLEL=STANDARD=2 DEEP=4 FAST=0
PROVIDER_SECRET_SYNC=ELIGIBLE_PROVIDERS_ONLY
```

The same contract passed on the immediately preceding run
(**34986670782**, `7db95e6d8c5c767125d180120afef56ce0a57fbe`) with identical
boundary results, so the outcome is repeatable, not a single run.

### Merged pull requests

| PR | Title | Merge commit (full SHA) |
|---|---|---|
| #339 | Stabilize live Model Mesh health and TinyFish evidence (Codex) | `9314783d3f1b981351e59b540ae62a3db8f66909` |
| #340 | fix(mesh): remediate provider canary failures (Codex) | `6e5bbb9e13ef95489949a51897ef1118ed0dd916` |
| #341 | unblock deploy gate, harden provider health, compile canonical policy | `aa30bccf730597903a9ff3e1e59ad3ad47ce4d93` |
| #342 | secret-sync path + single deployment authority | `a4a9e96efa845e10f2eed0721f04b0728baae078` |
| #343 | prove FAST/SECRET boundaries on the running Worker | `7db95e6d8c5c767125d180120afef56ce0a57fbe` |
| #344 | mark Brain 4.9.1 production verified known-good | `99359b1720a28614749d53615fe2b740044de40e` |

Codex branch heads: `codex/model-mesh-live-health-tinyfish` = `9c9e966102d805bba48ac4a651cb23d6028905fc`; `codex/model-mesh-live-remediation` = `e308a4150e5d227d410190508e6cd327c65cc19e`. Both fully contained in `main`.

### Deploy workflow run history (recent)

| Run | Head SHA | Conclusion |
|---|---|---|
| 34987419682 | `99359b1720a28614749d53615fe2b740044de40e` | success |
| 34986670782 | `7db95e6d8c5c767125d180120afef56ce0a57fbe` | success |
| 34985395770 | `a4a9e96efa845e10f2eed0721f04b0728baae078` | success |
| 34984533697 | `aa30bccf730597903a9ff3e1e59ad3ad47ce4d93` | failure (secret-sync path bug, fixed in #342) |
| 34980048523 | `6e5bbb9e13ef95489949a51897ef1118ed0dd916` | failure (the original blocker; see §3) |

### CI / test status

| Check | Status |
|---|---|
| `npm run check` (full Worker suite) | CI VERIFIED — green |
| `ci_validate.py --source-sha <HEAD>` | CI VERIFIED — `CI_VALIDATE=PASS failures=0` |
| `release.py verify` | SOURCE VERIFIED — 0 errors, 0 warnings |
| `release.py check` | SOURCE VERIFIED — `RELEASE_CHECK=PASS version=4.9.1` |
| PR checks on every merged PR | CI VERIFIED — green before merge |

---

## 3. Codex → Claude handoff history

Engineering facts only.

### What Codex completed

Codex executed `docs/superpowers/plans/2026-09-15-model-mesh-live-health-tinyfish-stabilization.md`, **Tasks 1–7**:

1. Canonical FREE_ONLY contract + sanitized failure taxonomy
2. Live-health state machine + isolated KV store (`brain:model-mesh:health:v1:`)
3. Provider probes + execution feedback
4. Runtime-aware health + planner
5. TinyFish evidence service on a separate `/brain/evidence/*` lane
6. Deployment hardening
7. Provider-by-provider remediation (PR #340)

Codex ran out of usage during **Task 8** (release, PR, exact-SHA production proof).

### The production failure Codex left behind

Run **34980048523** on `6e5bbb9e13ef95489949a51897ef1118ed0dd916`:

```
step 13  Deploy exact-main Worker                 → success
step 17  Production Model Mesh provider canary    → success
step 18  Production TinyFish free evidence canary → FAILURE (exit 3)
step 19  Final exact-SHA deployment gate          → SKIPPED
step 20  Deployment record                        → SKIPPED
```

New code was live with the exact-SHA gate never rendered.

### Independent review

An independent architecture/security review produced 2 critical blockers,
6 high and 7 medium findings. Its account of run 34980048523 was confirmed
step-by-step from the GitHub job record.

### Root causes found and fixed

| ID | Root cause |
|---|---|
| **C2** | Exit 3 was the *secret-leak* branch of `if(JSON.stringify(x).match(/API_KEY\|TOKEN\|secret/i))`. The fetch canary targets `docs.tinyfish.ai/fetch-api` — an API documentation page — and `tinyfish-client.js` returns 4000-char snippets verbatim. Documentation necessarily contains all three words, so the gate flagged its own fixture. Deterministic blocker, not a leak. |
| **C1** | Deploy ran before verification with no rollback, so any canary failure left the revision live and the final gate skipped. |
| **Dup authority** | Two workflows ran `wrangler deploy` against the same Worker on the same trigger. Found during remediation, not in the original review: on `aa30bccf` the gated workflow failed while `deploy-cloudflare-worker.yml` deployed the same revision unconditionally, making the exact-SHA contract bypassable. |
| **H1** | `consecutiveFailures` was persisted but never read — one transient 401/403/404 cost a 6-hour quarantine. |
| **H3** | Probing a provider already inside its own cooldown re-spent free quota. |
| **H4** | `retryAfter`/`resetAt` were captured then discarded; cooldown was a fixed 5 minutes, contradicting `policy.yaml quota.respect_provider_reset: true`. `quota-state.js` held the correct logic and was imported by nothing. |
| **H5** | Successful TinyFish evidence was discarded when circuit-breaker bookkeeping failed afterwards. |
| **H6** | No in-worker recovery for stale health evidence; the only refresher was an external schedule. |
| **M1** | `max_parallel` existed in four places; `contracts.js` was the de facto authority and `policy.yaml` changed nothing at runtime. |
| **M2** | Three of eight declared selection filters implemented; `domain_capabilities.yaml` authored and entirely unread. |
| **M4** | Deploy gated on a KV read-back that Workers KV does not guarantee. |
| **M6** | Credentials for three providers with no eligible model were synced into production. |
| **M7** | `endpoint_family` owned by two registries that could drift. |
| **CI false-green** | Two workflows ran the Worker suite against stale **committed** generated artifacts. |

### Claude's remediation

PRs #341–#344 (see §2). Final production verification on runs 34986670782 and
34987419682. Release 4.9.1 marked `known_good: true` via the canonical
`release.py build --version 4.9.1 --validated --known-good`.

---

## 4. Final Model Mesh architecture

```
request
  → GitHub Brain            (skill-gateway: routing + reasoning authority)
  → profile                 (FAST | STANDARD | DEEP)
  → policy                  (compiled canonical contract)
  → Model Mesh              (worker plane, zero authority)
  → live health             (KV evidence, TTL-bounded)
  → FREE_ONLY eligibility   (8-filter selection chain)
  → worker selection        (capability-ranked, family-deduplicated)
  → execution               (parallel, bounded by max_parallel)
  → verification/synthesis  (Brain; maker/critic, never a vote)
```

### Authority boundaries

| Layer | Authority | Enforcement |
|---|---|---|
| GitHub Brain (`skill-gateway.js`) | **SINGLE AUTHORITY** for routing and reasoning | zero `fetch(`, zero KV reads — SOURCE VERIFIED |
| Model Mesh | worker plane only | every envelope carries `routingAuthority:false, reasoningAuthority:false` (`model-mesh-runtime.js`) |
| External providers | workers only | never consulted for routing |
| TinyFish / evidence | optional evidence source | separate `/brain/evidence/*` lane, not mesh membership |

### Non-negotiable runtime contracts

| Contract | Mechanism | Status |
|---|---|---|
| FAST external = 0 | `max_parallel.FAST = 0`, compile-enforced in `compile_model_mesh_policy.py`; runtime short-circuit in `model-mesh-runtime.js` | PRODUCTION VERIFIED — `FAST_EXTERNAL_BOUNDARY=PASS external_workers=0 externalRoutingCalls=0` |
| SECRET external = 0 | 403 in handler and executor; `sanitizeDataClass` fails **closed** to SECRET | PRODUCTION VERIFIED — `SECRET_EXTERNAL_BOUNDARY=PASS http=403`, `DATACLASS_FAIL_CLOSED=PASS` |
| No majority vote | `conflict.js` → `majorityVote:false`; `policy.yaml provider_voting: forbidden`, compile-enforced | SOURCE VERIFIED |
| Family dedupe | `selector.js` dedupes by `model_family`; `same_family_counts_as_independent_reasoning:false`, compile-enforced | SOURCE VERIFIED + covered by test |
| Provider failure ≠ Brain failure | graceful-zero plan, `ok:true` with `workers:[]` | PRODUCTION VERIFIED — observed live (see below) |
| No paid fallback | `paid_fallback: disabled`, compile-enforced | SOURCE VERIFIED |

**Graceful zero was observed in production, not simulated.** A new `source_sha`
invalidates prior health evidence, so pre-probe the planner genuinely had no
live provider and returned:

```
MODEL_MESH_PLAN=PASS STANDARD workers=0 reason=no_live_healthy_provider
MODEL_MESH_PLAN=PASS DEEP     workers=0 reason=no_live_healthy_provider
```

### Policy authority chain (single source of truth)

```
AI_SKILL_LIBRARY/v4/model_mesh/policy.yaml
AI_SKILL_LIBRARY/v4/model_mesh/domain_capabilities.yaml
      ↓  AI_SKILL_LIBRARY/v4/tools/compile_model_mesh_policy.py
AI_SKILL_LIBRARY/v4/runtime/generated/model-mesh-policy.json
      ↓  cloudflare-worker/prepare-model-mesh.mjs
cloudflare-worker/generated/model-mesh-policy.js
      ↓
model-mesh/contracts.js · model-mesh/selector.js · model-mesh-handler.js
      ↓
CI assertions + the deployment record
```

`max_parallel` and the selection filters are never hard-coded at any step.
Generated artifacts are **build outputs and are not committed** — a committed
copy went stale silently (the tracked snapshot once held `models:[]` and an
old `source_sha`).

### Health state machine

`CONFIGURED` · `LIVE_HEALTHY` · `DEGRADED` · `COOLDOWN` · `QUARANTINED` · `NOT_ELIGIBLE`

- Evidence key prefix `brain:model-mesh:health:v1:`, keyed by model fingerprint.
- `LIVE_HEALTHY` TTL 30 min; `DEGRADED` 5 min; `QUARANTINED` 6 h; `COOLDOWN` follows the provider's own `Retry-After`/reset, clamped 30 s – 1 h.
- Quarantine requires a **threshold** of consecutive failures (`AUTH_FAILED` 2, `MODEL_NOT_FOUND` 3, `FREE_ENTITLEMENT_INVALID` 2), not a single failure.
- A new `source_sha` invalidates evidence (`SOURCE_REVISION_MISMATCH`).
- A resolved `kv.put` is the durability signal; KV read-back is a non-authoritative freshness hint only.

### Selection chain (all 8 declared filters implemented)

`free_entitlement` → `usage_terms` → `capability` → `permission_ceiling` → `privacy` → `health` → `quota` → `context_fit`

`selectionRejection()` returns the name of the first filter that rejects a
model, so an empty worker set is explainable rather than silent.

---

## 5. Provider matrix (production, measured)

From run 34987419682. **These numbers are measured truth, not targets.**

```
MODEL_MESH_PROBE=PASS probed=5 configured=5 successful=3 unavailable=2
MODEL_MESH_LIVE_OVERLAY=PASS active=3
MODEL_MESH_POST_PROBE_PLAN=PASS STANDARD workers=2
MODEL_MESH_POST_PROBE_PLAN=PASS DEEP     workers=3
```

| Provider | Model | Family | FREE_ONLY eligible | Configured | Health | Quota / cooldown | Probe result | Failure category | Notes |
|---|---|---|---|---|---|---|---|---|---|
| `groq` | `openai/gpt-oss-120b` | `gpt-oss-120b` | YES (`account_specific`) | YES | **LIVE_HEALTHY** | AVAILABLE | 200, 143 ms | — | Fastest healthy provider |
| `openrouter` | `openrouter/free` | `openrouter-free-router` | YES (`recurring`) | YES | **LIVE_HEALTHY** | AVAILABLE | 200, 1 439 ms | — | Dynamic free pool |
| `cloudflare_workers_ai` | `@cf/zai-org/glm-4.7-flash` | `glm-4.7-flash` | YES (`recurring`) | YES | **LIVE_HEALTHY** | AVAILABLE | 200, 785 ms | — | Latency has ranged 785 ms – 14.5 s across runs |
| `gemini_developer_api` | `gemini-2.5-flash` | `gemini-2.5-flash` | YES (`recurring`) | YES | **QUARANTINED** | n/a | 404, 162 ms | `MODEL_NOT_FOUND` | **UNRESOLVED — §6.1.** Model id confirmed present in live listing |
| `mistral` | `mistral-small-latest` | `mistral-small` | YES (`account_specific`) | YES | **COOLDOWN** | rate-limited | 429, 227 ms | `RATE_LIMITED` | **UNRESOLVED — §6.3.** Free tier vs probe cadence |
| `opencode_zen` | `mimo-v2.5-free` | — | **NO** — `usage_terms: evaluation` | YES (secret synced) | NOT_ELIGIBLE | n/a | **not probed** | `SELECTION_POLICY` | Excluded by design: evaluation is not production capacity |
| `cohere` | `command-a-plus-05-2026` | `command-a-plus` | **NO** — `trial_credit` | no secret synced | NOT_ELIGIBLE | n/a | not probed | `FREE_ONLY_POLICY` | Correctly excluded |
| `huggingface_inference_providers` | `openai/gpt-oss-120b` | `gpt-oss-120b` | **NO** — `trial_credit` | no secret synced | NOT_ELIGIBLE | n/a | not probed | `FREE_ONLY_POLICY` | Would also be family-deduped against `groq` |
| `alibaba_model_studio` | `qwen3.8-flash` | `qwen3.8-flash` | **NO** — `trial_credit` | no secret synced | NOT_ELIGIBLE | n/a | not probed | `FREE_ONLY_POLICY` | Correctly excluded |
| `nvidia_nim` | — | — | n/a | **no eligible model** | n/a | n/a | not probed | — | Binding enabled but registry has no model; secret no longer synced |
| `cerebras` | — | — | n/a | **no eligible model** | n/a | n/a | not probed | — | Same |
| `sambanova` | — | — | n/a | **no eligible model** | n/a | n/a | not probed | — | Same |

**ACTIVE = 3 of 5 probed.** A provider is ACTIVE only when it is FREE_ONLY
eligible **and** configured **and** carries fresh `LIVE_HEALTHY` evidence.
DEEP returned 3 of an allowed 4 because only 3 providers are healthy — correct
partial-outage behaviour, not a defect.

---

## 6. Unresolved items

Nothing below is marked resolved, because none has production evidence of
resolution.

### 6.1 `gemini_developer_api` returns 404 — ROOT CAUSE OPEN

**Evidence held**
- Production probe, every run: `status:404, category:"MODEL_NOT_FOUND", state:"QUARANTINED"`, latency 122–184 ms.
- Advisory diagnosis, every run: `GEMINI_MODEL_AVAILABILITY=PASS configured=gemini-2.5-flash` — the configured id **is present** in the live `GET /v1beta/models` listing for the deployed key.
- Fast failure (~160 ms) indicates the endpoint resolved and rejected, not a network problem.

**Ruled out**
- ❌ Wrong model id in the registry — disproven by the listing check. **Editing `active.json` would mask the real cause, not fix it.**
- ❌ Missing/unconfigured credential — the same key successfully lists models.
- ❌ Network/DNS — the listing call over the same host succeeds.
- ❌ Our quarantine logic misfiring — threshold behaves correctly; the 404 is real and repeats.

**Remaining hypotheses**
1. Request path/shape mismatch: adapter builds `{baseUrl}/models/{model}:generateContent` against `v1beta`; the model may require a different API version or a `models/` prefix handling difference.
2. Method/entitlement split: the key may be entitled to `models.list` but not `generateContent` for this model.
3. Region or project-level restriction returning 404 rather than 403.

**Files**
- `cloudflare-worker/model-mesh/providers/gemini.js` (adapter; URL construction, `x-goog-api-key` header)
- `AI_SKILL_LIBRARY/v4/model_mesh/active.json` (registry entry)
- `AI_SKILL_LIBRARY/v4/model_mesh/runtime_bindings.json` (`endpoint_family: gemini`, base URL)

**Reproduce**
```
POST https://trading-v77-scanner.hanlinh227.workers.dev/brain/mesh/probe
     -H "x-model-mesh-token: $MODEL_MESH_EXECUTION_TOKEN"
```
Then read the `gemini_developer_api` row of `MODEL_MESH_PROBE_MATRIX`. Or reproduce directly against the provider with the deployed key.

**Why not blocking:** the mesh degrades correctly. The provider is quarantined,
excluded from selection, and STANDARD/DEEP planning still succeeds on the
remaining healthy providers. No mandatory production contract depends on it.

**Recommended next investigation:** capture the provider's 404 *response body*
(currently discarded — only the sanitized category is retained) in a one-off
diagnostic that does not log credentials. That body will name the cause
directly. Compare a working `curl` against `v1beta` and `v1` for the same key.

### 6.2 `*/10` health-refresh schedule has never fired

**Where it is:** `.github/workflows/deploy-skill-mandatory-fast-gateway.yml`,
`on.schedule: - cron: '*/10 * * * *'`, job `refresh-model-mesh-health`
(`if: github.event_name == 'schedule'`).

**Status:** `total_count = 0` for `?event=schedule` on that workflow. Zero
scheduled runs, ever, since the cron was added at ~13:50Z 2026-09-15.
Confirmed repeatedly over more than an hour.

**Why it may not fire (not yet established):**
- GitHub scheduled workflows are explicitly best-effort and can be delayed heavily or dropped under load.
- A newly added schedule can take time to activate.
- Schedules only run from the default branch — it *is* on `main`, so that is not the cause.
- GitHub disables schedules after 60 days of repository inactivity — not applicable here.

**How self-heal compensates:** `cloudflare-worker/model-mesh/self-heal.js`.
When the planner finds `no_live_healthy_provider`, a bounded opportunistic
re-probe is scheduled via `ctx.waitUntil()` — after the response, adding no
request latency — rate-limited by an advisory KV lock to at most one attempt
per 5 minutes. A failing recovery probe never surfaces as a request error.

**Blast radius if BOTH the schedule and self-heal were absent:** `LIVE_HEALTHY`
TTL is 30 minutes. Thirty minutes after any deploy every model reads
`STALE_EVIDENCE → DEGRADED`, the planner returns zero workers permanently, and
`/brain/mesh/execute` returns 503 until a human manually POSTs
`/brain/mesh/probe`. The Brain itself stays fully operational throughout — FAST
and routing never touch provider health.

> **Therefore: the in-worker self-heal is currently the ONLY working recovery
> path, not a redundancy. Do not remove it while `event=schedule` count is 0.**

**Recommended investigation:** check whether any scheduled run appears after
24 h. If not, either move the refresh to a Cloudflare cron trigger plus a
`scheduled` handler (note `test-deploy-safety.mjs` currently asserts
`wrangler.example.jsonc` has no `"crons"`, so that assertion would need a
deliberate, reviewed change), or accept self-heal as the primary mechanism and
document it as such.

**Why not blocking:** self-heal covers recovery, and no mandatory production
contract depends on the schedule.

### 6.3 `mistral` rate-limited at probe cadence

429 on essentially every probe, at ~227 ms. Cooldown now honours the provider's
own reset and the provider is not re-probed while inside it, but the free tier
may simply be too small for this cadence. Not blocking; the provider is excluded
while cooling and re-enters automatically.

### 6.4 Registry capability coverage incomplete

`domain_capabilities.yaml` is compiled in as **ranking** authority (it declares
`weights_are_selection_metadata_only: true`). Hard capability filtering is
deliberately **not** enabled: no admitted model declares `math_quant` or
`data_analysis`, which the `trading` domain weights most heavily, so strict
enforcement would zero out whole domains. A missing declaration ranks a model
last rather than disqualifying it. Enabling hard filtering requires completing
registry capability coverage first.

### 6.5 Workers KV has no compare-and-set

Health writes are read-modify-write. Records stay well-formed under concurrent
writes, but `consecutiveFailures` can under-count. Move health state to a
Durable Object if it ever becomes load-bearing beyond the quarantine threshold.
(`TINYFISH_CIRCUIT` already demonstrates the transactional pattern.)

### 6.6 `/brain/mesh/plan` and `/brain/mesh/health` are unauthenticated

Both fan out to KV (one read per eligible model). `plan` can now also trigger a
recovery probe, bounded to one per 5 minutes by the advisory lock. Consider
token-gating or rate-limiting if abuse appears. `probe` and `execute` are
token-gated already.

### 6.7 Observed KV propagation flake in the overlay gate

On run 34987419682 the live-overlay check failed its first attempt with
`overlay_active_set_mismatch` and passed on retry
(`MODEL_MESH_KV_PROPAGATION_RETRY attempt=1`). This is Workers KV eventual
consistency behaving as documented and is why the deploy keeps a bounded
propagation retry around that check. It also vindicates removing the KV
read-back from `evidencePersisted` — had that still been authoritative, the run
would have failed for no real reason.

---

## 7. TinyFish final state

`OPTIONAL` · `COST_GATED` · `NO_HARD_DEPENDENCY`

TinyFish is **not** part of the Model Mesh and holds **no** reasoning or routing
authority. It lives on a separate `/brain/evidence/*` lane.

```
TINYFISH_HEALTH=PASS optional=true configured=true admissionControl=true
EVIDENCE_CANARY=PASS operation=search status=200 evidence=7 guardPersisted=true
EVIDENCE_CANARY=PASS operation=fetch  status=200 evidence=1 guardPersisted=true
TINYFISH_CANARY=success (optional, non-gating)
```

Brain behaviour when TinyFish is:

| Condition | Behaviour |
|---|---|
| **off / not configured** | `/brain/evidence/*` returns explicit `503 evidence_provider_not_configured` with `optional:true, hardDependency:false`. **No external call attempted.** Brain, routing and Model Mesh unaffected. |
| **unavailable / erroring** | Sanitized failure category returned; circuit breaker opens after repeated transient failures. Brain unaffected. |
| **quota exhausted** | `429` with guard state and `retryAfterMs`. Brain unaffected. |
| **DO admission control missing** | Fails **closed** (429) — without admission control, cost and rate cannot be bounded. Brain unaffected. |
| **bookkeeping fails after a successful call** | Evidence is **returned**, with `guardStatePersisted:false` reporting the degradation. The external call is already spent, so discarding it buys no safety and costs a second quota-spending retry. |

Its deploy canary is `continue-on-error: true` and **cannot roll back a Brain
revision**. Admission control: single global Durable Object `TINYFISH_CIRCUIT`,
≥2 s between requests, opens for 5 min after 3 consecutive transient failures.

---

## 8. Security state

| Area | State |
|---|---|
| **Secret synchronization** | Least privilege. A provider credential is synced only when the compiled snapshot carries an eligible model for it. Last run: `MODEL_MESH_SECRETS_SYNCED_COUNT=8`, `MODEL_MESH_SECRETS_SKIPPED_NO_ELIGIBLE_MODEL=6`. |
| **Secrets in production** | `MODEL_MESH_EXECUTION_TOKEN`, `TINY_FISH_API`, `GROQ_API_KEY`, `GEMINI_API_KEY`, `CLOUDFLARE_AI_API_TOKEN`, `OPENROUTER_API_KEY`, `MISTRAL_API_KEY`, `OPENCODE_ZEN_API_KEY` |
| **No longer synced** | `NVIDIA_API_KEY`, `CEREBRAS_API_KEY`, `SAMBANOVA_API_KEY` (no eligible model), plus `COHERE_API_KEY`, `HF_TOKEN`, `DASHSCOPE_API_KEY` (trial-credit providers) |
| **Credential leak detection** | `cloudflare-worker/security/secret-scan.js` — matches credential **shape** (provider key prefixes with entropy, JWTs, PEM headers, real bearer values) and concrete **env values**. Never vocabulary. Documentation placeholders excluded. Findings name the env var, never the value. |
| **Applied at** | mesh probe canary (`validate-model-mesh-probe.mjs`), evidence canary (`validate-evidence-canary.mjs`), `model-mesh/canary-policy.js` |
| **Redaction** | Deploy output redacted by value for all in-scope secrets plus shape regex (`redact-deploy-output.mjs`); every secret the job holds is now exported to it (previously 2 of 19). |
| **Evidence sanitization** | `title`, `snippet`, `url` and `finalUrl` all passed through `redactCredentials`. URL validation additionally blocks non-HTTPS, credentials-in-URL, IP literals, `localhost`, `.local`, `.internal`, and cloud metadata hosts. |
| **Endpoint auth** | `/brain/mesh/probe`, `/brain/mesh/execute`, `/brain/evidence/probe`, `/brain/evidence/query` require `x-model-mesh-token`, compared in constant time via SHA-256 digests. `/brain/mesh/health`, `/brain/mesh/plan`, `/brain/evidence/health` are unauthenticated (see §6.6). |
| **Rate limiting** | Evidence lane: global DO, ≥2 s between requests. Self-heal: ≤1 probe per 5 min. Provider probe concurrency: max 4. |
| **Permission widening** | None. `sanitizeDataClass` fails **closed** — an unrecognised data class is treated as SECRET (`DATACLASS_FAIL_CLOSED=PASS`, PRODUCTION VERIFIED). |
| **Hard-coded credentials** | None. Asserted by `prepare-model-mesh.mjs` (rejects credential-shaped values in bindings) and `test-model-mesh-bindings.mjs`. |
| **Generated config** | Provider secrets are never written into `wrangler.jsonc`; asserted in CI. Financial runtime switches (`BYBIT_AUTO_LIVE`, `BYBIT_BTC_LIVE_ACK`, `BYBIT_AUTO_DEMO`, `BYBIT_AUTO_ENABLED`) are never generated; asserted in CI. |
| **Historical exposure** | None found. No credential value appears in source or in the reviewed CI logs. No secret value is recorded anywhere in this handoff or in `CHECKPOINTS/MODEL_MESH_PRODUCTION_VERIFICATION.md`. |

---

## 9. Test matrix

Run everything:
```bash
cd cloudflare-worker
npm run prepare:all      # compiles canonical contracts at current HEAD
npm run check            # full Worker suite
```
Mesh subset: `npm run test:model-mesh`
Canonical Python + repo suite:
```bash
python3 AI_SKILL_LIBRARY/v4/tools/ci_validate.py --source-sha "$(git rev-parse HEAD)"
```
Release state: `python3 AI_SKILL_LIBRARY/v4/tools/release.py verify && … release.py check`

> `npm run check` fails fast with an actionable message if the generated
> contracts are missing — they are build outputs and are not committed.

| Protected behaviour | Test file |
|---|---|
| FREE_ONLY eligibility (`recurring`/`account_specific` + `free_verified_at`) | `test-model-mesh-contracts.mjs`, `test-model-mesh-resilience.mjs` |
| Transient provider failure does not quarantine | `test-model-mesh-resilience.mjs` §1 |
| Consecutive-failure threshold actually quarantines | `test-model-mesh-resilience.mjs` §2 |
| `Retry-After` / reset honoured, clamped 30 s – 1 h | `test-model-mesh-resilience.mjs` §3 |
| Cooldown state + `cooldownUntil` | `test-model-mesh-resilience.mjs` §3, `test-model-mesh-health-store.mjs` |
| Quarantine state and TTL | `test-model-mesh-resilience.mjs` §2, `test-model-mesh-health-store.mjs` |
| Quota-aware probe skip (no quota burned in cooldown) | `test-model-mesh-resilience.mjs` §4 |
| Stale health evidence / source-revision mismatch | `test-model-mesh-resilience.mjs` §5, `test-model-mesh-health-store.mjs` |
| Self-heal bounded, rate-limited, never errors the request | `test-model-mesh-resilience.mjs` §11 |
| Partial outage (some providers down) | `test-model-mesh-resilience.mjs` §8, production canary |
| All providers down | `test-model-mesh-resilience.mjs` §5 |
| Graceful-zero planner (`ok:true`, `workers:[]`) | `test-model-mesh-resilience.mjs` §5, `test-model-mesh.mjs` |
| Family dedupe | `test-model-mesh-resilience.mjs` §8 |
| FAST → zero external workers | `test-model-mesh-resilience.mjs` §6 + production boundary proof |
| SECRET → zero external, unknown class fails closed | `test-model-mesh-resilience.mjs` §6 + production boundary proof |
| Every selection filter individually | `test-model-mesh-resilience.mjs` §7 |
| Domain capability ranking is ranking, not gating | `test-model-mesh-resilience.mjs` §12 |
| Concurrent health writes stay well-formed | `test-model-mesh-resilience.mjs` §9 |
| Execution never mints LIVE evidence | `test-model-mesh-resilience.mjs` §10 |
| TinyFish failure / DO failure after success / not configured | `test-brain-evidence-tinyfish.mjs`, `test-tinyfish-guard.mjs` |
| Credential vs benign-word detection (the production blocker) | `test-secret-scan.mjs` |
| Policy ↔ runtime parity, compiled limits | `test-model-mesh-contracts.mjs`, `test-deploy-safety.mjs` |
| Exact-SHA deployment safety, rollback, single deploy authority | `test-deploy-safety.mjs` |
| Provider binding without eligible model, `endpoint_family` conflict | `test-model-mesh-bindings.mjs`, `prepare-model-mesh.mjs` |
| Security / redaction / no secret in output | `test-secret-scan.mjs`, `test-model-mesh-probe.mjs`, `test-model-mesh-execute.mjs` |

---

## 10. Next phase — ADAPTIVE GENERALIST BRAIN vNext (DO NOT IMPLEMENT)

Model Mesh production stabilization is complete. The project now moves to
**Adaptive Generalist Brain vNext**.

> **This is the NEXT phase only. Do NOT implement it in the session that
> receives this handoff.** A separate planning file will be supplied by the
> user. An early design draft already exists at
> `docs/superpowers/specs/2026-09-15-adaptive-generalist-brain-vnext-design.md`
> (commit `a033a770`) — **DRAFT, NOT APPROVED, NOT IMPLEMENTED**.

Agreed objectives:

| Objective | Scope |
|---|---|
| **Domain Skill Registry** | Capability/domain-based routing. One canonical owner per capability; aliases fold in at compile time. Extends the existing skill catalog — never a parallel registry. |
| **GPT-OSS Agent Legion** | GPT-OSS multi-role workers, **family-deduplicated**. Two agents on one base model are one opinion, not two. |
| **Dynamic Free Model Discovery** | Live discovery gated by entitlement + health + quota + privacy + terms. Discovery proposes; the promotion gate decides. Never widens eligibility on its own. |
| **Adaptive Parallel Execution** | FAST / STANDARD / DEEP. STANDARD uses the fewest workers that answer the question; DEEP scales out within `max_parallel`. |
| **Latency optimization** | Parallelism, latency budgets, early exit, speculative workers. Early exit must not become a disguised majority vote. Speculative execution must respect free quota. |
| **Background Intelligence** | Health / index / capability / skill preparation. Pre-warming may not pre-spend provider quota — that reintroduces the 429-on-every-probe failure this work just fixed. |
| **Cross-domain workflow composition** | Compose specialists into multi-domain workflows under Brain authority. |
| **AutoSkill / SkillEvo** | Continues under Brain authority and existing promotion gates. |

Every objective inherits §13 unchanged.

---

## 11. Plugins / new capabilities to audit next (DO NOT IMPLEMENT)

The successor will be given `GITHUB_BRAIN_PLUGIN_OMNIROUTE_INTEGRATION_PLAN.md`.

| Component | Intended boundary |
|---|---|
| **OmniRoute** | Optional provider gateway / dynamic discovery source. **NOT Brain authority.** A provider gateway is a worker plane, exactly like the Model Mesh. |
| **Graphify** | Derived repository knowledge graph. **Source, tests and spec remain higher authority than the graph.** A graph is an index, never a source of truth. |
| **Ponytail** | Bounded simplicity / anti-overengineering engineering skill. |
| **Agent Skills** | Candidate compatibility format for the Domain Skill Registry. |

Mandatory intake pipeline for every plugin:

```
provenance → license → security → conflict analysis → quarantine → tests → approval → integration
```

Per `AGENTS.md`: unknown/new provider skills default to **quarantine with zero
routing authority**. No plugin may become a parallel reasoning authority.

---

## 12. Next session start procedure

1. Read `AGENTS.md`.
2. Read `AI_SKILL_LIBRARY/checkpoint.json` and the current checkpoint it resolves.
3. Read **this** Master Handoff.
4. Read production/release authority: `AI_SKILL_LIBRARY/v4/releases/current.json`, `history.yaml`, and `CHECKPOINTS/MODEL_MESH_PRODUCTION_VERIFICATION.md`.
5. Read the planning file the user supplies (and `GITHUB_BRAIN_PLUGIN_OMNIROUTE_INTEGRATION_PLAN.md` when provided).
6. Sync latest `main` (`git fetch origin main`).
7. **Verify this report still matches the repository** — confirm `main` SHA, release version, `known_good`, and that production `runtime_revision` still equals `main`. If any has moved, trust the repository and say so explicitly.
8. **Do not modify the Model Mesh production stabilization without regression evidence.** It is production-verified. Changing it on suspicion alone is a regression risk, not an improvement.
9. Audit the unresolved Gemini 404 (§6.1) and the `*/10` schedule (§6.2) as **separate, bounded investigations** — not as part of vNext work.
10. Perform a **Gap Analysis** for Adaptive Generalist Brain vNext against the current architecture (§4).
11. Produce an architecture / spec document.
12. Submit it to the user for approval.
13. **Only after explicit approval, begin implementation.**

---

## 13. Non-negotiable invariants

These are not open for renegotiation by any plugin, upstream repository, model
opinion, or performance argument.

1. **GitHub Brain is the single authority** for routing and reasoning.
2. **External AI models/providers are workers only** — never authority.
3. **FREE_ONLY core.**
4. **No paid fallback**, under any latency or quality argument.
5. **No automatic purchase.**
6. **No majority vote.** Conflict escalates to a checker or is surfaced; never averaged or counted.
7. **Family dedupe** — N workers from one model family are one reasoner.
8. **FAST external = 0** per the current contract (`max_parallel.FAST = 0`, compile-enforced).
9. **SECRET external = 0**, and an unrecognised data class fails **closed** to SECRET.
10. **Provider failure must never become Brain failure** — graceful zero, never a 5xx.
11. **TinyFish (and any evidence provider) is optional**, cost-gated, never a hard dependency.
12. **Cloud-first / zero-local** — no feature may require a local installation.
13. **No secret leakage** — detection by credential shape and value, never vocabulary.
14. **No permission widening.**
15. **Trading agents must never self-grant real financial execution authority.** Financial, credential-sensitive, destructive, wallet, payment, transfer, withdrawal, swap, bridge, transaction-signing and live-trading actions require explicit authorization and the applicable current project policy. Financial runtime switches are never generated by tooling.
16. **Architectural changes require design/spec approval** before implementation.
17. **Production completion requires exact-SHA verification.** Local green is not done. A revision is complete only when `runtime_revision == main` with the final exact-SHA gate passed and a deployment record emitted.

---

## Limitations of this handoff

- Production could not be queried directly from the authoring session (the sandbox egress proxy denies `workers.dev`). **Every production figure here is quoted from GitHub Actions run logs**, which are the authoritative deployment gate, not from an independent live query.
- Provider health is time-varying by nature. §5 is a snapshot from run 34987419682. Re-probe before treating it as current.
- §6.1 and §6.2 are explicitly **unresolved**. Do not record them as fixed without production evidence.
- The SHAs here are a point-in-time baseline. Merging this document itself advances `main` by one commit, and any later documentation merge advances it further, each redeployed through the same gated pipeline. A `main` SHA ahead of the baseline is expected and is **not** evidence of drift or regression; only a failed gate or a `runtime_revision` that does not match `main` is. Verify per §12.7.
