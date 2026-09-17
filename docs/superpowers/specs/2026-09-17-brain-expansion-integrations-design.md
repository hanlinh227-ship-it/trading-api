# Brain Expansion Integrations Design

## Goal

Add a bounded expansion layer around the existing GitHub Brain so selected external repositories can improve observability, evaluation, browser execution, and typed output contracts without replacing the current routing, model, multi-agent, memory, security, evidence, or promotion authorities.

## Scope

This design registers eight upstream repositories in two classes.

Runtime-adapter candidates:
- `langfuse/langfuse` for sanitized observability.
- `vibrantlabsai/ragas` for retrieval/RAG evaluation.
- `confident-ai/deepeval` for LLM/agent behavior evaluation.
- `browser-use/browser-use` for sandboxed browser execution.
- `BoundaryML/baml` for optional typed output contracts.

Reference-only candidates:
- `microsoft/agent-framework` for orchestration, session, MCP/A2A, and telemetry patterns.
- `letta-ai/letta` for long-term memory architecture patterns.
- `agno-agi/agno` for agent-team/runtime architecture patterns.

Reference-only candidates do not gain runtime dependency, routing authority, memory authority, or control-plane authority under this design.

## Existing Authorities Preserved

The following remain canonical and cannot be replaced by any new integration:

1. `task_router` is the single routing authority.
2. Legion is the multi-agent execution authority.
3. Model Mesh is the model/provider selection authority.
4. Memory Continuity is the memory authority.
5. Project authority precedes memory and external framework guidance.
6. Existing security, evidence, eval, observability, and promotion gates remain authoritative.

Every new component is an adapter, evaluator, executor, or reference source. No new component becomes a second brain.

## Architecture

```text
User Request
    |
    v
Task Router  <--- canonical authority
    |
    +---- Primary Skill + bounded supporting skills
    |
    +---- Legion / Model Mesh / Memory Continuity as already defined
    |
    v
Capability Boundary
    |
    +---- Langfuse adapter ------> sanitized diagnostic telemetry only
    +---- Ragas adapter ---------> offline/CI retrieval evaluation
    +---- DeepEval adapter ------> offline/CI behavioral evaluation
    +---- Browser Use adapter ---> sandbox browser execution
    +---- BAML adapter ----------> optional typed contract validation
    |
    +---- Microsoft Agent Framework / Letta / Agno
          reference-only pattern sources
```

The stable request path must remain functional when all five runtime-adapter candidates are disabled.

## Component Contracts

### Langfuse

Purpose: improve trace inspection and debugging without changing reasoning or routing.

Contract:
- consume only sanitized OpenTelemetry-compatible metadata permitted by `stable/observability.yaml`;
- never persist raw prompts, raw private chat, private tool payloads, secrets, credentials, authentication tokens, private keys, or hidden chain-of-thought;
- tracing failure must never break the stable request path;
- traces remain diagnostic, never authority.

### Ragas

Purpose: add reproducible RAG/retrieval quality measurements.

Contract:
- execute offline or in CI by default;
- map results to existing retrieval and evidence eval classes;
- no production request dependency;
- no external score may auto-promote a candidate;
- repository-native deterministic checks remain authoritative for promotion.

### DeepEval

Purpose: add behavioral regression tests for LLM/agent outputs.

Contract:
- offline/CI by default;
- map failures into the existing failure taxonomy;
- supplement rather than replace existing eval logic;
- no majority-vote truth mechanism;
- no production-path dependency required.

### Browser Use

Purpose: add browser execution for workflows lacking a better native API/tool path.

Contract:
- sandbox only until promoted through existing security and eval gates;
- task_router selects the capability; Browser Use does not choose objectives;
- read-only is the default action class;
- reversible writes require an explicit user request plus current project/security policy allowance;
- destructive operations follow existing explicit approval requirements;
- financial execution is forbidden through this generic adapter;
- credential persistence is forbidden;
- success claims require runtime verification when material;
- adapter is independently disableable.

### BAML

Purpose: improve reliability of structured model outputs.

Contract:
- optional schema/contract layer only;
- may not replace business logic, reasoning authority, or current canonical schemas by default;
- must interoperate with existing Pydantic/JSON Schema contracts;
- removal of the adapter must not change business semantics;
- no provider lock-in.

### Microsoft Agent Framework

Reference-only purpose: selectively learn session, handoff, MCP/A2A, workflow, and telemetry patterns.

Prohibited:
- parallel router;
- replacement of Legion;
- replacement of Model Mesh;
- mandatory runtime dependency without a separate approved promotion decision.

### Letta

Reference-only purpose: selectively learn memory-block, archival-memory, compaction, and persistence patterns.

Prohibited:
- memory authority;
- automatic writeback into Memory Continuity;
- competing persistent truth store;
- runtime dependency without a separate approved promotion decision.

### Agno

Reference-only purpose: selectively learn agent-team, workflow, inspection, and runtime patterns.

Prohibited:
- router replacement;
- Legion replacement;
- competing runtime control plane;
- runtime dependency without a separate approved promotion decision.

## Security and Privacy

All existing security controls remain in force. In particular:
- capability does not imply permission;
- secrets never enter the repository or durable memory;
- executable candidates require sandboxing;
- no browser adapter may be used to bypass destructive, financial, credential-sensitive, or project-specific controls;
- telemetry must comply with the existing sanitized observability contract.

## Upstream Intake

Before any dependency is added, the implementer must verify for each upstream:
- canonical repository identity;
- current default branch and a pinned commit/tag/ref;
- license and any dependency-license concerns;
- maintenance status;
- security posture and supply-chain risk;
- overlap with existing capabilities;
- performance and cost impact;
- permission impact;
- rollback path.

The architecture registry intentionally marks licenses as `verify_before_runtime`; no license assumption in this design grants permission to activate code.

## Promotion Model

A. Architecture registered.

B. Upstream audited: identity, license, pinned ref, maintenance, security, dependencies.

C. Sandbox adapter: minimal implementation, bounded permissions, externalized secrets, failure isolation, rollback.

D. Evaluated: targeted unit/integration tests, relevant evals, baseline comparison, zero protected-dimension regression.

E. Limited activation: explicit feature flag, sanitized observability, health check, disabled by default unless existing policy authorizes otherwise.

F. Stable candidate: full tests, eval baseline, security, authority, CI, and current repository merge/promotion policy.

No stage may be skipped solely because an upstream framework is popular or produces a high score.

## Failure Isolation

Every runtime adapter must fail closed or fall back to the existing stable brain behavior. The stable system must continue operating if an adapter is unavailable, stale, misconfigured, rate-limited, or disabled.

Browser execution failure must not be reported as successful execution. Observability failure must not block normal execution. Eval tooling failure must not silently promote a candidate. Typed-contract failure must surface as a contract error or fall back only according to explicit existing policy.

## Testing Requirements

Each runtime candidate requires:
- unit tests for adapter boundaries;
- configuration/feature-flag tests;
- failure-isolation tests;
- authority-preservation tests;
- security/privacy tests relevant to the adapter;
- targeted integration tests;
- baseline comparison where performance or quality can change;
- full existing brain validators and CI before completion.

Additional mandatory checks:
- Langfuse: sanitized telemetry and trace-failure isolation.
- Ragas/DeepEval: no production hard dependency and no auto-promotion from scores.
- Browser Use: read-only default, forbidden financial execution, approval boundary preservation, runtime success verification.
- BAML: compatibility with existing canonical schema paths and clean disable/remove behavior.

## Rollback

Each adapter must be independently disableable. No adapter may make irreversible changes to canonical brain state during initial activation. Rollback is feature-flag disablement plus dependency/config removal where required. Reference-only sources require no runtime rollback because they are not executable.

## Success Criteria

The design is successful when:
- the new architecture is discoverable from canonical brain state;
- the five runtime candidates have bounded adapter contracts;
- the three reference candidates cannot gain authority implicitly;
- no existing router, Legion, Model Mesh, Memory Continuity, security, observability, evidence, or eval authority is weakened;
- stable brain behavior remains available with all new adapters disabled;
- Claude Code can execute the implementation from a deterministic plan with test, verification, and rollback gates.
