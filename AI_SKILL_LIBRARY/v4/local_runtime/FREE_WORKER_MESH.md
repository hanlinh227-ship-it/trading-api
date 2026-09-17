# Free Worker Mesh — the multi-wave execution fabric

**Status:** canonical. **Scope:** execution capacity only.

This is the contract every executor joins under — the container this runtime
lives in, an operator's MacBook, a CI runner, a hosted inference catalog, a GPU
box that does not exist yet. It exists so that adding an executor is a
registration rather than a change to anything that selects.

It is reusable for every future wave. Wave 4 and beyond add capability
requirements, models, and provider adapters where genuinely needed. They do not
add orchestration authority, and they do not require this document to be
rewritten.

## The one rule

**The mesh is capacity, not authority.**

| Authority | Owner | Not the mesh |
|---|---|---|
| Routing | `task_router` | The mesh never sees a user request |
| Specialist roles | AI Legion | The mesh never assigns one |
| Model selection | Model Mesh | The mesh never prefers a model |
| Admission | Open Model Universe | The mesh never admits an artifact |
| Placement policy | runtime scheduler | The mesh answers, it does not decide |
| Evidence | existing evidence authority | The mesh reports; it does not seal |

`routing_authority`, `reasoning_authority`, `memory_authority`,
`model_selection_authority`, `admission_authority` and `evidence_authority` are
class attributes fixed at `False` on `WorkerRecord`, `ProviderRecord`,
`WorkerRegistry`, `ProviderRegistry` and `FreeWorkerMesh`. They are not
constructor arguments, so passing one is a `TypeError`. A worker contributes
capacity; it does not get a vote on where work goes.

The flow is unchanged by anything here:

```
USER → GITHUB_BRAIN_V4 → task_router → AI Legion → Model Mesh
     → runtime scheduler → Free Worker Mesh → worker/provider
     → inference → verifier → evidence → synthesis
```

## What makes it wave-independent

**A capability is a string.** `coding` today, `vision` or `ocr` or
`audio_understanding` later. A requirement carrying a new tag matches against a
worker's measured capability set, and nothing in the router, the scheduler or
the Brain has to learn about it.

Two sets, never one:

- `declared_capabilities` — what a worker says it could do. **Advertising.**
- `measured_capabilities` — what a benchmark on this fleet established. **The
  only set matched against a requirement.**

A capability may be *named* before it is measured. It may not *qualify* anything
before it is measured. That is the whole difference between a taxonomy and a
claim, and `test_a_declared_capability_does_not_qualify_a_worker` fails if the
rule is removed.

`WorkerClass.FUTURE_PROVIDER` exists for the same reason: an executor type
nobody has thought of registers under it and is matched on declared resources
and measured capabilities like any other.

## Two execution modes, never merged

| Mode | What runs | What a measurement belongs to |
|---|---|---|
| `EXACT_MODEL` | the artifact the Open Model Universe admitted, or the same model held by a provider | the requested model |
| `CAPABILITY_PROVIDER` | a **different** model supplying the capability | **the substitute**, never the requested model |

Every placement records `requested_model`, `executed_model`,
`ran_the_requested_model`, `provider`, `fallback_reason`. A capability fallback
is never reported as availability of the model that was asked for. A provider's
model has no artifact digest to bind evidence to, which is why this distinction
is structural rather than a matter of care.

A fallback is only taken when the caller sets `allow_capability_fallback`. The
default is off: silently substituting is how a benchmark ends up attributed to
the wrong model.

## Worker classes

Owned: `EPHEMERAL_LOCAL`, `PERSISTENT_LOCAL`, `OWNED_MAC`, `OWNED_WINDOWS`,
`OWNED_LINUX`, `OWNED_VPS`.
Remote: `REMOTE_CPU`, `REMOTE_GPU`, `REMOTE_EPHEMERAL`, `REMOTE_PERSISTENT`,
`JIT_REMOTE`.
Third party: `FREE_CLOUD_EPHEMERAL`, `CI_EPHEMERAL`, `SERVERLESS_INFERENCE`,
`MODEL_PROVIDER`, `FUTURE_PROVIDER`.

The class is descriptive metadata, not a permission tier — with one exception
below.

## Privacy outranks cost

A third-party worker **cannot attest above `INTERNAL`**, enforced at
`WorkerRegistry.attest()`. The ceiling comes from where the machine is, not from
what its operator promises, so the over-claiming record never exists to be read
wrongly later. A `CONFIDENTIAL` or higher payload is refused a hosted provider
outright, and the refusal says why rather than reporting the provider as merely
unavailable.

No cost saving changes this.

## Four things exclude a worker before capability is considered

Each means the job would not arrive:

1. **Stale lease** — the heartbeat is older than `lease_seconds`, so the machine
   may already be gone. A worker never seen is stale, not fresh: the cost of
   wrongly calling a live worker stale is a missed placement; the reverse is a
   job handed to a machine that left.
2. **Open circuit** — repeated failures, now in cooldown. Never a permanent
   removal: the breaker half-opens and lets a probe through, because one bad
   afternoon is not evidence a machine is gone.
3. **Exhausted quota** — `QUOTA_LIMITED`, deliberately not `DEGRADED`. Nothing
   is wrong with a worker that is out of free tier, and retrying it is a loop
   against a limit only the reset clears. `quota_remaining` of `None` means
   unmetered and is never read as exhausted.
4. **No spare capacity** — already carrying `max_concurrent_jobs`.

## Selection is fit, not config order

Cost is a **filter**, not a score: nothing paid, ever, without explicit human
approval. Among the zero-cost survivors the ordering is

1. owned hardware — private, unmetered, no third party sees the payload;
2. measured warm latency, with **unmeasured last** rather than first, because an
   unmeasured worker has not earned a position;
3. spare capacity.

No provider is hardcoded ahead of another. Suitability changes; the ordering is
recomputed from what is currently measured.

## Failure behaviour

```
preferred worker unavailable   → next compatible worker
no exact-model worker          → provider serving the same model (still EXACT_MODEL)
no exact-model path            → permitted capability provider (CAPABILITY_PROVIDER)
nothing                        → CAPABILITY_TEMPORARILY_UNAVAILABLE, with reasons
```

The last is a truthful state and the only permitted alternative to running
something. Inference is never fabricated.

## Artifacts and cache

Models are **not** owned by the mesh. The Open Model Universe governs identity
and admission; the Model Mesh selects; the runtime lifecycle loads. The mesh
arranges capacity for a decision already taken.

Per-worker caches, not one central store. `jit_cache.py` plans acquisition
before a byte is fetched: artifact + staging + headroom must fit, and eviction
may only ever remove something that can be got back. Never evicted: an artifact
in use, one whose only copy this is, one another worker depends on, or canonical
evidence — a benchmark deleted to make room is gone, and re-running it produces
a different run, not the same one.

## Evidence classes

Never mixed: `MEASURED`, `OBSERVED`, `ESTIMATED`, `DECLARED_BY_PROVIDER`. A
provider must not be marked `VERIFIED_AVAILABLE` on documentation alone — real
execution proof is required, and until then the truthful state is `DISCOVERED`,
`VERIFICATION_PENDING`, `AUTH_REQUIRED` or `HUMAN_CONNECTION_REQUIRED`.

## Scoped conclusions

A resource measurement is a fact about the machine it was taken on. This
container's ~16 GB of RAM is not operator hardware, not a GitHub limit, and not
a property of any model. A model that does not fit here is
`REMOTE_WORKER_REQUIRED` with the exact shortfall named — never "infeasible".
Historical measurements are preserved untouched; what changes is the scope of
the conclusion drawn from them.

## Enrolling a device

Register → attest → heartbeat. That is all. The proof round
`owned_device_joins_and_becomes_eligible` runs two placements with no code path
changed between them: the first finds nothing, the second finds the device.

Enrollment requires operator authorization. A local worker is not exposed
publicly by default, and a remote worker never receives unrestricted repository
credentials.

## Where the parts live

| Concern | File |
|---|---|
| Worker contract, registry, attestation, lease, quota | `workers.py` |
| Hosted providers, exact-vs-capability offerings | `providers.py` |
| One surface over both, breaker, fit ordering | `free_worker_mesh.py` |
| Where a model can run, and what to say when nowhere | `placement.py` |
| Acquisition and eviction planning | `jit_cache.py` |
| Retry, failover, circuit breaker | `resilience.py` |
| Recorded zero-cost paths and their verified facts | `../open_model_universe/free_execution_paths.yaml` |
| Invariant tests | `../../tests/test_free_worker_mesh.py` |
| Scenario + live proof | `../tools/free_worker_mesh_proof.py` |

## For a future session

Do not create a second Brain, router, Model Mesh, registry, scheduler,
lifecycle manager, admission authority or evidence authority. A new wave
declares capability requirements and, where genuinely needed, a provider
adapter. Everything else already exists here.
