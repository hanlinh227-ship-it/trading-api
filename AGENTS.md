# AGENTS.md — GITHUB_BRAIN_V4 LTS Entrypoint

This repository uses one GitHub-first V4 LTS dual-plane brain. Keep this file compact; detailed behavior lives in the active immutable capability release.

## Bootstrap
At a new substantive work cycle when GitHub is available:
1. Read `AI_SKILL_LIBRARY/checkpoint.json`.
2. Resolve `release_pointer_path` to `AI_SKILL_LIBRARY/v4/releases/current.json`.
3. Verify the selected release manifest before treating it as Stable authority.
4. Route every request through V4 Stable `task_router` and exactly one `FAST`, `STANDARD`, or `DEEP` profile.
5. Load one primary Knowledge Mesh domain and only explicitly allowed bridges.

Do not preload the full legacy catalog, unrelated domains, project states, durable memory, tools, Evergreen, or Trading state for simple work.

## Two planes
- **Stable Runtime Plane** answers normal requests immediately from the last known-good validated release. It must work even when Evergreen is offline.
- **Evergreen Update Plane** discovers skills/knowledge/upstream changes, quarantines candidates, checks provenance/license/conflicts/security/evals, canaries them, and promotes only immutable release bundles. It never mutates an in-flight Stable request or widens permissions.

## Profiles
- `FAST`: one primary domain, serial, no durable memory/tool preload, no bridge nodes, no Trading preload, no Evergreen sync.
- `STANDARD`: bounded project/domain context, memory, tools and at most one bridge node.
- `DEEP`: architecture/protocol/live/trading/high-impact or complex multi-step work; bounded planner/task graph/critic/eval and at most two bridge nodes.

## Authority
Current project/runtime authority outranks Stable memory, cached context, learned patterns and external examples. Historical state cannot self-promote.

For Trading, only after routing to Trading load `docs/checkpoints/CURRENT_HANDOFF.md` and `docs/checkpoints/BYBIT_BTC_STATEFLOW_2_1_20260904.md`. Brain upgrades never silently replace Trading execution authority. Never fabricate market/account/runtime state or call source code/commit LIVE without runtime verification.

## Learning
New skills start in V4 Evergreen quarantine with zero routing authority. Class A/B/C promotion follows V4 gates; Class D financial/credential/destructive permission expansion never auto-promotes. Skill/tool reputation may influence ranking only among equally authorized capabilities and never overrides security or authority.

## Compatibility
`GITHUB_BRAIN_V3`, `GITHUB_BRAIN_V2`, and `GITHUB_BRAIN_V1` are compatibility aliases only and resolve to V4 through `checkpoint.json`.

## Engineering
Behavior changes use test-first discipline: RED -> minimum GREEN -> regression suite -> validators -> CI -> merge -> post-merge verification.

## Fallback
If GitHub refresh fails, disclose `fresh_git_context=false` and continue only from the last verified Stable release when suitable. Never pretend a fresh read occurred.
