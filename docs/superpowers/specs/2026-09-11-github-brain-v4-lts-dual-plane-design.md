# GITHUB_BRAIN_V4 LTS Dual-Plane Design

Date: 2026-09-11
Status: Proposed for implementation after user review
Branch: `github-brain-v4-lts-dual-plane`
Repository: `hanlinh227-ship-it/trading-api`

## 1. Objective

Build one long-lived AI brain architecture that can be used immediately while continuously improving itself without contaminating the active runtime.

V4 must provide two separated but interoperable planes:

1. **Stable Runtime Plane** — the production brain used for all normal user requests immediately.
2. **Evergreen Update Plane** — the autonomous research, skill-discovery, evaluation, optimization, and promotion system that continuously creates better candidates for Stable.

The system must remain GitHub-first, preserve project authority isolation, preserve Trading runtime authority, keep low-latency FAST routing, and avoid cross-domain context pollution.

V4 is intended as an LTS architecture. Future capability growth should happen through versioned skill packs, knowledge-mesh nodes, adapters, policies, and release bundles rather than repeated whole-brain redesigns.

## 2. Core Principles

1. Stable and Evergreen are separate execution authorities.
2. Evergreen may research, generate candidates, run tests, benchmark, and prepare/promote releases, but may never mutate an in-flight Stable request.
3. Stable consumes only immutable, validated release bundles through an atomic release pointer.
4. Current runtime/project authority always outranks memory, cached context, learned patterns, and external sources.
5. New knowledge does not automatically become authority.
6. New skills enter quarantine before they can participate in routing.
7. Cross-domain knowledge is connected through explicit verified bridges, not through global context dumping.
8. Low-risk declarative capability upgrades may be auto-promoted after all required gates pass.
9. High-impact executable, security, authority, financial, credential-sensitive, or destructive changes require stronger canary and rollback controls.
10. No hidden chain-of-thought is persisted. Only compact decision summaries, evidence references, test/eval results, and failure classifications may be stored.
11. Stable must remain usable if Evergreen is offline.
12. Evergreen must never widen permissions merely because a dependency, skill, or tool requests them.

## 3. High-Level Architecture

```text
User Request
    |
    v
+---------------------------+
| STABLE RUNTIME PLANE      |
| GITHUB_BRAIN_V4 LTS       |
|                           |
| task_router               |
| adaptive profile selector |
| authority resolver        |
| context scheduler         |
| knowledge mesh resolver   |
| skill-pack loader         |
| tool capability resolver  |
| planner/executor/critic   |
| verifier                  |
| security                  |
| evidence                  |
| memory                    |
+-------------+-------------+
              |
              | sanitized telemetry, failures,
              | corrections, benchmark candidates
              v
+---------------------------+
| EVERGREEN UPDATE PLANE    |
|                           |
| source scout              |
| skill scout               |
| upstream watcher          |
| knowledge curator         |
| conflict detector         |
| candidate builder         |
| eval generator            |
| benchmark runner          |
| security/license audit    |
| canary runner             |
| release promoter          |
| rollback controller       |
+-------------+-------------+
              |
              v
      immutable candidate
         release bundle
              |
      all promotion gates
              |
              v
       atomic pointer swap
              |
              v
    Stable uses new release
```

## 4. Stable Runtime Plane

Stable is the only plane allowed to answer normal user requests as the canonical brain authority.

### 4.1 Fast-path behavior

The existing FAST / STANDARD / DEEP model is preserved.

FAST remains intentionally small:

- `task_router`
- runtime-profile selection
- at most one directly relevant knowledge-mesh node
- no durable memory retrieval by default
- no project state unless the route requires it
- no Trading state for non-Trading requests
- no broad skill scan
- no Evergreen calls in the synchronous response path

STANDARD adds bounded memory, project state, tool discovery, and limited mesh bridges.

DEEP adds planner/executor/critic/verifier, deeper evidence resolution, bounded parallel task graph, and higher verification requirements.

### 4.2 Stable release consumption

Stable does not read arbitrary candidate files. It reads only:

`AI_SKILL_LIBRARY/v4/releases/current.json`

This file points to one immutable release bundle, for example:

`AI_SKILL_LIBRARY/v4/releases/4.0.17/manifest.yaml`

The manifest contains content hashes and paths for kernel, router, mesh, skill packs, policies, schemas, validators, and compatibility adapters.

Promotion is implemented as an atomic release-pointer update after the candidate bundle already exists and has passed all gates. Rollback is a pointer reversal to the last known-good release.

### 4.3 Stable cannot depend on Evergreen availability

Evergreen is not part of the user-request critical path. If the update plane fails, Stable continues using the last known-good release without degradation of normal request handling.

## 5. Evergreen Update Plane

Evergreen is a separate autonomous improvement system.

It continuously processes five classes of input:

1. verified user corrections and repeated failures;
2. Stable telemetry and benchmark results;
3. approved GitHub/upstream repositories and official documentation;
4. plugin/tool capability metadata and compatibility changes;
5. skill discovery candidates from trusted or reviewable public sources.

Evergreen produces versioned candidates, not direct Stable mutations.

### 5.1 Update cycle

```text
Discover
 -> Normalize
 -> Provenance + license check
 -> Quarantine
 -> Static/security inspection
 -> Skill/knowledge classification
 -> Conflict analysis
 -> Candidate implementation
 -> Unit/contract tests
 -> Domain evals
 -> Cross-domain regression evals
 -> Latency/context-cost evals
 -> Security/authority evals
 -> Canary
 -> Promotion decision
 -> Immutable release bundle
 -> Atomic Stable pointer update
 -> Observe
 -> Roll back automatically on protected regression
```

### 5.2 Continuous operation

Evergreen should support scheduled and event-driven GitHub Actions:

- source/upstream freshness scan;
- dependency/API compatibility scan;
- skill discovery scan;
- failure-to-eval conversion;
- candidate benchmark run;
- canary validation;
- promotion/rollback check.

The schedule is configurable by source class so stable sources are checked less frequently than fast-changing APIs or tool/plugin metadata.

## 6. Knowledge Mesh

V4 replaces the concept of one giant cross-domain knowledge pool with a **Knowledge Mesh**.

### 6.1 Domain namespaces

Each domain is isolated into a namespace, for example:

- `core`
- `engineering`
- `trading`
- `game`
- `design_2d`
- `design_3d`
- `adobe`
- `prompt_media`
- `writing`
- `academic`
- `data_docs`
- `business`

Each namespace owns:

- skills;
- stable rules;
- domain-specific sources;
- domain evals;
- domain memory candidates;
- domain tool mappings;
- conflicts/exclusions;
- authority rules.

### 6.2 Verified bridges

Domains connect through explicit bridge definitions rather than shared global preload.

Examples:

- `prompt_media <-> design_3d`
- `design_3d <-> blender`
- `engineering <-> android`
- `engineering <-> deployment`
- `academic <-> data_docs`
- `trading <-> quant_backtesting`
- `business <-> ux_ui`

A bridge defines:

- what information may cross;
- directionality;
- maximum context budget;
- source precedence;
- conflict rules;
- whether project authority is required.

No bridge may allow Trading runtime/account state to leak into unrelated domains.

### 6.3 Mesh routing

The router selects:

1. one primary domain node;
2. zero or more explicitly permitted bridge nodes;
3. one primary skill;
4. bounded supporting skills;
5. only the sources/tools attached to those nodes.

This provides multidisciplinary reasoning without globally loading every discipline.

## 7. Skill-Pack Architecture

The current flat skill catalog is migrated to versioned **Skill Packs**.

Suggested layout:

```text
AI_SKILL_LIBRARY/v4/
  skills/
    core/
    engineering/
    trading/
    game/
    design/
    adobe/
    prompt_media/
    writing/
    academic/
    data_docs/
    business/
```

Each skill pack must expose a machine-readable manifest:

```yaml
id:
version:
domain:
triggers:
excludes:
requires:
conflicts_with:
bridges:
tools:
sources:
permissions:
risk_class:
output_contract:
evals:
provenance:
license:
compatibility:
```

## 8. Autonomous Skill Discovery and Learning

When Evergreen finds a potentially useful skill, it must not append it directly to Stable.

### 8.1 Discovery sources

Candidates may come from:

- approved GitHub repositories;
- official framework/tool documentation;
- trusted plugin metadata;
- known skill registries;
- repeated user workflow patterns;
- verified failure clusters suggesting a missing capability.

### 8.2 Quarantine

Every new skill enters:

`AI_SKILL_LIBRARY/v4/evergreen/quarantine/`

Quarantine skills have no routing authority and cannot access Stable secrets, credentials, financial execution, or destructive write capabilities.

### 8.3 Admission gates

A skill can become a Stable candidate only if all applicable checks pass:

- provenance known;
- license acceptable;
- no secret-bearing content;
- no prompt-injection instructions that override system/project authority;
- no undeclared tool/network dependencies;
- schema valid;
- unique ID/version;
- no unresolved `requires` cycle;
- no unresolved conflict with existing skills;
- domain assignment resolved;
- bridge requirements explicit;
- output contract defined;
- domain evals pass;
- regression evals pass;
- latency/context budget acceptable;
- security policy pass;
- authority policy pass.

### 8.4 Automatic promotion classes

**Class A — declarative low-risk skills**
May auto-promote after all gates pass and canary shows no protected regression.

**Class B — tool adapters and executable helpers**
May auto-promote only after stronger static/security/dependency analysis, sandbox execution, compatibility tests, and canary.

**Class C — kernel/router/security/authority changes**
May be auto-generated and auto-benchmarked by Evergreen, but promotion requires a stricter release policy: two consecutive green canaries, zero protected-dimension regression, rollback snapshot, exact compatibility proof, and explicit V4 project-policy authorization for automated promotion.

**Class D — financial/credential/destructive capability expansion**
Never gains broader execution permissions solely from self-learning. Existing security and project authorization remain mandatory.

## 9. Conflict Prevention

V4 must treat conflicts as first-class data.

### 9.1 Conflict graph

Every skill and knowledge node participates in a conflict graph containing:

- duplicate capability;
- contradictory rules;
- incompatible output contract;
- incompatible tool dependency;
- version mismatch;
- domain leakage;
- project-authority collision;
- source-precedence conflict;
- permission expansion;
- latency/context bloat.

### 9.2 Resolution order

1. current runtime/project authority;
2. V4 security invariants;
3. Stable release contract;
4. domain policy;
5. verified current evidence;
6. skill-pack precedence;
7. durable memory;
8. external reference knowledge.

If a material conflict remains unresolved, the candidate cannot promote.

### 9.3 Deduplication

Evergreen should prefer extending or superseding an existing skill over creating near-duplicate skills. Similarity detection should compare triggers, tools, output contracts, sources, and eval behavior.

## 10. Self-Optimization Without Blocking Immediate Use

Stable answers the user immediately from the current release.

Evergreen receives sanitized post-run observations and may optimize in parallel through repository workflows. A later Stable request can use an improved release only after promotion.

The synchronous user path must never wait for Evergreen research, discovery, benchmarking, or candidate generation.

This provides the required behavior:

- usable now;
- optimized continuously;
- no user-request latency penalty from self-improvement;
- no partial upgrade visible to Stable.

## 11. Adaptive Router V4

The router learns from eval and telemetry without becoming opaque or unbounded.

It may adapt:

- FAST/STANDARD/DEEP profile choice;
- primary skill selection;
- supporting-skill selection;
- knowledge-mesh bridge selection;
- preferred tool among equivalent tools;
- context budget within hard limits.

It may not adapt:

- project authority precedence;
- security hard blocks;
- credential rules;
- Trading hard risk controls;
- hidden-reasoning persistence policy;
- maximum permissions.

Adaptive choices remain reproducible through compact feature/decision summaries and eval evidence.

## 12. Skill and Tool Reputation

V4 keeps bounded reputation records per capability:

- success rate;
- verification pass rate;
- latency;
- tool failure rate;
- freshness reliability;
- domain fit;
- user-correction rate;
- protected-regression history.

Reputation affects ranking among capabilities with equivalent permission and authority status. It never overrides hard policy.

## 13. Memory V4

The four-layer model remains:

- working;
- episodic;
- semantic;
- procedural.

V4 adds:

- decay by age and non-use;
- contradiction graph;
- automatic supersession when a newer verified item replaces an older item;
- confidence recalculation after successful/failed verification;
- domain namespace isolation;
- bridge-scoped retrieval;
- garbage collection of low-value redundant memories.

Secrets, credentials, private keys, raw private chat, sensitive personal information, and unreviewed runtime state remain excluded from durable memory.

## 14. Evaluation System

V4 requires a Golden Eval Suite split by domain plus global invariants.

Each domain gets representative tasks and failure cases. Global evals measure:

- routing accuracy;
- correctness;
- evidence quality;
- verification quality;
- authority adherence;
- security adherence;
- constraint adherence;
- context efficiency;
- latency efficiency;
- cross-domain contamination;
- recovery behavior.

A candidate must be compared to the currently active Stable release, not merely to a static pass threshold.

Protected dimensions must have zero material regression:

- correctness;
- authority;
- security;
- verification;
- project isolation.

## 15. Canary and Automatic Rollback

Before promotion, a candidate enters canary mode.

Canary runs use recorded/replayable non-sensitive tasks, benchmark tasks, and synthetic cases. They do not silently alter user production state.

After promotion, a health window checks protected metrics. If a protected regression is detected, the release pointer automatically rolls back to the previous known-good bundle.

Rollback must not depend on Evergreen successfully understanding the failure.

## 16. Security Model

Existing V3 least-privilege policy remains authoritative and is extended for Evergreen.

Evergreen-specific constraints:

- no Stable secret access by default;
- no credential export;
- no financial execution;
- no destructive production action as part of learning;
- quarantined skills run without privileged credentials;
- external executable content is treated as untrusted until scanned and sandbox-tested;
- source popularity does not imply trust;
- plugin/tool capability does not imply permission;
- automated promotion never grants permissions not already permitted by Stable policy.

The existing hard blocks for secret exfiltration, private key disclosure, credential logging, fabricated authorization, and bypassing hard risk controls remain unchanged.

## 17. Release Model

V4 separates brain version from capability-release version.

Architecture version:

`GITHUB_BRAIN_V4 LTS`

Capability releases:

`4.0.0`, `4.0.1`, `4.0.2`, ...

Future skill additions and optimization normally increment capability releases without requiring a V5 architecture.

A V5 should only exist if the two-plane contract itself must fundamentally change.

## 18. Proposed Repository Layout

```text
AI_SKILL_LIBRARY/
  checkpoint.json
  GITHUB_BRAIN_V4.md
  GITHUB_BRAIN_V3.md          # compatibility redirect
  GITHUB_BRAIN_V2.md          # compatibility redirect
  GITHUB_BRAIN_V1.md          # compatibility redirect

  v4/
    stable/
      kernel.yaml
      runtime.yaml
      router.yaml
      security.yaml
      memory.yaml
      context.yaml
      evidence.yaml
      reliability.yaml
      observability.yaml

    evergreen/
      policy.yaml
      discovery.yaml
      promotion.yaml
      quarantine/
      candidate_state/

    mesh/
      graph.yaml
      bridges.yaml
      domains/

    skills/
      core/
      engineering/
      trading/
      game/
      design/
      adobe/
      prompt_media/
      writing/
      academic/
      data_docs/
      business/

    evals/
      global/
      domains/

    schemas/
    validators/
    releases/
      current.json
      history.yaml
      4.0.0/
        manifest.yaml
```

Legacy root paths may remain as compatibility adapters during migration, but V4 canonical authority resolves through `checkpoint.json` and the V4 release pointer.

## 19. Git and Promotion Strategy

`main` represents the active Stable Plane.

Evergreen work is isolated into candidate branches such as:

`evergreen/candidate/<timestamp>-<capability>`

A promotion controller builds a release bundle and validates it before merging/promoting.

V4 may support automated promotion when explicitly allowed by the V4 project policy and when all class-specific gates pass. Promotion must be fail-closed: missing evidence, missing checks, unresolved conflicts, stale authority, or ambiguous permissions means no promotion.

## 20. Migration From V3

Migration must preserve current behavior before enabling autonomy.

Phase A:

- introduce V4 directory and schemas;
- copy/adapt V3 Stable policies;
- keep current routing behavior;
- create initial immutable `4.0.0` release;
- point V4 Stable to equivalent behavior;
- run full V3 and V4 compatibility suite.

Phase B:

- migrate flat skills into domain skill packs;
- build knowledge mesh and bridge rules;
- keep compatibility adapter for old catalog paths.

Phase C:

- enable Evergreen in observe-only mode;
- generate candidate skills/evals but do not auto-promote;
- validate telemetry, quarantine, and conflict detection.

Phase D:

- enable automatic Class A promotion;
- then Class B after canary evidence;
- then bounded Class C promotion only after its stricter policy is proven.

At no stage may Trading runtime authority be silently replaced by Brain authority.

## 21. Required Validators

V4 requires machine-enforced validators for at least:

- dual-plane isolation;
- one Stable brain authority;
- release-pointer integrity;
- immutable release manifest consistency;
- knowledge-mesh graph cycles and illegal bridges;
- skill manifest schema;
- duplicate/near-duplicate capability warnings;
- source provenance and license;
- conflict graph resolution;
- tool/permission declarations;
- security invariants;
- memory privacy exclusions;
- eval baseline comparison;
- promotion-class rules;
- rollback target availability;
- Trading authority preservation;
- V1/V2/V3 compatibility redirects.

## 22. Acceptance Criteria

V4 is complete only when all of the following are true:

1. `checkpoint.json` identifies V4 as canonical Brain authority.
2. Stable can answer using release `4.0.0` without Evergreen running.
3. FAST path remains lightweight and does not preload unrelated domains.
4. Stable uses an immutable release bundle selected by a release pointer.
5. Evergreen is isolated from Stable production state.
6. Evergreen can discover a synthetic new skill and place it in quarantine.
7. The synthetic skill cannot route before admission.
8. A valid Class A synthetic skill can pass gates and be promoted automatically in tests.
9. A conflicting skill is rejected.
10. A malicious/instruction-overriding skill is rejected.
11. A skill requesting undeclared privileged access is rejected.
12. Knowledge-mesh routing loads only the selected domain and permitted bridges.
13. Cross-domain contamination tests pass.
14. Memory remains domain-scoped and authority-subordinate.
15. Golden evals compare candidate vs current Stable.
16. Protected-dimension regression blocks promotion.
17. Canary failure blocks or rolls back a release.
18. Automatic rollback restores the previous release pointer.
19. Stable remains functional when Evergreen workflows fail.
20. Current Trading authority/checkpoint remains unchanged.
21. V1/V2/V3 activation aliases resolve to V4 compatibility paths.
22. Full CI, validators, security checks, domain evals, and release-integrity checks pass on `main` after merge.

## 23. Non-Goals

V4 does not attempt to:

- persist unrestricted private conversation history;
- grant itself new external permissions;
- bypass product or project authorization controls;
- treat every GitHub repository as trusted training data;
- execute arbitrary third-party scripts directly in Stable;
- make source code alone count as proof of a LIVE deployment;
- merge unresolved conflicts to preserve update velocity;
- replace domain-specific project runtime authorities with generic Brain knowledge.

## 24. Long-Term Evolution Rule

The long-term rule is:

**Do not redesign the brain to add knowledge. Add or improve a domain node, bridge, skill pack, adapter, eval, or policy; let Evergreen validate it; promote it as a new capability release.**

This is what makes V4 an LTS architecture instead of another temporary version milestone.
