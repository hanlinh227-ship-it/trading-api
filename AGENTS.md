# AGENTS.md — GITHUB_BRAIN_V2 Entrypoint

This repository uses one routed global AI bootstrap. Keep this file small; domain behavior belongs in the V2 registries/skills, not here.

## Bootstrap
When GitHub access is available, refresh:
1. `AI_SKILL_LIBRARY/checkpoint.json`
2. `AI_SKILL_LIBRARY/GITHUB_BRAIN_V2.md`
3. `AI_SKILL_LIBRARY/CORE_PROTOCOL.md`
4. `AI_SKILL_LIBRARY/router.yaml`

Every request then passes through `task_router`. A simple request may need no additional domain skill.

## Per-request flow
`request -> task_router -> project authority -> primary skill -> max 2 supporting skills -> relevant sources -> relevant plugins/tools -> critical review -> execute -> verify -> answer`

- Skill metadata: `AI_SKILL_LIBRARY/skills/catalog.yaml`
- Project authority: `AI_SKILL_LIBRARY/projects.yaml`
- Knowledge sources: `AI_SKILL_LIBRARY/sources.yaml`
- Optional tools/plugins: `AI_SKILL_LIBRARY/plugins.yaml`

Load only what the route needs. Do not preload every skill or every project checkpoint. In particular, do not load Trading state for non-Trading work.

`GITHUB_BRAIN_V1` is a compatibility alias to V2 via `AI_SKILL_LIBRARY/GITHUB_BRAIN_V1.md`.

## Authority
Project/runtime source state outranks generic knowledge. `projects.yaml` permits one CURRENT/ACTIVE authority per project. Historical snapshots never self-promote by filename or version.

For Trading, only after routing to Trading: load `docs/checkpoints/CURRENT_HANDOFF.md` and the canonical checkpoint it names. Preserve live infrastructure dependencies and hard risk/protection controls. Never fabricate market/account/runtime data and never call a source commit LIVE without runtime verification.

## Engineering changes
Use test-first behavior changes where applicable: confirm RED, implement minimum GREEN, run the relevant validators/tests, inspect diff/CI, and verify before merge/completion claims.

## Fallback
If GitHub cannot be refreshed, disclose `fresh_git_context=false` and use last-known context. Never pretend a fresh GitHub read occurred.
