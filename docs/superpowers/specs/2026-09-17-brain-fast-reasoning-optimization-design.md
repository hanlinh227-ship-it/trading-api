# Brain Fast-Reasoning Optimization — Design

Status: **DESIGN ONLY**. Nothing here is implemented. Authority unchanged:
`GITHUB_BRAIN_V4` is the Brain, `task_router` routes, the Adaptive Model Mesh
selects, Open Model Universe governs admission, the local runtime executes.
This document proposes no new component that holds any of those.

## 0. The finding that shapes everything else

The architecture for fast reasoning is **already built**. What is missing is
**measured evidence to feed it**.

Every mechanism the optimization brief asks for exists in some form:

| Asked for | Already exists as |
|---|---|
| FAST / SMART / DEEP modes | `stable/budgets.yaml` + `stable/runtime.yaml` profiles **FAST / STANDARD / DEEP** |
| confidence escalation | `runtime.yaml: adaptive.may_escalate: [FAST_TO_STANDARD, STANDARD_TO_DEEP]` |
| two-stage model routing | `model_mesh`: `eligible_free_candidate` → capability floor → `score_candidate` |
| routing utility formula | `domain_capabilities.yaml: scoring` (capability_fit .5, measured_quality .25, reputation .12, quota .08, latency .05) |
| precomputed capability index | `model_mesh/active.json`, compiled by `compile_model_mesh_active_index` |
| HOT/WARM/COLD residency | `local_runtime/`: `lifecycle.py`, `residency.py`, `scheduler.py`, `cache.py` |
| context minimization | `budgets.yaml: max_context_tokens` 2500 / 7000 / 16000, `index_tiers` |
| concurrency ceiling | `budgets.yaml: hard_limits.max_parallel_tasks: 4`, STANDARD 2 / DEEP 4 |
| parallelism policy | `max_parallel_nodes` per profile |
| early exit | **absent** |
| measured latency/quality feeding selection | **absent — this is the bottleneck** |

So the honest recommendation is the opposite of building a performance layer:
**do not add one.** The brief's "SMART" is the existing STANDARD, and
introducing a third vocabulary beside FAST/STANDARD/DEEP would create exactly
the duplication §24 warns against. Everything below extends what is there.

## 1. Current architecture map

```
USER / EVENT / IDLE OBJECTIVE
  → GITHUB_BRAIN_V4                     (authority)
  → task_router          stable/router.yaml         domain + primary skill
  → profile selection    stable/runtime.yaml        FAST | STANDARD | DEEP
  → budget envelope      stable/budgets.yaml        context/tool/parallel caps
  → Task Graph Builder                              bounded decomposition
  → AI Legion role       control_plane/specialists.yaml
  → Adaptive Model Mesh  tools/model_mesh.py        filter → floor → score
  → runtime              local_runtime/             residency + llama.cpp
  → verifier             control_plane/verifier.py
  → evidence synthesis   control_plane/e2e.py
  → Brain output
```

## 2. Current bottlenecks — measured, not assumed

All figures below are from runs committed in this branch
(`CHECKPOINTS/evidence/`), on this host, Qwen3-0.6B-Q8_0, llama-cpp-python 0.3.35.

**B1. Cold load does *not* dominate — corrected.** An earlier version of this
section claimed cold load was ~80% of first-response latency, from figures of
2756–3363 ms load against 702–767 ms inference. Those loads were **not measured
against a cold page cache**, so they were partly re-reading memory and partly
contention. With `/proc/sys/vm/drop_caches` dropped before every load
(`CHECKPOINTS/evidence/RESIDENCY_LATENCY_PROFILE.json`), across all four
admitted models:

| Model | size | cold load | warm inference | residency saving | peak RAM |
|---|---|---|---|---|---|
| Qwen3-0.6B-Q8_0 | 609 MB | 942 ms | 665 ms | 942 ms | 1829 MB |
| Granite-3.3-2B-Q4_K_M | 1473 MB | 836 ms | 3250 ms | 981 ms | 3317 MB |
| Qwen3-1.7B-Q8_0 | 1749 MB | 1387 ms | 1764 ms | 1508 ms | 4237 MB |
| Qwen3-4B-Q4_K_M | 2381 MB | 1588 ms | 5066 ms | 1859 ms | 5476 MB |

The conclusion reverses with model size:

* on the **smallest** model, load is 59% of first response — the old claim, in
  weakened form;
* on the **strongest** model, the one the mesh now selects and the baseline is
  frozen against, **inference dominates 3:1** (5066 ms against 1588 ms). Load is
  24% of first response.

So "fix residency first" is right for a small hot worker and wrong for the model
that actually answers hard requests. Residency still buys 0.9–1.9 s per request
and is worth having, but it is no longer the largest lever; **inference time on
the selected model is**, and that is a quantization and token-budget question,
not a caching one.

The earlier figures are left described rather than deleted because the mistake
is instructive: a latency measurement that does not control the page cache
measures what was read last. Granite first profiled at a 618 ms "cold" load
against Qwen3-1.7B's 4212 ms for a *larger* file — a cache artefact that looked
exactly like a property of the model.

**B1b. Not everything can be resident.** The four admitted models need
1829 + 3317 + 4237 + 5476 = 14.9 GB against 16.1 GB of host RAM. Keeping them
all hot would leave ~1 GB for everything else, so HOT must stay at one or two
models and the choice is a real trade: the most capable model is also the most
expensive to hold and the slowest to answer.

**B2. The routing utility is fed vendor claims, not measurements.**
`score_candidate` weights `measured_quality` at 0.25, yet in `active.json`
8 of 10 models' `text_reasoning` scores (0.70–0.85) cite **a documentation
URL** as their evidence. A vendor's own docs are a claim. Meanwhile
`latency_ema_ms` and `success_rate_ema` are unpopulated, so `latency_efficiency`
(weight 0.05) contributes 0 and `reputation` falls to its neutral default.

In effect **capability_fit alone decides**, on numbers nobody measured. The
formula is sound; its inputs are not. After Wave 0 the local model is the only
candidate in the system whose score (0.75) is a count of verified runs — and it
now competes against self-reported 0.85s. *Measured fact currently loses to
marketing.*

**B3. Escalation is declared but has no trigger.** `runtime.yaml` lists
signals — `risk, task_complexity, freshness_requirement, tool_requirement,
prior_route_eval, verification_need` — and permits FAST→STANDARD→DEEP. Nothing
computes any of them, so profile choice is static per request shape.

**B4. No early exit exists.** Nothing stops work once the answer is adequate.

**B5. TTFT is not measurable.** `LlamaCppPythonBackend.execute` returns a
completed `Llama(...)` call. There is no streaming path, so perception latency
cannot be separated from completion latency at all. §17 of the brief cannot be
evaluated until this exists.

**B6. The capability index is empty.** `compile_model_mesh_active_index`
reports `entries=7 verified=0`. Routing cannot consume precomputed results that
were never populated with verified data.

## 3. Existing components reused (nothing new competes with these)

`stable/budgets.yaml` · `stable/runtime.yaml` · `stable/router.yaml` ·
`stable/context.yaml` · `stable/retrieval.yaml` · `stable/memory.yaml` ·
`tools/model_mesh.py` · `model_mesh/domain_capabilities.yaml` ·
`model_mesh/active.json` · `control_plane/benchmark.py` ·
`control_plane/verifier.py` · `local_runtime/scheduler.py` ·
`local_runtime/residency.py` · `local_runtime/cache.py` ·
`local_runtime/benchmark.py` · `local_runtime/wave0_baseline.py`.

## 4. FAST / SMART / DEEP execution policy

**Proposal: keep the three existing profiles unchanged and do not rename them.**
"SMART" maps to STANDARD. The budgets already encode the intended behaviour
(FAST: 1 skill, 0 tools, 0 supporting skills, HOT index only, no planner, no
maker-checker, 2500 context tokens). No change is proposed to any budget number
without a benchmark showing it is wrong.

The one addition: a profile must also carry a **residency requirement**, because
today a FAST request can land on a cold model and pay 2.8 s that the 2500-token
budget was designed to avoid. Proposed, as a new key in the existing profile
blocks rather than a new file:

| Profile | `requires_resident` | Behaviour on a cold model |
|---|---|---|
| FAST | `true` | do not select it; prefer a resident candidate, else escalate to STANDARD |
| STANDARD | `prefer` | may wake, counted against the latency budget |
| DEEP | `false` | may wake and may acquire |

This makes the measured 2.8 s load a **routing input** rather than an invisible
cost, and it is the change with the largest expected effect.

## 5. Confidence escalation

Implement the triggers for the signals `runtime.yaml` already declares. Nothing
new decides the profile — `task_router` still does; escalation only moves along
the existing `may_escalate` edges.

| Signal | Computable from | Escalates |
|---|---|---|
| verifier disagreement | `control_plane/verifier.py` result | STANDARD → DEEP |
| verifier failure | same | re-run at DEEP once |
| tool/runtime failure | `resilience.py: FailureKind` | FAST → STANDARD |
| capability margin | `score - hard_capability_min_score` below a threshold | FAST → STANDARD |
| no resident candidate | scheduler placement | FAST → STANDARD |
| unfamiliar domain | router matched only the fallback skill | FAST → STANDARD |

Explicitly **not** a signal: the availability of more models. Escalation is
bounded by `hard_limits.max_replans: 3`, which already exists.

## 6. Early exit

The missing mechanism. Proposed as a check between existing stages, not a new
stage:

Stop and return when **all** hold: the verifier passed, no unresolved material
conflict (`context.yaml` already defines this), and the profile's own budget has
not been exhausted. Do not run a checker whose result cannot change the answer;
do not request a second opinion once the first is verified.

Anti-goal: early exit must never skip a verifier for a high-risk class. The
`may_not_override` list (security, authority, permission ceiling, trading risk
controls) applies unchanged.

## 7–8. Context and retrieval budget

Already specified in `budgets.yaml` (`max_context_tokens`, `max_index_hits`,
`max_retrieval_stages`, `index_tiers`) and `retrieval.yaml`. **No change
proposed.** The brief's evidence-packet shape (claim / source / freshness /
authority / excerpt / conflict status) matches `stable/evidence.yaml`; it should
be reused rather than re-specified.

## 9. Model residency

Reuse `lifecycle.py` states. Proposed policy, grounded in the measurement that
one resident 0.6B model costs ~1.83 GB:

| Tier | Contents | Justification |
|---|---|---|
| HOT | ≤1 model while only one is admitted | 2.8 s saved per FAST request; 1.83 GB measured |
| WARM | admitted models with capability evidence, not resident | wake on demand |
| COLD | admitted, artifact cached, not loaded | `LOAD_FROM_CACHE`, 15 s planned |
| ARCHIVED | superseded or redundant | evictable per `cache.py` |

Promotion to HOT must require measured evidence — RAM headroom from
`detect_resources()` and a capability score from `capability_evidence`. No
model becomes HOT because it is the only one.

## 10–11. Candidate filtering and the capability index

Two-stage filtering already exists and needs no redesign. The work is to make
stage 2 meaningful:

1. **Populate `active.json` from verified evidence only.** Extend the Wave 0
   rule already enforced in `validate_open_model_universe.py` — a capability
   score above zero requires a measurement bound to the artifact digest — to the
   mesh's active index. A documentation URL is not a measurement.
2. **Mark unmeasured scores as unmeasured** rather than silently comparable.
   `as_mesh_candidate` already distinguishes `measured:<suite>@<version>+<hash>`
   from `registry_declared` and sets `supported: "unknown"` without evidence;
   the index should carry the same distinction.
3. **Populate `latency_ema_ms` and `success_rate_ema`** from execution evidence
   that `EvidenceRecorder` already produces, so the two zero-contribution terms
   start contributing.

Until (1) lands, ranking a measured 0.75 against a self-reported 0.85 is worse
than not ranking at all, because it systematically demotes the only candidate
anyone has actually tested.

## 12. Parallelism policy

Unchanged: STANDARD ≤2, DEEP ≤4, `max_parallel_tasks: 4`,
`provider_voting: forbidden`. Parallelism is for independent I/O (retrieval,
tests, repo checks), not for duplicate generation. Same-family replicas count as
availability redundancy, not reasoning diversity, and should not occupy two
checker slots.

## 13. Background learning

Benchmarking, index rebuilds and discovery run outside the interactive path and
consume precomputed results at request time. `local_runtime_wave0.py` and
`local_runtime_baseline.py` are already batch tools of exactly this shape.
Background work must be preemptible by user requests.

## 14. Failure and fallback

Reuse `resilience.py` (`CircuitBreaker`, `RetryPolicy`, `classify_exception`).
Retry only failure kinds where a retry can succeed; never retry a
deterministic refusal. No paid fallback, under any escalation.

## 15. Benchmark plan

Nothing in §4–§11 should land without a measurement, and the harness for this
already exists (`local_runtime/benchmark.py`, frozen suites, raw-generation
evidence). Per the brief's matrix, and per class:

| Measure | Source |
|---|---|
| QUALITY | frozen suite score, verified count |
| TTFT | **needs B5 fixed first** |
| TOTAL_LATENCY | `EvidenceRecorder` |
| RAM / VRAM | `PeakSampler`, `detect_resources` |
| MODEL_CALLS / TOOL_CALLS / CONTEXT_TOKENS | budget instrumentation |
| ERROR_RATE | wave report failures |

Acceptance thresholds are deliberately **not** proposed here. `budgets.yaml`
already asserts `fast_p95_ms_max: 25` for the gateway; local-inference
thresholds should be set from the FAST/STANDARD/DEEP comparison once it has been
run, not guessed now.

## 16. Migration plan (smallest first, each independently revertible)

1. **Populate the capability index from verified evidence only.** Data change;
   largest correctness gain; no code path moves.
2. **Add `requires_resident` to the existing profile blocks.** Config change
   addressing the measured 2.8 s.
3. **Implement early exit** as a check between existing stages.
4. **Implement escalation triggers** for signals already declared.
5. **Add a streaming path** to the backend, unblocking TTFT.
6. **Feed `latency_ema_ms` / `success_rate_ema`** from execution evidence.

Steps 1–4 need no new module. Step 5 extends `backends/llama_cpp_python.py`.

## 17. Conflict audit

| Risk | Verdict |
|---|---|
| second router | **avoided** — escalation moves along existing edges; `task_router` still routes |
| second modes system | **avoided** — FAST/STANDARD/DEEP reused; "SMART" is STANDARD |
| second model registry | **avoided** — Open Model Universe stays the registry |
| second scheduler | **avoided** — `scheduler.py` reused; residency becomes a routing *input* |
| second evidence engine | **avoided** — `EvidenceRecorder` and `stable/evidence.yaml` reused |
| second budget file | **avoided** — `budgets.yaml` is single source of truth and says so |
| capability score inflation | **guarded** — extend the existing digest-bound evidence rule |

One live conflict found: the Open Model Universe now requires measured,
digest-bound evidence for a non-zero capability score, while the mesh's
`active.json` accepts a documentation URL. Two standards for the same number.
Resolution is §10 item 1 — raise the index to the registry's rule, never lower
the registry to the index's.

## 18. Rollback

Steps 1, 2 and 6 are data/config and revert by reverting the file. Steps 3–5 sit
behind the profile blocks and revert with them; the golden E2E gate
(`control_plane/e2e.py`) and the Wave 0 baseline are the regression net, since
both fail closed on evidence that stops being real.

## 19. Expected effect — and its honest bound

| Change | Expected | Confidence |
|---|---|---|
| resident-aware FAST routing | removes 0.9–1.9 s from a cold request, by model | **high** — measured cold-cache |
| smaller model for FAST | 665 ms vs 5066 ms inference, at 0.75 vs 0.92 capability | **high** — measured |
| early exit | removes one verifier/model call on already-verified answers | medium |
| verified capability index | better *correctness* of selection; latency effect unknown | high on correctness |
| streaming | large perceived improvement; no change to total latency | medium |

No quality improvement is claimed for any of them. §22's guardrail cuts both
ways: these are latency and correctness-of-selection changes, and the frozen
suites exist to catch it if reasoning quality drops. The only thing that has
raised measured quality so far is a better model, which is Wave 1's job.
