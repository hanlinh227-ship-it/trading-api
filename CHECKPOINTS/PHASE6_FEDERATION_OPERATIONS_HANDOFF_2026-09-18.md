# Phase 6 — role-specialized 24/7 federation. Operational checkpoint, 2026-09-18

**Branch:** `claude/magical-euler-uu98r8` · **PR:** #442 (not merged) · **Trading:** not started

This is the single Phase 6 checkpoint. A future session should be able to answer
every operating question from this file and the evidence it names, without
redesigning anything.

## Six flags, and none of them is a synonym for another

| Flag | Value |
|---|---|
| `PHASE6_OPERATIONAL_CLOSED` | **true** |
| `24X7_FEDERATION_READY` | **true** |
| `ALL_ROLES_REDUNDANT` | **false** |
| `ALL_MODELS_EXACT` | **false** |
| `ALL_CAPABILITIES_COVERED` | **false** |
| `ALL_WORKERS_ONLINE` | true (one worker, and it is up) |

The federation is 24/7-ready **and** not redundant. Both are true at once: every
local role runs on one host, so there is exactly one independent local path, and
four roles are served by a provider's own model under its own name. A report
that gave the first flag and let a reader infer the rest would be the failure
this gate exists to prevent.

Read from `AI_SKILL_LIBRARY/v4/tools/phase6_closure_gate.py`; all eighteen Phase 6
exit criteria pass, each against a named drill round or a matrix property.

## What roles exist

Seventeen branches in `AI_SKILL_LIBRARY/v4/model_mesh/role_branches.yaml`.
Four branches from the brief were merged with the reason recorded, not dropped:
`GENERAL_FAST` and `HEAVY_REASONING` are tiers of `REASONING_BRANCH`'s escalation
ladder, `SYSTEMS_ENGINEERING` is `CODING_BRANCH` (same suite, same models, same
ranking), and `AUDIO` is `SPEECH_BRANCH` because the only audio capabilities with
a model behind them are STT and TTS.

A branch is a responsibility. It selects nothing, routes nothing, admits nothing,
and its authority flags are all false.

## Which model owns each role

Derived by `role_capability_matrix.py` from recorded runs on every invocation —
never authored, and it moves when a new measurement lands.

| Role | Criticality | Primary | Fallback | Health |
|---|---|---|---|---|
| REASONING | CRITICAL | Qwen3-4B | Qwen3-8B | AVAILABLE_PRIMARY |
| CODING | CRITICAL | **granite-4.2-3b** | Qwen3-4B | AVAILABLE_PRIMARY |
| VERIFICATION | CRITICAL | Qwen3-8B | Qwen3-4B | AVAILABLE_PRIMARY |
| PLANNING | HIGH | Qwen3-4B | Qwen3-8B | AVAILABLE_PRIMARY |
| TOOL_USE | HIGH | Qwen3-4B | Qwen3-8B | AVAILABLE_PRIMARY |
| RESEARCH | HIGH | Qwen3-4B | Qwen3-8B | AVAILABLE_PRIMARY |
| VIETNAMESE | HIGH | Qwen3-4B | Qwen3-8B | AVAILABLE_PRIMARY |
| MULTILINGUAL | NORMAL | Qwen3-8B | Qwen3-4B | AVAILABLE_PRIMARY |
| SCIENCE_TECH | NORMAL | Qwen3-4B | Qwen3-8B | AVAILABLE_PRIMARY |
| RETRIEVAL | HIGH | bge-m3 + bge-reranker-base | — | FALLBACK_ONLY |
| MEMORY | HIGH | bge-m3 | — | FALLBACK_ONLY |
| VISION | NORMAL | llava-1.5-7b | — | FALLBACK_ONLY |
| SPEECH | NORMAL | aura-1 + whisper-large-v3-turbo | — | FALLBACK_ONLY |
| DOCUMENT_OCR | NORMAL | — | — | **DEGRADED** |
| FINANCE_ANALYSIS | OPPORTUNISTIC | — | — | UNAVAILABLE |
| CREATIVE_MULTIMODAL | OPPORTUNISTIC | — | — | UNAVAILABLE |

**The coding primary is granite-4.2-3b, not Qwen3-8B.** Qwen3-8B scores 0.167 on
the engineering suite's coding items; the bigger model is not the better coder.
This is the single clearest reason the matrix is derived rather than written.

`DOCUMENT_OCR` is DEGRADED, not unavailable: `ocr` has a measured path and
`document_understanding` has none. Calling it either available or unavailable
would hide half of it.

`FINANCE_ANALYSIS` carries **no** trading, wallet, transfer, signing or order
authority, and no model gains one by being placed there.

## Which workers are online

One: `ephemeral-local-0`, this container, registered from measurement.
Off-host providers usable: `cloudflare_workers_ai`, `github_actions_ubuntu_latest`.

The paths file also records `ephemeral-local-0` as a LOCAL_PROCESS provider. That
is this host under another name and is flagged
`offers_independent_capacity: false`. Counting it as a provider made the host
look like a second machine, and would have let a role whose only real path is
Cloudflare keep claiming to be serviceable after Cloudflare went away. Drill H
now removes only the off-host provider and the four provider-only roles correctly
go BLOCKED.

## Which models are HOT / WARM / COLD

All eight local artifacts are on disk and none is loaded, so every one reads
**COLD** with no session running. Provider models read **SERVERLESS** and carry
no hotness score, because we hold no bytes for them and there is nothing to act
on.

HOT is earned, never assigned: observed demand plus role criticality, pushed down
by resident memory and by being cheap to load anyway. A 22 GB model with no
demand is not recommended HOT and a drill asserts it. **24/7 means the federation
stays serviceable, not that every model stays loaded.**

## What is degraded, blocked, or needs a human

- **DEGRADED:** `DOCUMENT_OCR_BRANCH` — `document_understanding` has no path.
- **UNAVAILABLE:** `FINANCE_ANALYSIS_BRANCH`, `CREATIVE_MULTIMODAL_BRANCH` — never
  measured on any model.
- **SINGLE_PATH_RISK on every local role** — one host. This auto-recovers only in
  the sense that the host coming back restores it; a second machine is the fix
  and it is an enrolment, not a code change.
- **CAPACITY_DEFICIT on the three CRITICAL roles** — the host advertises one job
  slot and a CRITICAL role targets two. It serves them one at a time. Healthy and
  capacity-deficient are both true and both reported.
- **Human-only:** enrolling a second worker; accepting the
  `llama-3.2-11b-vision` licence (would move five Wave 4 capabilities); nothing
  else.

## What auto-recovers

Proven in `FEDERATION_24X7_PROOF.json`, 22/22 rounds: stale heartbeat fails over,
a tripped breaker removes a path and probes back, an exhausted free quota is
bypassed rather than retried, a worker that rejoins becomes placeable with
nothing rewritten, a worker joining mid-flight needs no authority change, and a
CONFIDENTIAL request is refused rather than sent to a third-party worker.

Round V is inference, not state: a real request through `run_federated` — the
existing USER → task_router → Model Mesh → scheduler → worker → model chain —
asserting the answer, that routing authority was `task_router`, that selection
authority was `model_mesh`, that nothing resolved by vote, and that every model
which ran is one a role branch maps.

## Where the parts live

| Concern | File |
|---|---|
| Role taxonomy | `AI_SKILL_LIBRARY/v4/model_mesh/role_branches.yaml` |
| Role → model, derived | `AI_SKILL_LIBRARY/v4/tools/role_capability_matrix.py` |
| 24/7 operating view | `AI_SKILL_LIBRARY/v4/local_runtime/federation_ops.py` |
| Drills and the live round | `AI_SKILL_LIBRARY/v4/tools/federation_24x7_proof.py` |
| Closure flags | `AI_SKILL_LIBRARY/v4/tools/phase6_closure_gate.py` |
| Invariant tests | `AI_SKILL_LIBRARY/tests/test_federation_ops.py` |

## For a future session

Nothing here is a new authority. `FederationOps` is built from the existing
`WorkerRegistry`, `ProviderRegistry` and `FreeWorkerMesh` and reads them; its
authority flags are class attributes fixed False, so passing one is a `TypeError`.
Operational residency is **derived** from the residency tier, the physical
`ResidencyState` and the placement — not a tenth enum, because two sources of
truth for where a model is would leave the second one wrong within a week.

A new role needs one entry in `role_branches.yaml` and a measurement. It does not
need a new gate, registry, scheduler or vocabulary.

Trading remains out of scope. It is a later domain application on top of this
federation, not a capability of it.
