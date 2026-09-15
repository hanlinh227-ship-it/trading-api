# Model Mesh Live Health and TinyFish Stabilization Design

## Status and authority

Approved architecture: option A. GitHub Brain V4 remains the only routing and reasoning authority. Model Mesh workers and TinyFish are subordinate execution/evidence services. FAST and SECRET traffic never leaves the Worker. The release remains `candidate` until Linux CI and exact-SHA production verification pass.

## Problem statement

The immutable Model Mesh snapshot describes configured candidates, but the runtime currently reports a provider as active from binding and credential presence alone. Every current model is statically `degraded`, while the selector only accepts `healthy`, so STANDARD and DEEP plans contain no workers. Probes are ephemeral, their errors are collapsed into `provider_error`, and CI accepts a partial probe result. Trial-credit models are also inconsistent with the FREE_ONLY runtime filter.

## Architecture

### Static registry and canonical FREE_ONLY policy

The source registry remains immutable at runtime. A versioned public policy artifact defines the only runtime-eligible free states. Recurring free access and account-specific verified free entitlement are eligible; trials, promotional credits, and time-limited offers are not. The compiler, JavaScript runtime, Python validation, health endpoint, planner, and CI consume or validate the same artifact.

### Live health overlay

`TRADING_STATE` stores Model Mesh records only under `brain:model-mesh:health:v1:`. No existing trading key is read, listed, changed, or deleted. Each model record includes schema version, provider/model fingerprint, source revision, state, sanitized failure category, observed time, expiry, latency, consecutive failures, and cooldown time. It contains no prompt, credential, response body, or raw provider error.

Runtime states are `CONFIGURED`, `LIVE_HEALTHY`, `DEGRADED`, `COOLDOWN`, `QUARANTINED`, and `NOT_ELIGIBLE`. A candidate is selectable only when it is FREE_ONLY eligible, configured, and has fresh `LIVE_HEALTHY` evidence for the current model fingerprint. Expired or missing evidence degrades safely. Authentication, entitlement, and model-not-found failures quarantine; rate limits and transient failures enter bounded cooldown. KV propagation is handled with bounded re-read retries and explicit stale status, never by optimistic activation.

### Planning and execution

Planning becomes environment-aware and reads the live overlay. FAST and SECRET always produce zero external workers. STANDARD selects one or two distinct model families when at least one live candidate exists. DEEP selects one to four. When none are live, the planner returns zero workers plus a stable `no_live_healthy_provider` reason. Provider execution updates health through tracked promises and never changes Brain routing decisions.

### Safe provider diagnostics

All adapters map failures to a closed enum: `AUTH_FAILED`, `MODEL_NOT_FOUND`, `RATE_LIMITED`, `FREE_ENTITLEMENT_INVALID`, `REQUEST_INVALID`, `REGION_UNAVAILABLE`, `TIMEOUT`, `PROVIDER_5XX`, `PARSE_FAILED`, or `UNKNOWN_SANITIZED`. Responses are read with a byte limit. Diagnostics expose only provider/model identifiers, state, status class, latency, and sanitized category. CI fails when any provider reported ACTIVE lacks a fresh live pass.

### TinyFish evidence lane

TinyFish is a separate Brain evidence path and is never a Model Mesh worker. Only the verified free Search and Fetch APIs are allowed; Agent and Browser APIs are forbidden under FREE_ONLY. The path is Brain request → policy guard → TinyFish Search/Fetch → bounded sanitizer → Brain synthesis input. FAST, SECRET, missing credentials, over-size inputs, redirects to unsupported hosts, and disallowed operations fail closed. The existing secret name is exactly `TINY_FISH_API`. Health and authenticated canary output only configuration and sanitized operational state.

### Deployment and security

Wrangler configuration continues using `keep_vars: true`; financial/live switches remain dashboard-owned. Secret sync uses stdin and suppresses Wrangler output. Deploy logs are passed through a redactor and never include variable values. Exact-main SHA is validated before deploy and after propagation. The rollout may expose diagnostic failure but may not call a partial provider matrix healthy or mark the release known-good.

## Acceptance criteria

- Static snapshot and runtime health are distinct and source snapshot bytes are never mutated.
- One FREE_ONLY definition is enforced everywhere; trials are not selectable.
- FAST/SECRET select zero; STANDARD selects 1–2 and DEEP 1–4 when fresh healthy providers exist; all-down is graceful and explicit.
- Family deduplication remains enforced.
- Stale, cooldown, quarantine, and recovery transitions are deterministic and tested.
- Provider and TinyFish outputs never expose secrets, raw prompts, or raw response bodies.
- CI cannot pass a reported ACTIVE provider without a live probe pass.
- TinyFish uses only Search/Fetch, with timeouts, bounded retries, rate/circuit protection, and separate health/canary evidence.
- Existing Bybit routes, bindings, runtime switches, and event-driven trading behavior remain unchanged.

