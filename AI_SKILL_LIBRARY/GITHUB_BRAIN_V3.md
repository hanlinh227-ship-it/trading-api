# GITHUB_BRAIN_V3 — Unified GitHub-First Kernel

This is the single canonical **GitHub-first** AI orchestration authority for the repository. Discovery starts from `AI_SKILL_LIBRARY/checkpoint.json`, then `AI_SKILL_LIBRARY/bootstrap.yaml`, then `AI_SKILL_LIBRARY/kernel.yaml`.

## Core contract
Every request enters `task_router`, selects exactly one runtime profile (`FAST`, `STANDARD`, `DEEP`), resolves only the authority/context required by that route, executes with bounded tools/memory/orchestration, verifies, and answers.

`request -> task_router -> runtime_profile -> kernel plan -> scoped authority/context -> skills -> sources/tools -> security gate when needed -> execute -> verify -> answer`

DEEP may additionally use planner, dependency graph, critic, evidence ledger, eval, trace, and bounded replanning. These are control-plane layers and do not consume the domain supporting-skill budget.

## FAST / STANDARD / DEEP
- **FAST**: single-intent, low-risk, non-mutating, no live/current-data dependency, no required external tool. Serial only; no durable memory; no project/trading preload; no persistent trace.
- **STANDARD**: normal domain/project work, artifact creation, ordinary research, reversible tool use. Bounded context/memory/tools and optional safe parallel reads.
- **DEEP**: architecture/protocol changes, live/trading, deployment/runtime claims, complex multi-step work, destructive/financial/credential-sensitive actions, or material evidence conflicts. Uses full control plane with bounded budgets.

## V2.2 context scheduler
`context.yaml` ranks current authority/runtime state, task relevance, freshness, evidence quality, and context cost. It deduplicates repeated registry reads, caches only within a work cycle, and invalidates on checkpoint/authority/source changes, explicit refresh, live/current requests, mutation, or deploy. Cache never outranks fresher authority.

## V2.3 reliability and evidence
`reliability.yaml` defines bounded retry, circuit breaker, recovery, and degraded-state disclosure. `evidence.yaml` defines provenance ledger, conflict handling, fact/inference/assumption separation, and uncertainty escalation. Hidden chain-of-thought is never persisted.

## V2.4 orchestration
`orchestration.yaml` defines dependency-aware task graphs and bounded parallelism. Independent reads/research/validation may run in parallel when beneficial. High-impact writes, credential operations, financial execution, conflicting writes, and dependent mutations remain serial/gated. Serial fallback is mandatory.

## V3 kernel
`kernel.yaml` unifies runtime profile selection, context planning, capability negotiation, orchestration, reliability, evidence, security, recovery, verification, and learning gates. Global invariants are enforced by `validate_v3.py` and CI.

## Routing and skills
`AI_SKILL_LIBRARY/router.yaml` remains the routed domain map. One primary skill plus at most two supporting skills is the default domain budget. `AI_SKILL_LIBRARY/skills/catalog.yaml` is lazy-loaded; the full catalog is never injected by default.

## Project authority
`AI_SKILL_LIBRARY/projects.yaml` permits exactly one current authority per project scope. Current project/runtime state outranks external examples and memory. Historical snapshots cannot self-promote.

For Trading, only after routing to Trading, load `docs/checkpoints/CURRENT_HANDOFF.md` and its canonical checkpoint `docs/checkpoints/BYBIT_BTC_STATEFLOW_2_1_20260904.md`. Trading runtime authority is unchanged by the V3 migration. Never fabricate prices/account/runtime state and never call source code or a commit LIVE without runtime verification.

## Memory and learning
`memory.yaml` keeps working/episodic/semantic/procedural memory bounded and scoped. Durable memory excludes secrets, credentials, private keys, account data, sensitive personal data, raw private chat, authentication tokens, and unreviewed runtime state. Current verified authority outranks memory.

`evals.yaml` turns verified failures/material corrections into candidate regression evals. Self-improvement cannot auto-merge; tests, eval baseline, security, authority, and CI gates remain mandatory.

## Security and observability
`security.yaml` uses least privilege and conservative defaults for destructive, financial, and credential-sensitive actions. `observability.yaml` records only bounded diagnostic summaries, not hidden reasoning.

## Sources and plugins
`AI_SKILL_LIBRARY/sources.yaml` is a knowledge-source registry; default training remains false. `AI_SKILL_LIBRARY/plugins.yaml` exposes optional tools/capabilities. Plugins are tools, never reasoning authority.

## Compatibility
`GITHUB_BRAIN_V2` and `GITHUB_BRAIN_V1` are compatibility aliases only. `AI_SKILL_LIBRARY/GITHUB_BRAIN_V2.md` and `AI_SKILL_LIBRARY/GITHUB_BRAIN_V1.md` redirect older chats to the V3 checkpoint and cannot declare current authority.

## Freshness and fallback
Refresh GitHub at a new work cycle, when continuing mutable project work, on explicit checkpoint/refresh requests, before code/config mutation, before merge/deploy, and before ACTIVE/LIVE/current-state claims. If refresh fails, disclose `fresh_git_context=false`; never pretend a fresh read occurred.

## Canonical files
- `checkpoint.json`
- `bootstrap.yaml`
- `kernel.yaml`
- `router.yaml`
- `runtime.yaml`
- `context.yaml`
- `reliability.yaml`
- `evidence.yaml`
- `orchestration.yaml`
- `projects.yaml`
- `skills/catalog.yaml`
- `memory.yaml`
- `evals.yaml`
- `observability.yaml`
- `security.yaml`
- `plugins.yaml`
- `sources.yaml`
- `migration.yaml`
- schemas and validators including `validate_v3.py`
