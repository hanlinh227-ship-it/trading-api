# Claude Personal AI Runtime — Handoff

**Lane:** Claude Code, implementation-heavy runtime lane
**Project:** Open Model Universe / Personal AI Federation
**Updated:** 2026-09-17

---

## Position

| Field | Value |
|---|---|
| Repository | `hanlinh227-ship-it/trading-api` |
| Branch | `claude/magical-euler-uu98r8` |
| HEAD SHA | `e899887a52f3cbead5b94bd7fbfb2c52ddfcda2a` |
| Base main SHA | `c5ad9112de60223ef9e1175bb5bcc1fcdfdf163f` |
| PR number | none opened yet — not requested |
| Rollback point | `c5ad9112de60223ef9e1175bb5bcc1fcdfdf163f` (branch is additive; deleting `AI_SKILL_LIBRARY/v4/local_runtime/` and the six `test_local_runtime_*.py` files restores main exactly) |

Canonical state read at session start: `AI_SKILL_LIBRARY/checkpoint.json`
(`GITHUB_BRAIN_V4`, 4.0.0, latest closure
`CHECKPOINTS/BRAIN_EXPANSION_BROWSER_RUNTIME_4_15_0_CLOSURE_2026-09-17.md`).
`CHECKPOINTS/OPEN_MODEL_UNIVERSE_WORK_HANDOFF_LATEST.md` **does not exist** —
the research lane has not published a handoff yet, so no integration contract
from Work was available to build against. Branch was cut from `origin/main` at
the SHA above, which is the merge of PR #425.

---

## Overlap / conflict map

Nothing in this lane touches a file the research lane is populating.

| Area | Owner | This lane's contact |
|---|---|---|
| `AI_SKILL_LIBRARY/v4/model_mesh/*` (providers, active, discovery, catalogs) | ChatGPT Work | **read-only, untouched** |
| `AI_SKILL_LIBRARY/v4/legion/*`, `evergreen/*`, `learning/*` | existing Brain | untouched |
| `AI_SKILL_LIBRARY/checkpoint.json`, `v4/stable/*` | canonical Brain | untouched |
| `AI_SKILL_LIBRARY/v4/local_runtime/*` | **Claude (this lane)** | new package |
| `AI_SKILL_LIBRARY/tests/test_local_runtime_*.py` | **Claude (this lane)** | new tests |

**Shared files touched: none.** No registry, catalog, policy or checkpoint file
was modified. A test asserts the canonical checkpoint carries no reference to
this plane, so the stable brain keeps working with the whole package deleted.

One standing tension to flag, not a conflict: the canonical
`AI_SKILL_LIBRARY/runtime/cloud_runtime.yaml` declares
`local_install_required: false` / `local_cli_execution: false` for the stable
request path, while this project is local-first. Resolved by keeping this plane
**non-authoritative and opt-in** — it is contracts and decision logic, activates
no runtime (`ADAPTER_TARGETS` is all `activated: False`), and is not resolvable
from the checkpoint. If the plane is ever to run in the stable path, that policy
is the file to amend, and it belongs to the canonical Brain, not to this lane.

---

## Completed workstreams

| § | Workstream | Module | State |
|---|---|---|---|
| 3 / A | Model runtime lifecycle | `lifecycle.py` | complete |
| 4 / B | Auto wake / sleep | `scheduler.py` | complete |
| 5 / C | Compute resource registry | `resources.py` | complete |
| 6 / D | Hardware-aware scheduler | `scheduler.py` | complete |
| 7 / E | JIT model acquisition | `acquisition.py` | complete |
| 8 / F | Cache manager | `cache.py` | complete |
| 9 / G | Runtime abstraction | `runtime.py` | contracts + probes + negotiation complete; **no adapter activated** |
| 10 | Capability negotiation | `runtime.py` | complete |
| 11 | Priority queue P0–P5 | `scheduler.py` | admission classes + preemptibility complete |
| 12 | Circuit breaker / failover | `resilience.py` | complete |
| 13 | Multi-worker contract | `workers.py` | registration lifecycle + attestation complete |
| 14 | Cross-machine preparation | `workers.py` | endpoint-addressed contracts; **transport not implemented** |
| 16 | Authority invariants | `federation.py` + tests | asserted by test |

### Files changed

All additions, under `AI_SKILL_LIBRARY/`:

```
v4/local_runtime/__init__.py        public surface
v4/local_runtime/lifecycle.py       16-state machine, transition graph, audit trail
v4/local_runtime/resources.py       cross-OS compute snapshot, watermarks
v4/local_runtime/scheduler.py       placement, wake/sleep, priority admission
v4/local_runtime/acquisition.py     pinned-revision download, resume, checksum, atomic finalize
v4/local_runtime/cache.py           scored eviction, protected kinds
v4/local_runtime/resilience.py      failure classification, circuit breaker, retry/failover
v4/local_runtime/runtime.py         adapter ABC, capability negotiation, RuntimeMesh
v4/local_runtime/workers.py         worker states, attestation, eligibility
v4/local_runtime/federation.py      serve() entry point and containment boundary

tests/test_local_runtime_lifecycle.py     19
tests/test_local_runtime_resources.py     18
tests/test_local_runtime_scheduler.py     36
tests/test_local_runtime_acquisition.py   22
tests/test_local_runtime_cache.py         21
tests/test_local_runtime_resilience.py    21
tests/test_local_runtime_runtime.py       25
tests/test_local_runtime_workers.py       30
tests/test_local_runtime_federation.py    18
```

---

## Tests

```
python -m unittest discover -s AI_SKILL_LIBRARY/tests -p "test_local_runtime_*.py"
  -> 210 passed

python -m unittest discover -s AI_SKILL_LIBRARY/tests -p "test_*.py"
  -> 832 passed, 3 skipped, 0 failed
```

CI picks these up automatically: `AI_SKILL_LIBRARY/v4/tools/ci_validate.py`
discovers `AI_SKILL_LIBRARY/tests`, which `.github/workflows/ai-skill-library-ci.yml`
runs on every push and PR touching `AI_SKILL_LIBRARY/**`. Dependencies are the
existing `AI_SKILL_LIBRARY/requirements.txt`; this lane adds none — it is
stdlib only.

Every test from the §15 required list is covered:

| Required test | Where |
|---|---|
| valid model lifecycle | `test_canonical_cold_start_path` |
| invalid transition rejection | `InvalidTransitionTests` (8 tests) |
| auto wake | `test_a_sleeping_model_is_woken_for_the_task` |
| auto sleep | `SleepPolicyTests` (6 tests) |
| warm model preference | `test_fast_tier_takes_a_warm_model_over_a_better_cold_one` |
| RAM overcommit prevention | `test_ram_overcommit_is_refused`, `test_reserve_headroom_is_not_spendable` |
| VRAM overcommit prevention | `test_vram_overcommit_is_refused` |
| disk pressure | `DiskPressureTests`, `test_disk_pressure_blocks_acquisition_only` |
| corrupted download | `test_corruption_of_a_finalised_artifact_is_detected` |
| checksum mismatch | `test_checksum_mismatch_fails_and_cleans_up` |
| interrupted download | `test_interrupted_download_resumes_from_the_offset` |
| runtime crash | `test_a_runtime_crash_is_an_outcome_not_an_exception` |
| worker disappearance | `test_a_worker_that_disappears_goes_offline` |
| no internet | `test_no_internet_is_a_status_not_an_exception` |
| all workers unavailable | `test_all_workers_unavailable_is_an_empty_result` |
| no eligible FREE_ONLY worker | `test_no_eligible_free_only_candidate_never_falls_back_to_paid` |
| priority scheduling | `PriorityQueueTests`, `WatermarkAdmissionTests` |
| background yields to interactive | `BackgroundYieldTests` (3 tests) |
| stable Brain survives runtime failure | `ContainmentTests`, `test_the_stable_brain_does_not_depend_on_this_plane` |

---

## Design decisions worth carrying forward

1. **Unknown is never zero.** An unreadable RAM/VRAM/disk figure is `None` and
   named in `unknown_dimensions`. Treating it as 0 refuses every placement;
   treating it as plentiful invites an OOM. The scheduler is told it does not
   know and refuses to prove a fit it cannot prove.
2. **Resident vs. allocating.** Only `WAKE`/`LOAD_FROM_CACHE`/`ACQUIRE` are
   fit-checked. A `RUNNING` model already holds its memory; refusing it for
   lack of free memory would evict work to make room for itself.
3. **Failure kind drives the response.** Timeout → retry here; OOM/disk-full →
   open the breaker at once (it reproduces exactly); quota → failover only.
   `UNKNOWN` stays `UNKNOWN` rather than being guessed into a policy.
4. **Transport failure keeps the partial; checksum failure deletes it.**
   Resuming corrupt bytes only rebuilds the corruption.
5. **Observation beats the registry.** A model advertised at 128k that loaded at
   32k negotiates against 32k, and the contradiction is recorded in
   `downgrades` rather than smoothed over.
6. **Authority is structural, not conventional.** `routing_authority` and
   friends are class attributes fixed at `False`, not constructor arguments, so
   `WorkerRecord(..., routing_authority=True)` is a `TypeError`.
7. **`serve()` is a containment boundary.** Every module is written not to
   raise, but that is a claim about today's code. The wrapper makes it
   structural: a future bug anywhere in the plane returns `degraded=True`, not a
   traceback climbing into the router.

---

## Blockers

**Runtime blockers:** none. The lane is stdlib-only and fully tested.

**Dependency blockers:** none for the work completed. Activating any adapter in
`ADAPTER_TARGETS` needs its runtime installed and proven in a real environment;
that is deliberately out of scope until an activation lane exists (the Brain
Expansion activation jobs in `ai-skill-library-ci.yml` are the pattern to copy).

**Open decision for the canonical Brain, not this lane:**
`AI_SKILL_LIBRARY/runtime/cloud_runtime.yaml` currently forbids local execution
in the stable request path. Local-first execution cannot be switched on without
amending that policy. Nothing here depends on the answer.

---

## Integration points expected from ChatGPT Work

This lane consumes, and does not produce, the following. Each has a typed shape
already in the code, so wiring is a translation step rather than a redesign.

| Needed from Work | Consumed as | Where |
|---|---|---|
| Open Model Universe registry entries (id, ram/vram/disk, runtime, context, capabilities, quality, specializations, licence/approval) | `scheduler.ModelProfile` | `scheduler.py` |
| Per-model zero-cost entitlement and privacy ceiling | `ModelProfile.zero_cost`, `.max_privacy` | `scheduler.py` |
| Official source metadata: URI, **pinned revision**, size, sha256 | `acquisition.AcquisitionRequest` | `acquisition.py` |
| Registry capability claims for negotiation | `runtime.RegistryClaim` | `runtime.py` |
| Champion/challenger + benchmark quality scores | `ModelProfile.quality`, `CacheEntry.quality` | `scheduler.py`, `cache.py` |
| Family grouping / replacement availability | `CacheEntry.replacement_available`, `.specialization_score` | `cache.py` |

Note for Work: acquisition **refuses** `main`, `master`, `latest`, `head`,
`trunk`, `dev` and `stable` as revisions, and refuses a model with no declared
size or sha256. Registry entries without a pinned revision and a checksum cannot
be acquired at all.

---

## Next exact task

Wire the plane to real registry data behind a compile step, without giving it
authority: a `v4/tools/local_runtime_plan.py` that reads the Model Mesh's
existing `active.json` / `providers.yaml`, projects each entry into a
`ModelProfile`, runs `detect_resources()` on the host, and emits a placement
plan as JSON evidence — read-only, no execution, no writes to any Work-owned
file. That closes the loop from registry to placement decision and produces the
first real evidence artifact for this lane.

### Next exact command

```bash
git fetch origin && git checkout claude/magical-euler-uu98r8
python -m unittest discover -s AI_SKILL_LIBRARY/tests -p "test_local_runtime_*.py"
# then TDD the new tool:
#   AI_SKILL_LIBRARY/tests/test_local_runtime_plan_tool.py
#   AI_SKILL_LIBRARY/v4/tools/local_runtime_plan.py
```

Do **not** modify `AI_SKILL_LIBRARY/v4/model_mesh/*` to make the projection fit.
If a field is missing, record the gap here and project a conservative default.
