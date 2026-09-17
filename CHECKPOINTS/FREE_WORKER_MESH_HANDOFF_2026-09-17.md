# Free Worker Mesh — canonical handoff (2026-09-17)

**Read this before adding an executor, a provider, or a wave.**

Canonical spec: `AI_SKILL_LIBRARY/v4/local_runtime/FREE_WORKER_MESH.md`.
Registered in `AI_SKILL_LIBRARY/checkpoint.json` as `free_worker_mesh_spec_path`.

## What exists now

A single execution-capacity surface under the existing runtime scheduler,
covering every executor the federation has or will have: this container, an
operator's Mac/Windows/Linux/VPS, CI runners, hosted serverless catalogs, and a
`FUTURE_PROVIDER` class for types nobody has thought of yet.

It holds **no authority**. `task_router` routes, AI Legion assigns roles, the
Model Mesh selects models, the Open Model Universe admits, the runtime scheduler
places. The mesh answers "which executor could carry this" and nothing else. The
authority flags are class attributes fixed at `False`, so acquiring one is a
`TypeError` rather than an oversight.

## The three rules a future session must not soften

1. **A capability qualifies a worker only when it has been measured.**
   `declared_capabilities` advertises; `measured_capabilities` qualifies. This is
   what makes the fabric wave-independent: Wave 4's `vision` or `ocr` is a new
   string matched by existing code, and adding it is a measurement, not an
   architecture.
2. **A capability fallback is never availability.** A provider serving a
   *different* model supplies the capability under its own name. `executed_model`
   and `ran_the_requested_model` are recorded on every placement. A hosted model
   has no artifact digest, so evidence taken there can never be bound to the
   model that was asked for.
3. **Documentation is not execution proof.** A provider is selectable only in
   `VERIFIED_AVAILABLE` or `VERIFIED_LIMITED`, both of which require something to
   have actually run. `DISCOVERED` is the default so that omission fails closed.

## Scoped conclusions

A resource measurement is a fact about the machine it was taken on. This
container's RAM is not operator hardware, not a GitHub limit, and not a property
of any model. A model that does not fit here is `REMOTE_WORKER_REQUIRED` with
the shortfall named — never "infeasible". Do not re-collapse these.

## Wave 3 state at this handoff

| Candidate | State | Blocker |
|---|---|---|
| Qwen/Qwen3-8B-GGUF | `AVAILABLE_LOCAL` | none; admitted and measured |
| microsoft/Phi-4-mini-instruct | `ADMISSION_PENDING_WORKER_AVAILABLE` | artifact provenance; a worker meets its ~5000 MB |
| deepseek-ai/DeepSeek-R1-Distill-Qwen-7B | `ADMISSION_PENDING_WORKER_AVAILABLE` | artifact provenance; a worker meets its ~9360 MB |
| openai/gpt-oss-20b | `PROVIDER_PATH_PENDING_VERIFICATION` | **exact model** is on Workers AI as `@cf/openai/gpt-oss-20b`; blocked on token scope |
| Qwen/Qwen3-Coder-30B-A3B-Instruct | `PROVIDER_PATH_PENDING_VERIFICATION` | **capability fallback only** — `@cf/qwen/qwen2.5-coder-32b-instruct`, not the same model |
| google/gemma-3-4b-it | `HUMAN_LICENSE_GATE_REQUIRED` | a licence only the operator can accept; deferred to Wave 4 |

Cloudflare's entire Qwen catalog is three models and Qwen3-Coder-30B-A3B is none
of them. Do not record the qwen2.5-coder substitute as availability of the
Qwen3-Coder candidate.

## The one operator action outstanding

Grant the repository's `CLOUDFLARE_API_TOKEN` the **Workers AI: Read**
permission, or add a second token carrying it.

Probe run 35245779094 presented the existing token to the Workers AI run API for
all three recorded models; Cloudflare answered HTTP 401 / error 10000 on each.
The credential exists and its scope does not cover this API.

This is a token scope change only — **no new account, no plan change, no
payment**. The Workers Free plan already includes 10,000 Neurons per day and has
no billing path, so it cannot be charged.

Once granted, re-dispatch `wave3-model-discovery.yml` with
`probe_workers_ai: yes`. A `FREE_TIER_SERVES_IT` verdict on `@cf/openai/gpt-oss-20b`
moves it to `AVAILABLE_SERVERLESS` with no other change.

## Evidence

| File | What it holds |
|---|---|
| `CHECKPOINTS/evidence/FREE_WORKER_MESH_PROOF.json` | nine scenario rounds plus a live federated inference |
| `CHECKPOINTS/evidence/WAVE3_FREE_EXECUTION_PATHS.json` | every zero-cost path and its verified facts |
| `CHECKPOINTS/evidence/WORKERS_AI_FREE_TIER_PROBE.json` | the 401 result and the named remedy |
| `CHECKPOINTS/evidence/WAVE3_PLACEMENT.json` | per-model placement against the current pool |
| `CHECKPOINTS/evidence/WAVE3_FEDERATION_PROOF.json` | nine-round federation proof, no round resolved by vote |

## For Wave 4 and later

Declare capability requirements. Add a provider adapter only where one is
genuinely needed. **Do not create** a second Brain, router, Model Mesh, model
registry, scheduler, lifecycle manager, admission authority or evidence
authority — all of them already exist, and the readiness test
(`test_a_future_capability_needs_no_new_authority`) passes without any of them
changing.
