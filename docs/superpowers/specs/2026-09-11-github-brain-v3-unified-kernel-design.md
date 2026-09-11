# GITHUB_BRAIN V2.2 → V3 Unified Kernel Design

## Goal
Evolve the current V2.1 adaptive runtime through explicit V2.2, V2.3, V2.4 milestones and promote one final V3 authority without creating competing brain authorities or preloading unnecessary context.

## Non-goals
- Do not alter Trading runtime state or Trading execution authority.
- Do not weaken risk/security gates.
- Do not preload all skills, projects, sources, plugins, memory, or Trading state.
- Do not claim runtime/live state from source code alone.

## Version milestones

### V2.2 — Context Scheduler & Cache
Add a bounded context scheduler with cache/dedup policy. It ranks authority, freshness, task relevance, evidence value, and cost; avoids repeated registry reads inside one work cycle; invalidates cache on checkpoint/project/source freshness changes; and preserves FAST as the zero-heavy-context path.

### V2.3 — Reliability & Evidence Ledger
Add retry/circuit-breaker/fallback policy, evidence ledger, provenance/conflict handling, and uncertainty escalation. Material conclusions must be traceable to evidence classes without persisting hidden chain-of-thought.

### V2.4 — Task Graph & Parallel Orchestration
Add task-graph decomposition for independent subtasks, bounded parallelism, dependency-aware joins, tool/cost/latency budgets, and deterministic fallback to serial execution. High-impact actions remain gated and cannot be parallelized across unsafe side effects.

### V3 — Unified Kernel
Promote a single canonical `GITHUB_BRAIN_V3.md` authority and `kernel.yaml` control plane. V1/V2 become compatibility redirects only. Add migration registry, global invariant validator, version discovery, capability negotiation, recovery state machine, and one canonical execution contract.

## V3 execution model
1. Compact bootstrap discovers checkpoint and kernel.
2. `task_router` selects FAST/STANDARD/DEEP.
3. Kernel computes context plan, authority set, skill set, evidence/tool budget, security class, and orchestration mode.
4. FAST remains minimal and non-persistent.
5. STANDARD uses bounded context/evidence/tools and verification.
6. DEEP adds task graph, planner, critic, evidence ledger, security gate, bounded replanning, eval/trace.
7. Any failed invariant degrades safely rather than widening scope.

## Core invariants
- Exactly one CURRENT ai_brain authority.
- Trading authority remains `docs/checkpoints/CURRENT_HANDOFF.md` following its canonical checkpoint.
- One runtime profile per request.
- No hidden reasoning persistence.
- No durable secrets/credentials/private keys/account data.
- Destructive/financial/credential-sensitive actions require DEEP and explicit permission policy.
- Cache never outranks fresher authority/current source state.
- Parallelism is bounded and dependency-aware.
- Self-improvement never auto-merges.
- V1/V2 compatibility files cannot declare CURRENT_AUTHORITY.

## Completion gates
- RED contract observed before implementation.
- All legacy V2 tests remain green.
- New V3 invariant tests/validator green.
- Branch CI green.
- Diff/authority audit confirms no Trading state change.
- PR merge succeeds.
- Post-merge main CI green.
