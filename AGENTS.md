# AGENTS.md — GITHUB_BRAIN_V4 LTS Entrypoint

This repository uses one GitHub-first V4 LTS dual-plane brain. Keep this file compact; detailed behavior lives in the active immutable capability release and checkpoint-resolved registries.

## Bootstrap
At a new substantive work cycle when GitHub is available:
1. Read `AI_SKILL_LIBRARY/checkpoint.json`.
2. Resolve `global_checkpoint_path` and read `AI_SKILL_LIBRARY/AI_GLOBAL_CHECKPOINT.md` before inferring current runtime/deployment state from conversation history.
3. Resolve `release_pointer_path` to `AI_SKILL_LIBRARY/v4/releases/current.json`.
4. Verify the selected release manifest before treating it as Stable authority.
5. Resolve `skill_registry_index_path` from the checkpoint and perform the lightweight registry-index lookup required for every request. Do not preload provider detail.
6. Resolve `cloud_runtime_policy_path` and `cloud_runtime_manifest_path` before provider execution; normal crypto research must not depend on local installation.
7. Route every request through V4 Stable `task_router` and exactly one `FAST`, `STANDARD`, or `DEEP` profile.
8. Load one primary Knowledge Mesh domain and only explicitly allowed bridges.
9. After domain selection, lazy-load only the matching provider registry, source registry, or capability metadata declared by the checkpoint/domain pack. Provider capability does not become reasoning authority.

Do not preload the full legacy catalog, provider registries, unrelated domains, project states, durable memory, tools, Evergreen, or Trading state for simple work.

## Skill registry
- The checkpoint is the discovery root; never hard-code a registry version or provider list in client instructions.
- `AI_SKILL_LIBRARY/skills/registry/index.yaml` is a small pointer/index surface and may be consulted for every request.
- Provider registries are capability/evidence metadata only. Existing primary/supporting reasoning skills remain the decision path.
- Provider detail is lazy-loaded only after domain selection and subject to the configured candidate cap.
- Provider conflicts use the checkpoint-resolved conflict policy. Never majority-vote or silently average conflicting provider claims.
- Unknown/new provider skills default to quarantine with zero routing authority.
- `HIGH_RISK` financial/wallet/credential capabilities are discoverable for classification but never auto-activate.

## Zero-local cloud runtime
- Normal research execution must not require the user to install Node, npm, Python, exchange skill bundles, provider CLIs, or local MCP servers.
- Execution preference is checkpoint-resolved and cloud-first: connected cloud tool -> public first-party HTTPS -> approved remote read-only MCP -> explicit degraded failure.
- Never fall back to asking for a local installation merely because a provider adapter is unavailable.
- Production Railway releases use the checkpoint-resolved connector-managed exact-commit protocol; do not assume Railway GitHub autodeploy exists.
- `RESEARCH_SAFE` may execute in the approved cloud gateway when healthy.
- `AUTH_READ_ONLY` remains disabled until separate credential authorization and must use cloud-held restricted read-only secrets only.
- `HIGH_RISK` has no cloud execution path in the zero-local research runtime.
- Cloud provider output is evidence only and remains subordinate to project authority, Stable security, freshness and the conflict policy.

## Two planes
- **Stable Runtime Plane** answers normal requests immediately from the last known-good validated release. It must work even when Evergreen is offline.
- **Evergreen Update Plane** discovers skills/knowledge/upstream changes, quarantines candidates, checks provenance/license/conflicts/security/evals, canaries them, and promotes only immutable release bundles. It never mutates an in-flight Stable request or widens permissions.

## Profiles
- `FAST`: one primary domain, serial, no durable memory/tool preload, no bridge nodes, no Trading preload, no Evergreen sync.
- `STANDARD`: bounded project/domain context, memory, tools and at most one bridge node.
- `DEEP`: architecture/protocol/live/trading/high-impact or complex multi-step work; bounded planner/task graph/critic/eval and at most two bridge nodes.

## Authority
Current project/runtime authority outranks Stable memory, provider guidance, cached context, learned patterns and external examples. Historical state cannot self-promote.

For Trading, only after routing to Trading load `docs/checkpoints/CURRENT_HANDOFF.md` and `docs/checkpoints/BYBIT_BTC_STATEFLOW_2_1_20260904.md`. Brain upgrades and provider skills never silently replace Trading execution authority. Never fabricate market/account/runtime state or call source code/commit LIVE without runtime verification.

## Learning
New skills start in V4 Evergreen quarantine with zero routing authority. Class A/B/C promotion follows V4 gates; Class D financial/credential/destructive permission expansion never auto-promotes. Skill/tool reputation may influence ranking only among equally authorized capabilities and never overrides security or authority.

## Compatibility
`GITHUB_BRAIN_V3`, `GITHUB_BRAIN_V2`, and `GITHUB_BRAIN_V1` are compatibility aliases only and resolve to V4 through `checkpoint.json`.

## Engineering
Behavior changes use test-first discipline: RED -> minimum GREEN -> regression suite -> validators -> CI -> merge -> post-merge verification.

## Fallback
If GitHub refresh fails, disclose `fresh_git_context=false` and continue only from the last verified Stable release when suitable. Never pretend a fresh read occurred.
