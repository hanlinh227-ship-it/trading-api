# Skill-Mandatory Fast Gateway Design

## Status
Approved by user on 2026-09-12 for implementation planning.

## Goal
Make every request handled by GitHub Brain pass through at least one real reasoning skill before answer generation, while reducing routing latency by compiling stable routing/skill metadata into a hot exact-SHA snapshot that does not require a GitHub read on the FAST path.

## Scope
This design governs the GitHub Brain orchestration/runtime that this repository controls. It does not claim to alter or expose hidden reasoning inside the ChatGPT platform itself. The externally testable contract is the request path, selected profile, selected primary skill, applied skill execution capsule, optional supporting skills, authority/security decisions, snapshot revision, and response-quality gate.

## Non-Negotiable Request Contract
Every handled request must follow:

`request -> task_router -> runtime_profile -> primary_skill_required -> skill_execution_capsule -> optional_context/tools -> execute -> response_quality_gate -> answer`

There is no valid `request -> answer` bypass.

Rules:
- `primary_skill_count` is exactly 1 for every request.
- `task_router` remains mandatory infrastructure and does not satisfy the primary-skill requirement by itself.
- The selected primary skill must contribute an execution capsule that is applied before answer generation; attaching only a `skill_id` without applying its contract is invalid.
- A request that cannot match a specialist skill falls back to `core_reasoning`.
- `critical_thinking` may be added as a supporting skill when challenge/critique/uncertainty signals materially justify it.
- Supporting skills remain bounded by the selected runtime profile and the existing global ceiling of 2.
- Provider/tool capability is evidence or execution capability, never reasoning authority.
- Project authority, Stable security, permission ceilings, and trading hard-risk controls always outrank skill selection.

## Skill Execution Capsule
The repository currently represents domain skills through the canonical catalog plus domain manifests rather than a separate long-form body for every skill. Therefore the gateway must compile a bounded execution capsule for each selectable skill from validated source metadata.

Each capsule contains:
- `skill_id` and `domain`;
- the skill/domain `output_contract`;
- applicable `requires`, `excludes`, `conflicts_with`, and priority metadata;
- domain permissions and risk ceiling from the matching V4 skill manifest;
- declared tool/source capability names as lazy references only;
- response checks derived from the output contract and domain policy.

Capsules must not contain hidden chain-of-thought, credentials, live provider data, user secrets, or unvalidated generated instructions. They are execution constraints and quality criteria, not private reasoning transcripts.

A request fails the response-quality gate if its selected primary skill has no valid capsule in the active snapshot.

## Runtime Profiles
### FAST
Purpose: short, low-risk, single-intent questions that do not require fresh external state or project mutation.

Contract:
- exactly 1 primary skill and its execution capsule;
- 0 supporting skills;
- 0 external tool candidates by default;
- 0 durable-memory preload;
- 0 bridge nodes;
- no GitHub/network round-trip for routing or skill selection;
- routing and skill metadata come only from the last verified hot snapshot;
- if specialist routing is not eligible under the deterministic local selection contract, select `core_reasoning` rather than perform a blocking GitHub refresh.

### STANDARD
Purpose: bounded project/domain work, artifacts, ordinary research, memory-sensitive work, or requests requiring external tools.

Contract:
- exactly 1 primary skill and its execution capsule;
- 0-2 supporting skills;
- lazy-load only the matched domain/project authority, bounded memory, provider/source metadata, and tools required for execution;
- max 1 mesh bridge unless existing Stable policy is stricter;
- independent safe tool calls may run in parallel within the existing profile ceiling.

### DEEP
Purpose: architecture/protocol changes, deployment/runtime claims, live/trading work, destructive or financial actions, credential-sensitive work, and complex research.

Contract:
- exactly 1 primary skill and its execution capsule;
- 0-2 supporting skills;
- authority/security resolution is mandatory before execution;
- planner/task graph/critic/verification stages remain available;
- max 2 bridge nodes and the existing parallel-task ceiling remain unchanged;
- live/freshness-dependent tasks must never be downgraded to cached FAST behavior.

## Domain Coverage
The compiled router must preserve the current Stable domain routes and catalog coverage for:
- core/general reasoning;
- engineering/software/API/database/security/Android/web/deployment/automation;
- trading/crypto/forex/futures/indices/microstructure/risk/backtesting/MT5/live-data validation;
- game development/design/engines/AI/2D/3D;
- UX/UI/product/graphic/2D/3D/Blender/modeling/materials/lighting/rigging/animation/rendering;
- Adobe workflows;
- prompt engineering/image/video/constraints/continuity/camera/storyboard;
- writing/script/voice-over/advertising/storytelling;
- academic research/methodology/qualitative/quantitative/interdisciplinary/citations;
- data/spreadsheets/charts/reports/DOCX/PDF/slides/presentations;
- business/marketing.

Unknown domains use `core_reasoning` and may escalate to STANDARD or DEEP if tools, freshness, authority, or risk require it.

## Deterministic Local Skill Selection
FAST selection must be possible from the hot snapshot without a blocking network lookup.

Eligibility and ranking contract:
1. Normalize request text with Unicode normalization, case folding, and whitespace normalization.
2. Apply trusted internal route hints when present. User-supplied text cannot directly forge a trusted skill/domain hint.
3. Apply catalog `excludes` before positive matching; an exclusion removes that candidate.
4. A specialist candidate is eligible when at least one validated trigger/alias matches the normalized request or when a trusted internal route hint selects that domain/skill.
5. Rank eligible candidates deterministically by: trusted exact skill hint, number/specificity of trigger matches, catalog priority, then stable skill ID as final tie-breaker.
6. If no specialist is eligible, choose `core_reasoning`.
7. Profile escalation occurs independently from specialist eligibility; freshness, risk, mutation, tool, authority, live/trading, deployment, financial, destructive, and credential-sensitive signals can escalate FAST -> STANDARD -> DEEP before execution.

The implementation may add a validated multilingual routing-alias map, but aliases must be canonical repository data included in the snapshot hash/validation path; runtime-generated or provider-generated aliases cannot silently alter routing authority.

## Compiled Hot Snapshot
### Purpose
Remove repeated file-resolution overhead from the request path while keeping GitHub `main` as the canonical source of truth.

### Source Inputs
The compiler consumes the exact commit versions of:
- `AI_SKILL_LIBRARY/checkpoint.json`;
- the active release pointer and immutable release manifest;
- `AI_SKILL_LIBRARY/v4/stable/router.yaml`;
- `AI_SKILL_LIBRARY/v4/stable/runtime.yaml`;
- `AI_SKILL_LIBRARY/skills/registry/index.yaml`;
- `AI_SKILL_LIBRARY/skills/catalog.yaml`;
- V4 domain skill manifests used by selectable skills;
- the canonical multilingual routing-alias map if introduced;
- Stable authority/security identifiers and hashes required to prove the snapshot belongs to the same validated release.

Provider-detail registries, project bodies, trading handoffs, durable memory, and unrelated domain state are not embedded in the universal hot snapshot.

### Snapshot Schema
The generated artifact must include at least:
- `schema_version`;
- `source_sha`;
- `release_id` or immutable release reference;
- `generated_at`;
- `checkpoint_hash`;
- `router_hash`;
- `runtime_hash`;
- `registry_index_hash`;
- `skill_catalog_hash`;
- `domain_manifest_hashes`;
- `routing_alias_hash` when an alias map exists;
- `security_hash`;
- `authority_hash`;
- `fallback_primary_skill: core_reasoning`;
- normalized profile limits;
- normalized domain-to-skill candidate maps;
- per-skill execution capsules;
- normalized skill metadata needed for selection: id, domain, triggers/aliases, excludes, priority, requires, conflicts, output contract, and tool/source capability names.

The snapshot must not contain credentials, private provider responses, trading account state, live market data, user secrets, or hidden chain-of-thought.

## Snapshot Build and Promotion
- GitHub remains canonical authority.
- Snapshot generation occurs from an exact commit SHA after canonical V4 validators pass.
- The compiler must be deterministic for the same source SHA and source files except for `generated_at`; source/content hashes and normalized routing data must be stable.
- A snapshot is promoted only if schema validation, router validation, skill-reference validation, capsule validation, fallback-skill validation, security/authority hash validation, and regression tests all pass.
- Cloudflare receives only a validated exact-SHA snapshot.
- The runtime exposes its active `source_sha` and snapshot schema version through health/diagnostic metadata.

## Refresh and Failure Behavior
- Request handling never blocks on a GitHub refresh for FAST selection.
- A new validated snapshot replaces the previous one atomically.
- The previous verified snapshot remains available as last-known-good rollback state.
- If refresh/build/promotion fails, requests continue from the last verified snapshot where policy permits and diagnostics expose `fresh_git_context=false` or equivalent.
- No failed or partially generated snapshot may become active.
- STANDARD/DEEP may lazy-load project/provider/source data after routing; failures follow existing fail-closed or degraded-response policy depending on risk and materiality.

## Skill Selection and Execution Order
1. classify risk, freshness, mutation, tool requirement, and project-authority requirement;
2. choose FAST/STANDARD/DEEP under existing escalation rules;
3. select exactly one primary domain;
4. select exactly one primary skill under the deterministic local selection contract;
5. resolve and apply that skill's execution capsule;
6. if no specialist is eligible, use `core_reasoning` and its capsule;
7. add supporting skills only when allowed by the profile and materially useful;
8. resolve authority/security/tool gates;
9. execute;
10. run the response-quality gate;
11. answer.

Selection must honor `excludes`, `conflicts_with`, priority, required infrastructure, and domain boundaries. Multiple matching skills are ranked deterministically; there is no majority vote across providers or skills.

## Response Quality Gate
Every answer must pass a lightweight machine-checkable gate before final emission.

Mandatory checks:
- exactly one primary skill is present;
- selected skill exists in the active snapshot;
- a valid execution capsule for that skill was applied;
- selected profile is valid;
- domain and skill are compatible;
- authority/security result is not violated;
- requests requiring fresh state have not been answered solely from stale snapshot metadata;
- tool-required tasks have either executed the necessary tool path or explicitly returned a degraded/failure result;
- the final answer is non-empty;
- bounded routing/execution metadata is recorded internally.

FAST performs only these bounded checks. STANDARD/DEEP may add verification appropriate to the domain and risk.

## Internal Routing Trace
For observability, each request produces a bounded internal trace containing:
- request class/id;
- active snapshot `source_sha`;
- profile;
- primary domain;
- primary skill;
- execution capsule ID/hash;
- supporting skills;
- whether project authority was loaded;
- whether tools were required/used;
- whether fresh external state was required;
- quality-gate result;
- route latency and total gateway latency.

The trace must not expose secrets, hidden chain-of-thought, raw credentials, or private provider payloads. It records routing decisions and verifiable execution metadata only.

## Latency Requirements
The optimization target is routing overhead, not arbitrary model-generation time.

Acceptance targets under a warm runtime:
- FAST routing/skill selection must perform zero GitHub reads and zero external-network calls;
- FAST route selection p95 target: <= 25 ms inside the gateway runtime, excluding model generation and client/network transit;
- snapshot/capsule lookup should be in-memory or equivalent edge-local hot state;
- STANDARD/DEEP may perform external calls only after profile/domain/primary-skill selection;
- no provider registry or full skill catalog network fetch occurs before primary-domain selection.

If platform constraints prevent the 25 ms target in a specific environment, CI/performance evidence must report the measured number rather than silently relaxing the contract; zero external routing RTT remains mandatory.

## Safety and High-Risk Behavior
- Skill-mandatory routing never weakens security policy.
- `HIGH_RISK` capabilities remain non-auto-activating and must not gain a cloud execution path through this feature.
- Trading/live requests remain DEEP and continue to load current trading authority only after routing to Trading.
- No cached snapshot may masquerade as live market/account/runtime state.
- Credentials, wallet actions, destructive actions, and permission expansion remain governed by existing security/authorization policy.

## Compatibility
- Existing V4 checkpoint/release/mesh/provider architecture remains canonical.
- `GITHUB_BRAIN_V1/V2/V3` remain compatibility aliases to V4.
- Existing skill IDs are reused; this design does not rename domain skills.
- Existing provider registries remain lazy capability metadata.
- Existing project/trading authority files remain lazy-loaded after route selection.

## Files Expected to Change During Implementation
The implementation plan is expected to touch a focused set of files in these areas:
- V4 stable router/runtime policy to encode `primary_skill_required` for all profiles;
- skill-registry validation to reject missing/invalid fallback, capsule, or primary-skill contracts;
- a new deterministic snapshot compiler and schema/validator;
- V4 domain manifests as compiler inputs, without broad unrelated refactoring;
- an optional canonical multilingual routing-alias file if needed for reliable Vietnamese/English specialist routing;
- a generated snapshot artifact location under the V4 stable/runtime tree;
- Cloudflare gateway loader/router integration for hot snapshot use;
- CI workflow for exact-SHA compile/validate/bundle/promotion;
- observability/health fields for active snapshot revision and route metrics;
- tests for FAST/STANDARD/DEEP routing, capsule application, fallback, failure, stale snapshot, authority/security escalation, and no-network FAST behavior.

The implementation must not be coupled to the unfinished Bybit public-bridge PR; gateway work uses a separate feature branch/PR.

## Testing Strategy
TDD is mandatory for behavior changes.

Required test classes:
1. RED test proving a request cannot answer without a primary skill.
2. RED test proving a request cannot answer when a skill ID is present but its execution capsule is absent/not applied.
3. FAST specialist-match tests across representative domains and Vietnamese/English requests.
4. FAST unknown-domain fallback to `core_reasoning`.
5. FAST test that fails if GitHub/fetch/provider access occurs during routing.
6. STANDARD lazy-load tests.
7. DEEP escalation tests for architecture, deployment, live/trading, financial, destructive, and credential-sensitive intents.
8. deterministic snapshot compiler/hash tests.
9. invalid/missing skill, manifest, capsule, alias, and conflict validation tests.
10. atomic snapshot replacement and last-known-good fallback tests.
11. response-quality-gate rejection tests.
12. regression runs for existing V4 brain/router/authority/security validators.
13. performance benchmark capturing warm FAST routing p50/p95 and external-call count.

## Deployment and Rollout
1. Implement and validate on an isolated feature branch.
2. Build the snapshot from the feature head and run all V4 validators/regressions.
3. Verify real Cloudflare bundle/dry-run where the runtime integration is affected.
4. Merge only with green required checks.
5. Build/promote an exact-main snapshot.
6. Verify production health exposes the merged `source_sha` and snapshot schema.
7. Run domain-routing smoke tests and confirm a valid applied primary-skill capsule for every request class.
8. Compare routing latency and external-call count before/after.
9. Keep last-known-good snapshot available for rollback.

## Success Criteria
The feature is complete only when all conditions are proven:
- 100% of tested request classes have exactly one primary skill;
- 100% of tested requests have a valid applied execution capsule for that primary skill;
- no FAST request uses GitHub or external-network access for routing/skill selection;
- unknown intents safely fall back to `core_reasoning`;
- representative Vietnamese and English requests route to appropriate specialist skills or the explicit safe fallback;
- STANDARD/DEEP retain lazy loading and existing authority/security behavior;
- live/high-risk tasks do not downgrade to FAST;
- active snapshot is traceable to an exact canonical GitHub SHA;
- invalid snapshots cannot activate;
- all existing V4 validators and regression tests pass;
- production exposes active snapshot revision and routing metrics;
- measured warm FAST p95 routing overhead is reported and targeted at <= 25 ms;
- no credentials, private provider payloads, live market state, or hidden chain-of-thought are stored in the snapshot, capsules, or routing trace.

## Explicit Non-Goals
- Replacing the ChatGPT platform model or its hidden reasoning.
- Preloading every skill body, project, provider, memory item, or tool for every request.
- Turning provider output into reasoning authority.
- Adding new trading strategies or modifying current trading authority.
- Expanding high-risk permissions.
- Coupling universal routing availability to Evergreen synchronization or live provider health.
