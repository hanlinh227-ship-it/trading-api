# GITHUB_BRAIN_V2 Adaptive Agent Runtime Design

## Goal
Upgrade the routed GitHub-first brain in one compatible release so it learns from failures, retrieves only useful memory, uses planner/critic/verification only when warranted, dynamically limits tools, records compact traces, and enforces side-effect permissions without slowing simple requests.

## Design principles
- Keep `AI_SKILL_LIBRARY/checkpoint.json` as the stable discovery entrypoint.
- Preserve `task_router` as mandatory for every request.
- Add a compact `bootstrap.yaml` so a new chat can discover the active control plane without loading the full library.
- Separate control-plane policies from domain skills. Memory/eval/observability/security are orchestration layers, not extra domain skills and do not consume the two-supporting-skill budget.
- Progressive disclosure: load only the profile, project, skills, memory slices, sources, and tools needed by the current task.
- No Trading preload for non-Trading work and no change to current Trading authority.
- No self-modifying brain promotion without tests, eval comparison, security checks, CI, and explicit merge policy.

## Runtime profiles

### FAST
For single-intent, low-risk, non-mutating, non-live tasks.
Flow: `task_router -> minimal core reasoning -> answer`.
No project state, memory, source registry, plugin discovery, planner, critic, or trace payload unless the task itself needs them.

### STANDARD
For domain work, one-project work, ordinary research, artifact creation, or tool use.
Flow: `task_router -> project authority if relevant -> primary/supporting skills -> bounded memory retrieval -> relevant sources/tools -> execute -> verification -> answer`.
Critical review is conditional on consequence/uncertainty.

### DEEP
For architecture, multi-step engineering, deployment/runtime claims, live/trading work, destructive or financial actions, complex research, and brain modifications.
Flow: `task_router -> authority -> scoped memory -> planner -> skills -> sources/tools -> security gate -> execute -> critic -> verifier -> eval/trace -> replan if allowed -> answer`.
Replan budget is capped to prevent loops.

## Components

### `bootstrap.yaml`
Compact machine-readable startup map: checkpoint id/version, canonical paths, profile defaults, fast-path rules, and refresh triggers. It is intentionally small enough to load in every new work cycle.

### `runtime.yaml`
Defines FAST/STANDARD/DEEP selection, stage activation, context budgets, replan limits, freshness escalation, and control-plane ordering.

### `memory.yaml`
Four logical layers:
- working: current task only;
- episodic: prior task outcomes/failures;
- semantic: stable verified facts/rules;
- procedural: reusable successful workflows.

Memory records must be scoped, sourced, confidence-tagged, timestamped, and supersedable. Retrieval is bounded by profile. Secrets, credentials, account data, sensitive personal data, raw private chat, and unreviewed runtime state are excluded from durable memory.

### `evals.yaml`
Defines failure taxonomy, regression conversion, benchmark gates, scoring dimensions, and promotion policy. User corrections and verified failures can become candidate regression cases. Brain changes are promoted only when required tests pass and no protected dimension regresses beyond tolerance.

### `observability.yaml`
Defines compact decision traces with event allowlists and sampling. FAST requests default to no persistent trace. STANDARD stores only errors/corrections/material decisions. DEEP stores a bounded trace. Hidden chain-of-thought is never recorded; only concise decisions, evidence references, tool outcomes, verification results, and failure categories.

### `security.yaml`
Classifies capabilities as read-only, reversible-write, destructive, financial, or credential-sensitive. Defines default-deny for destructive/financial/credential-sensitive side effects unless an existing higher-priority user/project policy explicitly authorizes them. Secret exfiltration and private-key disclosure remain blocked.

### `validate_runtime.py`
Validates cross-file consistency: profile order and budgets, bootstrap pointers, memory limits/privacy exclusions, eval gates, trace policy, security classes, and router integration.

## Performance model
- New chat loads `checkpoint.json` plus compact `bootstrap.yaml`; detailed protocol files are lazy-loaded when the selected profile requires them.
- FAST path has zero supporting skills and zero default external tools/memory reads.
- STANDARD and DEEP cap memory items and tool discovery results.
- Planner/critic/eval are not always-on.
- Observability is sampled and bounded; no verbose reasoning transcript is stored.
- Full skill catalog is never injected into task context; router metadata remains the selector.

## Learning loop
`verified failure or user correction -> classify -> candidate eval -> reproduce -> propose policy/skill patch -> run tests/evals -> compare baseline -> PR -> promote only after verification`.
This is controlled improvement, not autonomous self-rewriting.

## Compatibility
- Checkpoint id remains `GITHUB_BRAIN_V2`; version advances within V2.
- `GITHUB_BRAIN_V1` remains an alias.
- Existing project authority and source/plugin registries remain canonical in their current roles.
- Existing router routes remain valid; runtime profiles wrap them rather than replace them.

## Acceptance criteria
1. Every request still enters through `task_router`.
2. FAST path exists and does not preload project state, memory, tools, or Trading state.
3. STANDARD/DEEP profiles have bounded context/tool/memory budgets.
4. Memory, eval, observability, and security policies are explicit and validated.
5. Checkpoint/bootstrap pointers are complete and future-compatible.
6. CI compiles/runs the new validator and tests.
7. Existing V2 contract, authority, router, registry, and ingest checks remain green.
