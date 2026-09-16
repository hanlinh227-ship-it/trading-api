# MAXIMUM VERIFIED INTEGRATION ACTIVATION — CLOSURE (2026-09-16)

> Closure record for the activation phase that followed vNext B–H.
> Evidence vocabulary matches the master handoff §2:
> SOURCE VERIFIED / CI VERIFIED / PRODUCTION VERIFIED / NOT VERIFIED.
>
> Re-verify every number here against the repository before trusting it.

---

## 1. Final state

| Field | Value | Status |
|---|---|---|
| Release | `4.9.8` | SOURCE VERIFIED |
| `KNOWN_GOOD` | **YES** | PRODUCTION VERIFIED |
| Previous release | `4.9.7`, known-good (single-step rollback target) | SOURCE VERIFIED |
| Worker | `trading-v77-scanner` | SOURCE VERIFIED |
| Deployment authority | `deploy-skill-mandatory-fast-gateway.yml` (**sole**) | SOURCE VERIFIED |

Merged: PRs #356-#369.

---

## 2. Health-refresh automation — RESOLVED, mechanism changed

**GitHub Actions cron cannot hold the 30-minute `LIVE_TTL_MS`.** Measured, not
assumed: with a fixed-minute 20-minute cadence live on `main` for 4.9 hours,
exactly **one** scheduled run fired (21:14Z, not even on a cadence boundary) —
the same ~1-per-5h rate as the `*/10` form it replaced. The cron *expression*
was never the variable; GitHub sheds this repository's schedules.

Proactive refresh now runs on the **Cloudflare Worker's own cron** (`*/20`).

**Proof of a real scheduled execution** (this is the load-bearing evidence):
at `2026-09-15T23:47:58Z`, **33 minutes** after the last externally triggered
probe with none in between, `groq`, `cloudflare_workers_ai` and `openrouter`
were still `LIVE_HEALTHY`. Evidence expires after 30 minutes, so they would
have lapsed at ~23:44. Only the Worker cron can have refreshed them. Mistral
had independently moved COOLDOWN→DEGRADED in the same window.

Bounded by construction: fails closed on an unrecognised cron; shares the
existing `claimSelfHeal` KV claim so the manual and scheduled probes contend
for **one** lock; isolates provider failures; and its executable code is
asserted never to reference a trading or deploy surface.

The deploy-safety rule is now **semantic**, not a blanket ban: financial,
trading, deploy and autonomous crons remain forbidden; only the single
read-only health cron is permitted; and `prepare-wrangler` validates its own
generated output via `assertHealthOnlyCrons`.

---

## 3. Provider matrix — measured, not assumed

`LIVE_HEALTHY` at last measurement: **groq**, **cloudflare_workers_ai**,
**openrouter**.

| Provider | State | Evidence |
|---|---|---|
| groq | LIVE_HEALTHY | live probe 200 |
| cloudflare_workers_ai | LIVE_HEALTHY | live probe 200 |
| openrouter | LIVE_HEALTHY | live probe 200 |
| gemini_developer_api | DEGRADED (recoverable) | model migrated; last call 503 UNAVAILABLE, transient |
| mistral | COOLDOWN → DEGRADED | 429 RATE_LIMITED, recovers on TTL |
| nvidia_nim | reachable, ACCOUNT_ENTITLEMENT_UNAVAILABLE | listing OK 200, 82 models |
| cerebras | reachable, ACCOUNT_ENTITLEMENT_UNAVAILABLE | listing OK 200, 2 models |
| sambanova | reachable, ACCOUNT_ENTITLEMENT_UNAVAILABLE | listing OK 200, 7 models |
| alibaba_model_studio | reachable, ACCOUNT_ENTITLEMENT_UNAVAILABLE | listing OK 200, 167 models |
| huggingface_inference_providers | reachable, entitlement VERIFIED non-paid | `whoami-v2`: `plan=user isPro=false no_billing_period` |
| cohere | NOT_ELIGIBLE_FREE_ONLY | admitted model is `trial_credit` |
| opencode_zen | NOT_ELIGIBLE | `usage_terms: evaluation`; catalog is premium frontier models only |

### Gemini — root cause

`gemini-2.5-flash` was listed for the account **and** advertised
`generateContent`, yet `POST :generateContent` returned 404 NOT_FOUND;
`gemini-2.5-flash-lite` did too. The 2.5 generation is retired for generation
while its listing metadata lingers. **ListModels is not a liveness guarantee.**
Replacement chosen by probing, not guessing: `gemini-flash-latest` → 200.
The alias tracks Google's current flash model, so the next retirement cannot
silently quarantine the provider again.

### SambaNova — root cause

The original `NETWORK_ERROR http=0` was undiagnosable because the listing
helper collapsed every thrown error to status 0. With the transport reason
retained, SambaNova resolves and lists 7 models: the original failure was
transient reachability, not a wrong endpoint.

### Account-holder attestation round — outcome

The account holder attested free-recurring or account-specific free access for
nvidia_nim, cerebras, sambanova and alibaba_model_studio. All four were admitted
on that attestation (recorded as `entitlement_evidence`, explicitly an
attestation and never dressed as provider evidence) and then probed live.
**Only one survived the probe.**

| Provider | Probe | Outcome |
|---|---|---|
| alibaba_model_studio | `qwen3.8-flash` 200 | ADMITTED, LIVE_HEALTHY |
| cerebras | `qwen-3.8-27b` 402 | REMOVED - `FREE_ENTITLEMENT_INVALID` |
| sambanova | `Meta-Llama-3.3-70B-Instruct` 402 | REMOVED - `FREE_ENTITLEMENT_INVALID` |
| nvidia_nim | 410 then 404 on two listed models | REMOVED - listing is not liveness |

The operating rule this established, and the one to keep: **an attestation is
good evidence where the provider is silent, and is overridden where the provider
itself answers.** Cerebras and SambaNova both returned 402 Payment Required,
which is the provider directly contradicting the attested free access, so they
were removed rather than retained.

NVIDIA is a different failure: two models that the live `/v1/models` listing
returned both failed on chat completions (410 Gone, then 404 MODEL_NOT_FOUND).
This is the same listing-versus-liveness gap proven on Gemini. Re-admitting
NVIDIA requires a probe-driven selection loop like the Gemini diagnostic - not
another model id chosen by hand.

**LIVE_HEALTHY: 4** - groq, cloudflare_workers_ai, openrouter,
alibaba_model_studio.

### Why entitlement stops here

A model listing proves reachability, never that access is **recurring** free
rather than trial credit or paid — and `free_only_policy.json`
(`eligible_statuses: [recurring, account_specific]`) turns on exactly that
distinction. Only HuggingFace exposes plan at runtime. For the rest, no
runtime endpoint exposes entitlement, so they are recorded as
`ACCOUNT_ENTITLEMENT_UNAVAILABLE` rather than admitted on an assumption.
**Writing `free_status: recurring` without evidence would fabricate the exact
fact the policy exists to require.**

---

## 4. Integration states

| Integration | State | Proven by |
|---|---|---|
| **OmniRoute** | **Stage A ON** (`A_discovery_catalog`) | Enabled for candidate normalisation only. Not on by default, no network execution, sandbox only, no authority, every forbidden default off. A fully verified candidate is still quarantined; paid/trial/promo/promotional/credit refused; each of five verification gates independently blocks. |
| **Agent Skills** | Functional, quarantine-controlled | Real `SKILL.md` through parse→normalize→admission; injected "you are now the routing authority" body with unverified provenance refused for all three reasons. |
| **Graphify** | Functional, derived only | Real build; bounded by `max_nodes`; exact source SHA; marked stale at a different SHA. |
| **Ponytail** | Functional, advisory only | Requests to drop `security_tests` and `acceptance_criteria` land in `rejected_removals`, `accepted_removals` empty. |
| **Legion** | Functional, subordinate | FAST → zero nodes and `max_parallel: 0`; STANDARD ≤2, DEEP ≤4; every node assigned; routing/reasoning authority false. |
| **Adaptive execution** | Bounded, speculation OFF | Budgets 0/2/4. Speculation refuses when the enable is merely omitted and when any gate flips. Early exit refuses same-family checker, REJECT, unresolved conflict, each maker gate, missing evidence — no majority-vote path. |

### OmniRoute Stage B/C are not reachable

`executable_dependency_added: false` — there is no OmniRoute dependency in the
runtime to execute through. Stage B (sandbox network execution) and Stage C
(production gateway) are not a flag flip; reaching them means adding an
upstream executable dependency, a supply-chain decision. **Stage A is the
highest safe verified stage.**

---

## 5. Operational readiness

| Property | Result | Evidence |
|---|---|---|
| **Rollback** | VERIFIED | Exercised twice under real failure. A failing provider canary produced `ROLLBACK=PASS` to the previous good revision, and production stayed serving throughout. |
| **Cold start / redeploy recovery** | VERIFIED | Health evidence lives in KV and survives redeploys; `scheduleSelfHeal` re-probes on demand when a plan finds no live provider. Both observed across the rollbacks above. |
| **Idempotency** | VERIFIED | The shared `claimSelfHeal` claim suppresses an overlapping probe (asserted in `test-scheduled-health.mjs`); `release.py` manifests are content-hashed and `_rows_for` de-duplicates. |
| **No manual step** | VERIFIED | The refresh cron runs Worker-side. The scheduled execution at 23:47:58Z occurred with no local machine involved. |
| **Boundaries** | PRODUCTION VERIFIED | Every gated deploy: `FAST_EXTERNAL_ROUTING_CALLS=0`, SECRET external boundary proof PASS, `MODEL_MESH_MODE=FREE_ONLY`, `MAX_PARALLEL=STANDARD=2 DEEP=4 FAST=0`, `MODEL_MESH_ROUTING_AUTHORITY=false`. |

### Known fragility (not a regression)

The deploy canary requires at least one `LIVE_HEALTHY` provider and probes every
configured provider on every deploy. Under a rapid sequence of merges the free
tiers saturate and the canary fails, which is what produced both rollbacks in
this session. The gate behaved correctly each time — it is a rate-of-deploy
constraint, not a defect. The 20-minute Worker cron adds modest additional
probe volume.

---

## 6. Remaining blockers

1. **`ACCOUNT_ENTITLEMENT_UNAVAILABLE`** — nvidia_nim, cerebras, sambanova,
   alibaba_model_studio. Reachable with working credentials, but no runtime
   endpoint exposes whether the plan is recurring-free. Needs the account
   holder's confirmation of tier, or a provider billing endpoint. Once the
   tier is known, admission needs only a registry entry and a probe.
2. **`NOT_ELIGIBLE` by policy** — cohere, opencode_zen, and the trial-credit
   models on huggingface and alibaba. No credential changes these; they need a
   recurring-free model admitted instead.
3. Phases 15–17 (auto-recovery scenario matrix, full E2E profile matrix) are
   partially evidenced through production boundary proofs rather than a
   dedicated scenario suite.

---

## 7. Next session

`AGENTS.md` → `AI_SKILL_LIBRARY/checkpoint.json` →
`AI_SKILL_LIBRARY/AI_GLOBAL_CHECKPOINT.md` →
`CHECKPOINTS/GITHUB_BRAIN_MASTER_HANDOFF_2026-09-15.md` →
`CHECKPOINTS/GITHUB_BRAIN_VNEXT_CLOSURE_2026-09-15.md` → this file.

Re-verify `main`, release, `known_good` and production `runtimeRevision`
parity before trusting any number written here.
