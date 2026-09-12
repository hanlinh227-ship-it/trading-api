# AGENTS.md — GITHUB_BRAIN_V4 LTS Entrypoint

This repository uses one GitHub-first V4 LTS dual-plane brain. Keep this file compact; detailed behavior lives in the active immutable capability release, checkpoint-resolved registries, and the validated Skill-Mandatory Fast Gateway snapshot.

## Bootstrap
At a new substantive work cycle when GitHub is available:
1. Read `AI_SKILL_LIBRARY/checkpoint.json`.
2. Resolve `global_checkpoint_path` and read `AI_SKILL_LIBRARY/AI_GLOBAL_CHECKPOINT.md` before inferring current runtime/deployment state from conversation history.
3. Resolve `release_pointer_path` to `AI_SKILL_LIBRARY/v4/releases/current.json` and verify the selected immutable release before treating it as Stable authority.
4. Resolve the checkpoint-declared Skill Gateway compiler/validator/schema/alias paths. The active runtime snapshot must be exact-SHA validated before promotion.
5. Route every handled GitHub Brain request through V4 Stable `task_router`, exactly one `FAST`, `STANDARD`, or `DEEP` profile, exactly one primary reasoning skill, and that skill's validated execution capsule before answer generation.
6. Load one primary Knowledge Mesh domain. Supporting skills/bridges are optional and bounded by the selected profile; provider capability never becomes reasoning authority.
7. Only after routing, lazy-load project authority, bounded memory, sources, provider metadata, and tools that are materially required.
8. Before provider execution resolve the cloud runtime and relevant provider policy. Normal research must not depend on user-local installation.

There is no valid `request -> answer` bypass inside the GitHub Brain orchestration path. `task_router` is mandatory infrastructure but does not satisfy the primary-skill requirement.

## Skill-Mandatory Fast Gateway
- Every routed request has exactly one primary skill. Unknown/ambiguous specialist intent falls back to `core_reasoning`.
- The primary skill must have a validated execution capsule and the capsule must be applied; attaching only a skill ID is invalid.
- `FAST` route/skill/capsule selection uses the last verified exact-SHA hot snapshot and performs no GitHub/provider/network call for routing.
- `FAST` has zero supporting skills, zero durable-memory preload, zero bridge nodes and zero tool preload.
- `STANDARD` and `DEEP` lazy-load only relevant authority/context/tools after primary-skill selection.
- Live, trading, deployment/runtime, destructive, financial, credential-sensitive and other high-impact requests remain eligible for escalation and may not be downgraded to cached FAST behavior.
- Snapshot/provider data never masquerades as fresh live state.
- Internal routing traces may record profile/domain/skill/capsule hash/source SHA/latency/tool-use metadata, but never hidden chain-of-thought, credentials, secrets, or private provider payloads.

## Skill registry
- The checkpoint is the discovery root; never hard-code a registry version or provider list in client instructions.
- `AI_SKILL_LIBRARY/skills/registry/index.yaml` remains a compact discovery surface; the production FAST router uses the validated compiled snapshot rather than fetching the registry on each request.
- Provider registries are capability/evidence metadata only. Primary/supporting reasoning skills remain the decision path.
- Provider detail is lazy-loaded only after domain selection and subject to the configured candidate cap.
- Provider conflicts use the checkpoint-resolved conflict policy. Never majority-vote or silently average conflicting provider claims.
- Unknown/new provider skills default to quarantine with zero routing authority.
- `HIGH_RISK` financial/wallet/credential capabilities are discoverable for classification but never auto-activate.

## Zero-local cloud runtime
- Normal research execution must not require the user to install Node, npm, Python, exchange skill bundles, provider CLIs, or local MCP servers.
- Skill routing production runs on Cloudflare Workers through the exact-main GitHub Actions deployment contract and exposes `/brain/health` and `/brain/route`.
- The existing Railway research gateway remains authoritative for live-price research until a separate Cloudflare live-research cutover is production-verified; do not infer that Skill Gateway deployment migrated live market execution authority.
- Execution preference is checkpoint-resolved and cloud-first: connected cloud tool -> public first-party HTTPS -> approved remote read-only MCP -> explicit degraded failure.
- Never fall back to asking for a local installation merely because a provider adapter is unavailable.
- `RESEARCH_SAFE` may execute in an approved healthy cloud gateway.
- `AUTH_READ_ONLY` remains disabled until separate credential authorization and must use cloud-held restricted read-only secrets only.
- `HIGH_RISK` has no cloud execution path in the zero-local research runtime.
- Cloud/provider output is evidence only and remains subordinate to project authority, Stable security, freshness and conflict policy.

## Two planes
- **Stable Runtime Plane** answers normal requests immediately from the last known-good validated release/snapshot. It must work even when Evergreen or GitHub refresh is temporarily unavailable.
- **Evergreen Update Plane** discovers skills/knowledge/upstream changes, quarantines candidates, checks provenance/license/conflicts/security/evals, canaries them, and promotes only validated immutable release bundles. It never mutates an in-flight Stable request or widens permissions.

## Profiles
- `FAST`: exactly one primary skill + capsule; no supporting skill, durable memory/tool preload, bridge node, Trading preload, Evergreen sync, or routing network RTT.
- `STANDARD`: exactly one primary skill + capsule; bounded project/domain context, memory/tools and at most one bridge node; up to two supporting skills only when materially useful.
- `DEEP`: exactly one primary skill + capsule; architecture/protocol/live/trading/high-impact/complex work; bounded planner/task graph/critic/eval and at most two bridge nodes/supporting skills.

## Authority
Current project/runtime authority outranks Stable memory, provider guidance, cached context, learned patterns and external examples. Historical state cannot self-promote.

For Trading, only after routing to Trading load `docs/checkpoints/CURRENT_HANDOFF.md` and `docs/checkpoints/BYBIT_BTC_STATEFLOW_2_1_20260904.md`. Brain upgrades and provider skills never silently replace Trading execution authority. Never fabricate market/account/runtime state or call source code/commit LIVE without runtime verification.

## Learning
New skills start in V4 Evergreen quarantine with zero routing authority. Class A/B/C promotion follows V4 gates; Class D financial/credential/destructive permission expansion never auto-promotes. Skill/tool reputation may influence ranking only among equally authorized capabilities and never overrides security or authority.

## Compatibility
`GITHUB_BRAIN_V3`, `GITHUB_BRAIN_V2`, and `GITHUB_BRAIN_V1` are compatibility aliases only and resolve to V4 through `checkpoint.json`.

## Engineering
Behavior changes use test-first discipline: RED -> minimum GREEN -> regression suite -> validators -> CI -> merge -> post-merge production verification.

## Fallback
If GitHub refresh or snapshot promotion fails, disclose `fresh_git_context=false` when material and continue only from the last verified Stable release/snapshot where policy permits. Never activate a partial/invalid snapshot and never pretend a fresh read occurred.
