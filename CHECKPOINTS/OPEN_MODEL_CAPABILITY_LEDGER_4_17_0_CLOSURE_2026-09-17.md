# Open Model Capability Ledger 4.17.0 — Closure

Date: 2026-09-17
Architecture: GITHUB_BRAIN_V4
Status: PACKAGED / VALIDATED LOCALLY / NOT YET PRODUCTION-PROVEN
Target release: `4.17.0`
Previous known-good release: `4.14.0`

## Scope

Two releases were cut in this lane and both seal the same file:
`AI_SKILL_LIBRARY/v4/model_mesh/capability_evidence.json`, the canonical Model
Mesh capability ledger. It is sealed by the active manifest, so putting a row
into it is a governed act rather than a file edit, which is exactly why the
tooling refuses to write it as a side effect of benchmarking.

| Release | What it seals |
| --- | --- |
| `4.16.0` | the ledger populated from seven existing measurements |
| `4.17.0` | the eighth row, Qwen3-8B, measured after its Wave 3 admission |

## Why the ledger was empty

`compile_model_mesh_active_index` reported `verified=0` because the ledger held
`records: []`. The measurements had existed for some time:
`local_runtime_wave0.py` measures a model and *prints* a ledger row rather than
writing one, deliberately — a benchmark harness that can edit the registry it
benchmarks for is one bug away from promoting its own model. Seven such rows had
been sitting unread in `CHECKPOINTS/evidence/WAVE0_CAPABILITY_*.json`.

`compile_capability_ledger.py` is the other half of that split. It measures
nothing and invents nothing; it collects rows real runs produced and refuses on
any it cannot back against the Open Model Universe registry — unknown model,
digest mismatch between the row and the registry's artifact, a score disagreeing
with the governance plane, or a missing benchmark id. It refuses rather than
dropping, so a silent partial ledger is not a reachable state.

Eight rows, one per admitted model, `text_reasoning` 0.583333 to 1.0. BitNet and
Ministral have none: their runs are REFUSED because llama.cpp cannot load the
formats, and a quarantined model carrying a capability score would be a score
for an artifact nothing has ever executed.

## What is *not* closed

The compiled active index still reports `verified=0`, and that is correct rather
than outstanding. Its seven entries are remote free-tier providers and not one
of them has ever been measured — every capability score they carry cites a
vendor documentation page. All eight ledger rows are `local_runtime`
measurements. That gap closes when somebody benchmarks a hosted provider, not by
writing a number.

## Release state

Neither release is `known_good`. Both are packaged and locally validated:
`CI_VALIDATE=PASS failures=0`, `OPEN_MODEL_UNIVERSE_VALIDATE=PASS errors=0`,
`AI_CORE_RELEASE=PASS passed=9/9`. Neither has been proven by a production
deployment, so `promotion.validated` is false on both and rollback resolves to
`4.14.0`, the nearest known-good predecessor.

That is three unvalidated releases stacked at the tip (`4.15.0`, `4.16.0`,
`4.17.0`). It is worth naming rather than leaving to be discovered: the rollback
distance from the active pointer is now three releases, and closing it needs a
production gate run, not another cut.

## Boundaries unchanged

`task_router` remains the only routing authority. The ledger declares
`routing_authority: false` and `reasoning_authority: false`, and its schema pins
both. No Trading file was touched. No admission, security or runtime gate was
weakened; one was added — `_admission_refusals` now refuses a registry row that
carries both a passing malware scan and an unsuperseded operator risk
acceptance.

Previous closure record:
`CHECKPOINTS/BRAIN_EXPANSION_BROWSER_RUNTIME_4_15_0_CLOSURE_2026-09-17.md`.
