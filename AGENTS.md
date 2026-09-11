# AGENTS.md — GITHUB_BRAIN_V2 Adaptive Entrypoint

This repository uses one GitHub-first routed brain with an adaptive runtime. Keep this file small; detailed behavior belongs in the canonical registries.

## Fast bootstrap
When GitHub access is available at a new chat or substantive work cycle:
1. Read `AI_SKILL_LIBRARY/checkpoint.json`.
2. Follow its `bootstrap_path` to `AI_SKILL_LIBRARY/bootstrap.yaml`.
3. Every request enters `task_router`, then selects exactly one runtime profile: `FAST`, `STANDARD`, or `DEEP`.

Do not preload the full brain, skill catalog, project state, memory, source registry, plugin registry, or Trading state merely to answer a simple request.

## Adaptive execution
- `FAST`: low-risk, single-intent, non-mutating work. Use minimal core reasoning and answer; no default memory/tool/project preload.
- `STANDARD`: domain/project/tool work. Load only relevant authority, skills, bounded memory, sources/tools, then verify.
- `DEEP`: architecture, brain changes, deployment/runtime claims, live/trading, destructive/financial/credential-sensitive or complex multi-step work. Add scoped memory, planner, security gate, critic, verification, eval/trace, with bounded replanning.

Control-plane layers do not consume the domain supporting-skill budget. Domain selection remains one primary plus at most two supporting skills by default.

## Canonical registries
Discover current paths from `checkpoint.json` / `bootstrap.yaml`. Current canonical files include:
- `AI_SKILL_LIBRARY/router.yaml`
- `AI_SKILL_LIBRARY/runtime.yaml`
- `AI_SKILL_LIBRARY/projects.yaml`
- `AI_SKILL_LIBRARY/skills/catalog.yaml`
- `AI_SKILL_LIBRARY/memory.yaml`
- `AI_SKILL_LIBRARY/evals.yaml`
- `AI_SKILL_LIBRARY/observability.yaml`
- `AI_SKILL_LIBRARY/security.yaml`
- `AI_SKILL_LIBRARY/sources.yaml`
- `AI_SKILL_LIBRARY/plugins.yaml`

Load `GITHUB_BRAIN_V2.md` and `CORE_PROTOCOL.md` when the selected profile/task requires detailed protocol semantics, and always for changes to the brain itself.

`GITHUB_BRAIN_V1` remains a compatibility alias to the current V2 checkpoint.

## Authority
Current runtime/source state outranks generic knowledge. `projects.yaml` permits one CURRENT/ACTIVE authority per project. Historical snapshots never self-promote.

For Trading, only after routing to Trading: load `docs/checkpoints/CURRENT_HANDOFF.md` and the canonical checkpoint it names. Never fabricate market/account/runtime data or call code/commit LIVE without runtime verification.

## Learning and memory
Memory is retrieved before durable writes, remains scoped and bounded, and never outranks current project authority. Verified failures and user corrections may become candidate evals; brain changes are not auto-promoted or auto-merged merely because an agent proposes them.

## Engineering changes
Use test-first behavior changes where applicable: confirm RED, implement minimum GREEN, run relevant validators/tests, inspect diff/CI, and verify before merge/completion claims.

## Fallback
If GitHub cannot be refreshed, disclose `fresh_git_context=false` and use last-known context when appropriate. Never pretend a fresh GitHub read occurred.
