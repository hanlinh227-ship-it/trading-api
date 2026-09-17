# Personal AI Full Convergence Design

## Status and authority

This design continues the approved Open Model Universe / Personal AI Federation architecture. It does not introduce another Brain, router, provider registry, or runtime. `GITHUB_BRAIN_V4` and `task_router` remain the sole reasoning and routing authority. Model Mesh owns model selection. Open Model Universe owns model governance and admission. Claude's local runtime owns acquisition, lifecycle, scheduling, loading, inference, telemetry, runtime failover, and runtime adapters.

## Goal

Provide the non-runtime control-plane contracts required to drive a real admitted local model through B2 canonical inference, B3 golden end-to-end execution, B4 offline verification, Wave 0 benchmarking, baseline freeze, bounded multi-model selection, and controlled self-development as soon as Claude supplies real runtime evidence.

## Components

1. **Local candidate projection** converts only admission-cleared Open Model Universe records into generic `local_runtime` Model Mesh candidates. Unknown capabilities remain unknown. Immutable artifact identity is preserved; health, resource, and benchmark evidence are separate inputs.
2. **Canonical ingress** validates the ChatGPT-style request envelope, routes through `task_router`, and produces a selection request without selecting a model or widening privacy, permission, or FREE_ONLY policy.
3. **Verifier V1** dispatches task-specific deterministic checks for coding, math, structured output, research, Vietnamese, trading research, and creative constraints. Outputs are untrusted and majority voting is never truth.
4. **Golden E2E harness** composes ingress, router, Model Mesh selection, an injected Claude runtime boundary, verifier, synthesis, and lifecycle evidence. A run cannot pass unless runtime evidence proves a real artifact-backed inference.
5. **Wave 0 and baseline** define the existing 12-task composition, ingest immutable real-run evidence, retain failures, bind environment fingerprints, and freeze `PERSONAL_AI_BASELINE_001` only when every reproducibility and verifier gate passes.
6. **Multi-model federation V1** defines FAST/STANDARD/DEEP execution profiles, specialist contracts, selection request/result schemas, bounded fan-out, lineage-aware diversity, champion/challenger roles, resource-aware selection, and routing-quality metrics. It remains subordinate to `task_router`.
7. **Controlled self-development V1** defines the authorized state machine, protected branch restrictions, gate evidence, before/after scorecard, PR-only promotion, and rollback triggers. It never writes to canonical main or approves itself.

## Data flow

`ingress -> task_router -> bounded context -> Model Mesh -> admitted candidate -> Claude runtime boundary -> verifier -> Brain synthesis -> response`

The E2E harness accepts runtime evidence through a callable/protocol boundary. It neither downloads models nor implements runtime behavior. Runtime evidence must include immutable artifact identity, backend/runtime identity, timestamps, measured latency/resources, output, and success/failure state.

## Failure behavior

- Missing or unknown admission, identity, health, resource, benchmark, privacy, or zero-cost evidence fails closed at the relevant gate.
- No eligible model produces an explicit selection failure; ingress never hardcodes a fallback model.
- Fake, fixture-only, simulated, or incomplete runtime evidence cannot produce B2/B3 PASS.
- Verification failure retains raw run references and blocks synthesis promotion and baseline freeze.
- Any protected-dimension regression, authority violation, security regression, runtime instability, or missing rollback target blocks auto-development promotion.

## Testing

Each component is developed RED -> GREEN with focused `unittest` contracts. Regression includes Open Model Universe, Model Mesh, Brain authority, verifier, benchmark/baseline, federation, self-development, and canonical `ci_validate.py`. Runtime-dependent tests use evidence fixtures only to test rejection/ingestion semantics; no fixture may be reported as real B2/B3 evidence.

## Out of scope

Model download, model cache, llama.cpp adapters, runtime lifecycle, hardware discovery, scheduler implementation, worker execution, runtime failover, and real inference remain exclusively in Claude's lane. Expansion beyond the first green E2E remains staged and does not mass-activate models.
