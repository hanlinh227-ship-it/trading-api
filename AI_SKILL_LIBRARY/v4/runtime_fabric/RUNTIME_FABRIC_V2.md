# Runtime Fabric V2 — zero-cost portable execution capacity

The fabric answers one question: **where can this capability run right now, for
free, at the revision we mean?**

It never answers what to do, which model to use, or whether a request is
admitted. Those belong to `GITHUB_BRAIN_V4`, `task_router` and the Model Mesh.

```
GITHUB_BRAIN_V4 → task_router → AI Legion → Model Mesh → Runtime Fabric
                                                              ↓
                                                  execution → verifier → evidence
```

The fabric is **capacity, not authority**. `RuntimeFabric` fixes all six
authority flags to `False` as class attributes, and passing one to the
constructor raises `AuthorityViolation` rather than being quietly ignored —
because silently ignoring it would let a caller believe it had been granted.

## Verification axes

Six facts, recorded **separately** and never collapsed:

| Axis | Means |
|---|---|
| `configured` | credentials and settings exist |
| `deployed` | something is actually running |
| `health_verified` | a probe answered |
| `exact_sha_verified` | it is running *the commit we mean* |
| `free_tier_verified` | the free tier was checked, not assumed |
| `production_eligible` | **derived from the above — never stored** |

`production_eligible` is deliberately absent from the registry. A stored
eligibility flag and the facts it summarises are two things wearing one name,
and every time this repository has let one label carry two facts, a bypass
followed. A test asserts no entry declares it.

The distinction earned its keep immediately: while the deploy authority was
failing, Cloudflare was `health_verified: true` and `exact_sha_verified: false`
— it answered, but at a commit from before the failure. A single "healthy" flag
would have hidden a frozen production runtime behind a green check. Both axes
are true now, and they became true separately, which is the point.

## States

`UNVERIFIED · PROBING · HEALTHY · DEGRADED · RATE_LIMITED · QUOTA_LOW ·
QUOTA_EXHAUSTED · CIRCUIT_OPEN · HALF_OPEN · COOLDOWN · DISABLED · QUARANTINED`

`STATE_VALUES` is derived from the table that documents them, so the two cannot
disagree about which states exist.

Only `HEALTHY` and `QUOTA_LOW` are selectable. `QUOTA_LOW` is selectable on
purpose: nearly-spent free quota is still free, and excluding it would push work
toward nothing rather than toward a cheaper path.

## Selection

Eligibility is a conjunction — verified **and** free-only **and** capability
match **and** health ok **and** quota available **and** exact-SHA **and**
lifecycle `STABLE`. Selection walks `tier_order`
(`primary → secondary → tertiary → batch_recovery → emergency`) and **never
selects by provider brand**.

A refusal returns *every* failing reason, not the first. "Not eligible" that
could mean six different things sends an operator to fix the wrong one — which
in this repository cost a real credential rotation that was never the cause.

No eligible runtime ⇒ `CAPABILITY_TEMPORARILY_UNAVAILABLE`. Never a paid
escalation, never a retired provider.

## Circuit breaker

`failures → DEGRADED → (threshold) → CIRCUIT_OPEN → (cooldown) → HALF_OPEN →
probe → HEALTHY | CIRCUIT_OPEN`

One transient error never causes a failover. Half-open is **one** chance, not a
fresh threshold's worth. Runtime ping-pong is worse than a slow runtime: it
multiplies load across providers, burns free quota on retries, and makes
evidence unreadable.

## Zero-cost guard

Separate from eligibility on purpose. "Not ready" and "would charge you" are
different failures needing different responses, and the second must never be
resolved by waiting. Refuses on mandatory billing, unverified free tier, or
exhausted free quota.

An unverified free tier is `false`, not true-by-reputation: a provider *having*
a free plan is not evidence anyone checked.

## Workload placement

| Workload | Runtime class |
|---|---|
| HTTP / API | Cloudflare → Deno → Netlify |
| scheduled / batch / probes | GitHub Actions |
| container-only | Koyeb / Render (emergency) |
| model & provider selection | **Model Mesh only** |

GitHub Actions is `http: false`. It cannot hold a persistent endpoint, so it is
never eligible for `http_api` however healthy it is.

## Stable vs development lab

`DISCOVERED → ADAPTER_READY → TESTED → LIVE_PROBED → VERIFIED → PROMOTABLE →
STABLE`, failure → `QUARANTINED`.

Only `STABLE` may take stable traffic. A development runtime that is fully
verified on every axis is still refused until promoted.

## Evidence

Operational facts only, from a closed allowlist. An unknown field is **refused,
not dropped** — silently discarding a field a caller believed was recorded is
how a secret ends up believed-redacted and actually absent from the audit trail
it was supposed to be in. Never hidden reasoning, never credentials.

## Anti-regression

Railway is retired. The refusal is in code, not commentary:
`retired_provider_reasons()` matches the runtime id *and* any endpoint it
declares, so a renamed entry pointing at a `railway.app` URL is refused too.
Tests add a *perfect* Railway entry — every axis true, `STABLE`, primary tier —
and require refusal.

## Current truthful state

This table is a **reading of the registry, not a second record of it**. It goes
stale the moment the registry moves, so treat `registry.yaml` and
`acceptance.py` as the authority and this as commentary. (It did go stale once,
describing a frozen Cloudflare and an undeployed Deno after both had been
promoted — a doc asserting a state the evidence contradicts is the same
one-label-two-facts defect this module exists to refuse.)

| Runtime | Tier | Lifecycle | Production eligible |
|---|---|---|---|
| cloudflare_workers | primary | STABLE | yes — all five axes verified |
| deno_deploy | secondary | STABLE | yes — live-probed, exact SHA matched |
| netlify_functions | tertiary | ADAPTER_READY | no — not configured, not deployed |
| github_actions | batch_recovery | STABLE | yes, for batch — never for HTTP |
| koyeb_free | emergency | DISCOVERED | no — free tier unverified |
| render_free | emergency | DISCOVERED | no — free tier unverified |

Registry eligibility is not the acceptance matrix. `FULL_ACTIVE` stays false
while `CLOUDFLARE_DEPLOY`, `CLOUDFLARE_HEALTH`, `CLOUDFLARE_SHA_MATCH` and
`LIVE_RESEARCH_SMOKE` are `NOT_OBSERVED` — recorded verification and a gate
observed on this run are different facts, and not observing a gate never counts
as passing it.
