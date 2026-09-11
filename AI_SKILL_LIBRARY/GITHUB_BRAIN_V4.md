# GITHUB_BRAIN_V4 LTS

Canonical AI-brain authority for `hanlinh227-ship-it/trading-api`.

## Discovery

1. Read `AI_SKILL_LIBRARY/checkpoint.json`.
2. Resolve `release_pointer_path` to `AI_SKILL_LIBRARY/v4/releases/current.json`.
3. Verify the selected immutable release manifest before use.
4. Route every request through V4 Stable `task_router` and exactly one FAST/STANDARD/DEEP profile.
5. Load one primary Knowledge Mesh domain and only explicitly permitted bridges.
6. Load project authority only when the routed domain requires it. Trading authority remains external to Brain at `docs/checkpoints/CURRENT_HANDOFF.md`.

## Two planes

### Stable Runtime Plane
Stable is the only canonical request plane. It answers immediately from the current validated release and never waits for Evergreen. Stable must remain functional if all Evergreen workflows are unavailable.

### Evergreen Update Plane
Evergreen continuously discovers useful skills, upstream changes, verified failure patterns and optimization candidates. Every candidate is normalized, provenance/license checked, quarantined, conflict/security checked, benchmarked, canaried and promoted only through the release contract. Evergreen cannot mutate an in-flight Stable request or expand its own permissions.

## Knowledge Mesh
Knowledge is partitioned into domain namespaces. Cross-domain reasoning uses explicit bounded bridges. Global domain preload is forbidden. Trading runtime/account state cannot leak through ordinary bridges.

## Skill admission
New skills default to no routing authority. Low-risk declarative Class A skills may auto-promote only after every required gate and a green canary. Class B executable/tool adapters additionally require sandbox/compatibility checks. Class C kernel/router/security/authority changes require two green canaries, exact compatibility proof and a rollback snapshot. Class D financial, credential-sensitive or destructive permission expansion never auto-promotes.

## Authority and evidence
Precedence: current runtime/project authority → V4 security invariants → active Stable release contract → domain policy → verified current evidence → skill-pack precedence → scoped verified memory → external reference knowledge. Material unresolved conflict blocks promotion and must be disclosed during normal reasoning when relevant.

## Long-term rule
Do not redesign the brain merely to add knowledge. Add or improve a domain node, bridge, skill pack, adapter, eval, source policy or capability release; let Evergreen validate it; promote only a verified immutable release.

## Compatibility
`GITHUB_BRAIN_V3`, `GITHUB_BRAIN_V2`, and `GITHUB_BRAIN_V1` are compatibility activation aliases that resolve to this V4 authority. Their legacy files contain redirect semantics only after V4 promotion.
