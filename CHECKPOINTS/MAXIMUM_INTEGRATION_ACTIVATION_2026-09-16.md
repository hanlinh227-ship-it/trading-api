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
| cohere | NOT_ELIGIBLE_FREE_ONLY | admitted model is `trial_credit`; discovery-only until a zero-cost tier appears |
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

**LIVE_HEALTHY: 5** on release 4.10.1 (deploy run 35051343161) - groq, cloudflare_workers_ai,
openrouter, alibaba_model_studio and now **nvidia_nim** on
`meta/muse-glimmer-30b` at 200 in 2013ms. gemini and mistral sit in COOLDOWN on
429; a rate limit is a cooldown and a rotation, not a loss, and both re-enter
when their window resets.

### Why entitlement stopped here, and what replaced it

A model listing proves reachability, never that access is free. The policy that
turned on that distinction admitted only `recurring` and `account_specific`,
which kept paid usage out but also kept out models that genuinely cost nothing
right now — and it decided eligibility per provider, so one paid model or one
retired model id wrote off a whole catalog.

`free_only_policy.json` schema 2 replaces that rule. FREE_ONLY now means **zero
monetary cost at execution time**, proven per model:

| Class | Autonomous | What has to be true |
|---|---|---|
| `recurring` | yes | recurring $0 tier evidence |
| `account_specific` | yes | account-specific $0 evidence |
| `temporary_zero_price` | yes | live price = 0, re-proven every 24h, auto-quarantined the moment it rises |
| `free_quota_hard_stop` | yes | free quota remaining, a verified hard stop, and an unexpired window |
| `trial_credit` | no | only after conversion to a hard-stop class with proof |
| `paid` | never | rejected |

A recorded price above zero vetoes a model whatever its class says, because the
class is a claim and the price is evidence. **Writing a zero-cost class without
that evidence would fabricate the exact fact the policy exists to require.**

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

The entitlement blocker recorded earlier in this session is closed. It said
admission needed the account holder's tier confirmation because no runtime
endpoint exposes it; the zero-cost classes plus a model-level probe now decide
admission from current price and quota evidence instead of from a tier label.
`alibaba_model_studio` is admitted as `free_quota_hard_stop` on a console
verification (Free Quota Only enabled, quota status Enabled, window to
2026-11-21), so it cannot fall through to PAYG; it leaves the pool by itself on
expiry or when headroom reaches the safety reserve.

### Probe round 2026-09-16 (run 35047130298, main 69dd282)

The live probe ran against nvidia_nim, sambanova and opencode_zen. **No model
was admitted.** Each provider failed a different half of the test, and the
distinction is the point: a completed call is not evidence that the call was
free, and a published price is not evidence that the model answers.

| Provider | Listing | Completion | Zero-cost | Outcome |
|---|---|---|---|---|
| nvidia_nim | 200, 82 models | `meta/muse-glimmer-30b` **200 on the first candidate** | **not proven** — no published price, no runtime tier endpoint | fail-closed; liveness recorded |
| sambanova | 200, 7 models | never attempted | **disproven** — all 7 publish a price above zero | fail-closed; discovery-only |
| opencode_zen | 200, 70 models | `muse-spark-1.3` **401** | not proven — no published price | fail-closed; credential scope issue |

Three things this round settled:

**The price-aware skip earned its place immediately.** SambaNova's seven models
are all priced, and the probe skipped every one before making a call. Without
that skip this round would have spent money on seven billable completions to
learn that SambaNova has no free tier for this account. The earlier single 402
was not a fluke of one model: the whole catalog is priced.

**NVIDIA's liveness gap is closed; its cost gap is not.** The probe-driven loop
found a working model on its first candidate, which is exactly what two
hand-picked ids failed to do. But NVIDIA publishes no price in `/v1/models` and
exposes no tier endpoint, so admitting it would assert a zero cost nothing has
shown. It waits on the same kind of account evidence Alibaba has.

**~~The documented Zen free models do not exist.~~ CORRECTED by probe run
35048454601.** They do exist. The first round printed the catalog capped at 40
of 70 ids and that capped list was read as the whole catalog, so six models
present in it were reported absent. `big-pickle`, `mimo-v2.5-free`,
`ling-3.0-flash-fin-free`, `nemotron-3-ultra-free`,
`nemotron-3.5-lightning-free` and `muse-spark-1.3-contributor-free` are all in
the live listing, alongside `deepseek-v4-flash-free` and
`muse-spark-1.2-contributor-free`. The listing now announces when it truncates,
so a capped list cannot be mistaken for a complete one again. The 401 on
completions was real and is still open.

### Probe round 2 (run 35048454601): what the APIs actually expose

The account holder verified that NVIDIA Build marks models Free Endpoint and
that Zen's pricing page lists six Free models. Round 2 asked whether either API
exposes that, by dumping the catalog row shape instead of guessing field names.

Both are bare OpenAI listings. Every row carries exactly
`created, id, object, owned_by` — **no price, no free marking**:

```
PROVIDER_FREE_LABELS provider=nvidia_nim    labelled=0/82 (catalog exposes no free-tier field)
PROVIDER_FREE_LABELS provider=opencode_zen  labelled=0/70 (catalog exposes no free-tier field)
```

So the free marking is a **website-only fact** for both. With
`probe_require_free_label` on, all 152 candidates were skipped and **not one
completion call was made** — the round cost nothing and admitted nothing, which
is the correct outcome when the evidence a rule requires is absent.

That splits the two providers cleanly:

- **nvidia_nim** stays fail-closed on a provider-side evidence gap. The API
  offers no way to tell a Free Endpoint model from a paid one, and admitting on
  the website's word would assert a fact the runtime cannot check. Closing this
  needs NVIDIA to expose the tier, or an account-holder attestation of the kind
  that admitted Alibaba, recorded as attestation rather than as provider
  evidence.
- **opencode_zen** turned out to be settled, and not on cost. Probe run
  35049301279 matched all 8 documented free ids against the live catalog (8/8)
  and probed them. The answer came back from the provider itself:

  ```
  big-pickle  400  "OpenCode's free tier can only be used in OpenCode"
  ```

  Zen restricts its free tier to the OpenCode client. The models exist, billing
  is off, the credential lists fine — the tier simply cannot be reached from an
  API client. That is a provider policy limit, not a pricing or credential gap,
  and impersonating the client to get around it would be circumvention. Zen is
  discovery-only until the provider opens the tier to API clients.

  The probe now recognises a refusal that describes the tier rather than the
  model and ends the round there, instead of walking the rest of the list to
  collect the same answer.

### Release 4.10.1: NVIDIA admitted on two-source evidence

Probe run 35050894513 resolved the account holder's Free Endpoint capture
against the live 82-model listing, and 4.10.1 shipped the one model that cleared
every condition.

**Resolution: 21 of 36 display names.** Each had to normalize to exactly one
live id. The 15 that did not are out on purpose: 13 are absent from the API
listing, and 2 are near misses whose candidates are recorded rather than chosen
-- `ising-calibration` did not become ising-calibration-1.5-31b, and
`synthetic-video-detector` did not become ai-synthetic-video-detector. Choosing
either would repeat the guess that once put two non-existent ids in this
registry.

**Modality: 16 text_chat, 5 deferred.** One embedding, one vision-specialized
and three safety models are recorded with their class and kept out of the chat
pool. Sending them to `/chat/completions` would return a meaningless 400.

**Admitted: `meta/muse-glimmer-30b`,** and only it. All four conditions held at
once -- on the captured catalog, in the live listing, HTTP 200 on chat
completions, covered by the attestation. Its provenance splits the evidence:
`pricing_evidence_source: vendor_web_catalog` with the capture timestamp for
price, the probe run for liveness, and a 30-day revalidation window so a web
page cannot vouch for it indefinitely. The other 15 text_chat models are
resolved and catalogued but unadmitted: the probe stops at its first success, so
only one carries a completion PASS, and a resolution is not a liveness proof.

Production verified by deploy run 35051343161 with no rollback:

```
MODEL_MESH_PROBE=PASS probed=7 configured=7 successful=5 unavailable=2
MODEL_MESH_LIVE_OVERLAY=PASS active=5
FREE_ONLY_ZERO_COST_GUARD=PASS models=7 zero_price=7 finite_quota=1 hard_stop_missing=0
  paid_fallback=disabled auto_purchase=false next_quota_expiry=2026-11-21
  classes={free_quota_hard_stop:1, recurring:3, account_specific:2, temporary_zero_price:1}
SECRET_EXTERNAL_BOUNDARY=PASS http=403    DATACLASS_FAIL_CLOSED=PASS
FAST_EXTERNAL_BOUNDARY=PASS external_workers=0 externalRoutingCalls=0
FINAL_EXACT_SHA_GATE=PASS revision=168ba9cf5a08b51297b453d432198d93e9ecaa62
```

### Remaining, in order of what unblocks most

1. **nvidia_nim** — admitted and LIVE_HEALTHY on `meta/muse-glimmer-30b`. What
   remains is optional breadth, not a blocker: 15 resolved text_chat models
   await a probe-all round (the probe stops at its first success), and the
   Free Endpoint capture revalidates by 2026-10-16 or its model quarantines
   itself.
2. **opencode_zen** — closed as discovery-only on a provider restriction, not
   an account gap. Nothing to do here unless Zen opens its free tier to API
   clients.
3. **sambanova, cerebras, cohere** — discovery-only on provider evidence
   (priced catalog; finite free trial; trial/evaluation). None is a code change;
   all re-enter automatically if a zero-price model or tier appears.
   `huggingface_inference_providers` is admissible as `free_quota_hard_stop`
   once remaining included credit is readable at runtime.
4. Phases 15–17 (auto-recovery scenario matrix, full E2E profile matrix) are
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
