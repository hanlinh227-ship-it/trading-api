# AGENTS.md — GITHUB_BRAIN_V3 Entrypoint

This repository uses one GitHub-first unified kernel. Keep this file small; detailed behavior belongs in checkpoint/bootstrap/kernel registries.

## Bootstrap
When GitHub access is available at a new chat or substantive work cycle:
1. Read `AI_SKILL_LIBRARY/checkpoint.json`.
2. Follow `bootstrap_path` to `AI_SKILL_LIBRARY/bootstrap.yaml`.
3. Follow `kernel_path` to `AI_SKILL_LIBRARY/kernel.yaml`.
4. Route every request through `task_router` and select exactly one profile: `FAST`, `STANDARD`, or `DEEP`.

Do not preload the full brain, skill catalog, project states, memory, sources, plugins, or Trading state for simple work.

## Profiles
- `FAST`: serial, low-risk, non-mutating, no live/current-data requirement, no durable memory/tool preload.
- `STANDARD`: bounded project/domain context, memory, tools, verification; safe independent reads may run in parallel.
- `DEEP`: architecture/protocol, live/trading, deployment/runtime claims, complex multi-step or high-impact work; adds planner, dependency graph, security gate, critic, evidence ledger, eval/trace and bounded replanning.

## V3 control plane
- Context/cache: `AI_SKILL_LIBRARY/context.yaml`
- Reliability: `AI_SKILL_LIBRARY/reliability.yaml`
- Evidence/provenance: `AI_SKILL_LIBRARY/evidence.yaml`
- Orchestration: `AI_SKILL_LIBRARY/orchestration.yaml`
- Runtime: `AI_SKILL_LIBRARY/runtime.yaml`
- Project authority: `AI_SKILL_LIBRARY/projects.yaml`
- Skills: `AI_SKILL_LIBRARY/skills/catalog.yaml`
- Security/memory/evals/observability/plugins/sources remain lazy and scoped.

`GITHUB_BRAIN_V2` and `GITHUB_BRAIN_V1` are compatibility aliases only and redirect to V3.

## Authority
Current project/runtime state outranks memory and external examples. One current authority per project. Historical snapshots cannot self-promote.

For Trading, only after routing to Trading: load `docs/checkpoints/CURRENT_HANDOFF.md` and `docs/checkpoints/BYBIT_BTC_STATEFLOW_2_1_20260904.md`. Never fabricate market/account/runtime data or call code/commit LIVE without runtime verification.

## Engineering
Behavior changes use test-first discipline where applicable: RED -> minimum GREEN -> validators/tests -> diff/CI -> merge -> post-merge verification.

## Fallback
If GitHub cannot be refreshed, disclose `fresh_git_context=false` and use last-known context only when appropriate. Never pretend a fresh read occurred.
