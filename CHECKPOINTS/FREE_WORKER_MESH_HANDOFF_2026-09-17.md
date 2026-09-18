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

## Wave 3 — CLOSED

`WAVE3_OPERATIONAL_CLOSED = true`
`WAVE3_ALL_EXACT_MODELS_AVAILABLE = false`

**These are different facts and neither implies the other.** Wave 3 closed
because every candidate reached a terminal state with an exact, evidenced
blocker, no authorized zero-cost path was left unexplored, and the wave's
capabilities are covered by measured models. It did **not** close by making
every candidate available — three end with no executable exact path, and that
is recorded rather than smoothed over.

| Candidate | Terminal state | Exact model executable |
|---|---|---|
| Qwen/Qwen3-8B-GGUF | `AVAILABLE_LOCAL` | yes |
| openai/gpt-oss-20b | `AVAILABLE_SERVERLESS` | yes |
| Qwen/Qwen3-Coder-30B-A3B-Instruct | `REMOTE_WORKER_REQUIRED` | **no** |
| microsoft/Phi-4-mini-instruct | `QUARANTINED_PROVENANCE` | **no** |
| deepseek-ai/DeepSeek-R1-Distill-Qwen-7B | `QUARANTINED_PROVENANCE` | **no** |
| google/gemma-3-4b-it | `DEFERRED_TO_WAVE4` | **no** |

**Why the three closed unavailable.**

*Qwen3-Coder-30B* needs ~37,200 MB, which no attached worker meets. Cloudflare's
whole Qwen catalog is three models and this is none of them; the NVIDIA NIM free
catalog holds 21 models and no Qwen; SambaNova's catalog is entirely priced. The
remaining providers are non-autonomous or have no recorded catalog, so they are
**UNVERIFIED and deliberately not called absent**. Cloudflare does serve
`@cf/qwen/qwen2.5-coder-32b-instruct` — a **separate fact**, carried as
`capability_fallback`, never as this model's state.

*Phi-4-mini and DeepSeek-R1-Distill-Qwen-7B* are quarantined on provenance. The
final search read the artifacts' own GGUF metadata rather than their READMEs.
Across five conversions, **not one names a base revision**. The unsloth Phi-4
build comes closest — its GGUF carries `general.quantized_by: Unsloth` — and it
still cannot say which commit of the base weights it converted. Capacity was
never the blocker for either; a worker meets both comfortably.

*Gemma-3-4B* is gated on a licence only the operator can accept.

**None of these rules was relaxed to close the wave.** One was tightened mid-work:
`provenance_complete` had been checking base model and converter only, omitting
the base revision that pins *which* weights were converted.

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
