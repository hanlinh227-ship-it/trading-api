# Open Model Universe Phase A/B Design

## Goal

Add the canonical, authority-free metadata foundation for the Open Model Universe without activating, downloading, or running any model. This slice makes the later Personal AI runtime possible while preserving `task_router`, Model Mesh, Legion, Memory Continuity, Evergreen, and Stable release authority.

## Routed scope

- Profile: `DEEP`
- Domain: `engineering`
- Primary skill: `software_architecture`
- Supporting skills: `tdd`, `github`
- Base: `origin/main` at `affb99b9c3bbf17b674fc12807dec29a4ce8709e`

## Conflict map

| Existing subsystem | Reuse | Forbidden overlap |
| --- | --- | --- |
| `task_router` | Domain and primary-skill resolution | No model or runtime self-routing |
| Model Mesh | Selection after canonical routing | Registry cannot become routing or reasoning authority |
| Legion | Bounded worker coordination | No second orchestrator or unbounded worker tree |
| Memory Continuity | Existing candidate/writeback lifecycle | No direct stable-memory writes |
| Evergreen | Discovery, quarantine, promotion | No discovered model may jump directly to runtime |
| Harmonization | License, overlap, authority, security gates | No duplicate authority or silent conflict resolution |
| Brain Expansion | Optional runtime adapter pattern | No mandatory dependency on Stable request path |
| PR #425 | Browser runtime and release `4.15.0` candidate | This slice does not edit release/checkpoint/Browser Use files |

## Architecture

The new registry lives under `AI_SKILL_LIBRARY/v4/open_model_universe/` and is metadata only. A JSON Schema defines a registry envelope and complete model records, including family identity, variant identity, provenance, per-release licensing, capability scores, hardware/runtime compatibility, lifecycle state, health, and immutable `authority=false` declarations.

A small Python contract module owns lifecycle vocabulary and transition validation. A separate validator loads the registry, applies JSON Schema, enforces authority and zero-paid-token invariants, rejects direct discovery-to-runtime transitions, and checks family/variant identity uniqueness. Existing Model Mesh remains the only model/provider selector after `task_router` has routed the request.

The checked-in registry begins empty and valid. Population is Phase D because every model/release requires official-source and per-release license research; scale targets must never be met with fabricated metadata. The schema and validator are designed for 1000+ records and tests generate large in-memory registries to prove linear validation behavior without committing unverified models.

## Lifecycle contract

Canonical states are:

`DISCOVERED`, `QUARANTINED`, `REGISTERED`, `APPROVED`, `AVAILABLE`, `DOWNLOADING`, `CACHED`, `WARM`, `RUNNING`, `SLEEPING`, `DEGRADED`, `BROKEN`, `EVICTED`, `SUPERSEDED`, `RETIRED`, `BLOCKED`, and `QUARANTINED_UPDATE`.

Transitions are explicit. `DISCOVERED -> RUNNING` is forbidden. Runtime-bearing states require prior approval, but Phase A/B performs no runtime transition and adds no `enabled=true` flag.

## Zero-paid-token and authority boundaries

- Policy id is `OPEN_MODEL_ZERO_TOKEN_FIRST`.
- Default paid fallback is `NO_PAID_FALLBACK`.
- Every model record declares `authority: false`.
- The registry envelope declares routing, reasoning, permission, memory, project-truth, and final-answer authority as false.
- Registration never implies approval, availability, cache presence, or runtime activation.
- Secrets, credentials, private keys, tokens, and secret values are forbidden.

## Testing

Tests are written RED first and cover schema presence, valid empty registry, full lifecycle vocabulary, forbidden transitions, explicit authority boundaries, duplicate identities, secret-like data, paid fallback rejection, and 1000-record scale. The validator is then added to the canonical `ci_validate.py` entrypoint.

## Deferred dependency-ordered work

Phase C adds the supporting-repository capability registry. Phase D researches and populates official model families and variants. Later slices add harmonization, discovery, compute registry, lifecycle manager, JIT download/cache, federation scheduler, verifier, benchmarks, specialization, and unified ingress. None may bypass this registry's approval and transition gates.

