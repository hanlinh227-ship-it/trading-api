# GITHUB_BRAIN_V4 LTS

Canonical **GitHub-first** AI-brain authority for `hanlinh227-ship-it/trading-api`.

## Discovery

1. Read `AI_SKILL_LIBRARY/checkpoint.json`.
2. Resolve `release_pointer_path` to `AI_SKILL_LIBRARY/v4/releases/current.json`.
3. Verify the selected immutable release manifest before use.
4. Resolve `skill_registry_index_path` and perform the lightweight registry-index lookup required for every request; do not preload provider detail.
5. Route every request through V4 Stable `task_router` and exactly one FAST/STANDARD/DEEP profile.
6. Load one primary Knowledge Mesh domain and only explicitly permitted bridges.
7. Load project authority only when the routed domain requires it. Trading authority remains external to Brain at `docs/checkpoints/CURRENT_HANDOFF.md`.
8. After domain selection, lazy-load only the relevant provider/source registry declared by the checkpoint or domain pack. Provider capabilities are evidence/tool metadata, not reasoning authority.
9. Use `AI_SKILL_LIBRARY/sources.yaml` plus checkpoint-declared bounded source subregistries; source entries never outrank current project/runtime authority.

## Skill Registry

The registry index is a small GitHub-resident discovery layer. It exists so every request can resolve the current skill/capability map without loading every skill. Canonical reasoning still uses one primary skill and the bounded supporting-skill budget.

Provider registries:
- are loaded only after domain routing;
- do not count as reasoning skills;
- cannot override project authority, Stable security, runtime evidence, or user hard-risk controls;
- cap provider candidates to prevent context explosion;
- keep unknown/new upstream skills in quarantine with zero routing authority;
- keep financial/wallet/credential `HIGH_RISK` capability non-routable and non-auto-activating by default.

Provider disagreement is reconciled by the checkpoint-resolved conflict policy. Provider outputs are evidence, not votes: never majority-vote or silently average material conflicts. Normalize identity, venue/instrument, price semantics, timestamp/window and units before comparing evidence. Unresolved material conflict must be disclosed and blocks any dependent high-consequence conclusion.

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
Precedence: current runtime/project authority → V4 security invariants → active Stable release contract → domain policy → verified current evidence → skill-pack/provider evidence precedence → scoped verified memory → external reference knowledge. Material unresolved conflict blocks promotion and must be disclosed during normal reasoning when relevant.

## Long-term rule
Do not redesign the brain merely to add knowledge. Add or improve a domain node, bridge, skill pack, provider registry, adapter, eval, source policy or capability release; let Evergreen validate it; promote only a verified immutable release.

## Compatibility
`GITHUB_BRAIN_V3`, `GITHUB_BRAIN_V2`, and `GITHUB_BRAIN_V1` are compatibility activation aliases that resolve to this V4 authority. Their legacy files contain redirect semantics only after V4 promotion.
