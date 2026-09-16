# Universal Brain Fabric — Approved Architecture

> **Status: APPROVED DESIGN / NOT IMPLEMENTED**
>
> Approved by the user on 2026-09-16. This document extends `GITHUB_BRAIN_V4`; it does not replace the existing Brain, router, skill registry, Model Mesh, Evergreen plane, release gates, Trading authority, or zero-cost safety contract.

## 1. Goal

Make ChatGPT, Claude, Gemini, OpenCode, mobile clients, browser agents, and future AI clients operate as adapters into one canonical GitHub Brain rather than as independent reasoning authorities.

The target behavior is:

- FAST requests remain zero-RTT and use the last verified HOT snapshot;
- STANDARD/DEEP/high-impact requests route through the cloud Brain gateway;
- all clients share promoted project/memory/skill/capability state while retaining separate raw chat sessions;
- the Brain continuously discovers, evaluates, assimilates, and improves useful capabilities without creating a parallel authority or widening permissions;
- GitHub remains canonical authority while runtime state is served from a portable cloud state layer;
- normal operation remains cloud-first and zero-local.

## 2. Architectural decision

Use a **Hybrid Universal Brain Fabric** built as an incremental extension of the current V4 architecture.

```text
ChatGPT ─┐
Claude ──┤
Gemini ──┤
OpenCode ┤
Mobile ──┤
Future ──┘
    │
    ▼
Universal Entry Adapter Contract
    │
Intent + Risk + Freshness Classification
    │
    ├── FAST ──> verified HOT snapshot, zero network routing RTT
    │
    └── STANDARD / DEEP / HIGH-IMPACT
              │
              ▼
        Cloud Brain Gateway
              │
              ▼
        GITHUB_BRAIN_V4
              │
       task_router + profile
              │
      exactly one primary skill
      + validated execution capsule
              │
        capability requirements
              │
      memory / RAG / tools / sources
              │
          Model Mesh workers
              │
        checker / grader as policy allows
              │
          Brain synthesis
              │
          client adapter
```

Rejected alternatives:

1. **Hard online gateway for every request** — rejected because it violates the existing zero-network FAST contract and creates an unnecessary availability bottleneck.
2. **Independent client brains** — rejected because it fragments memory, authority, routing, and skill ownership.
3. **Cloud database as primary authority** — rejected because runtime state must not outrank GitHub release/checkpoint authority.
4. **Full raw-chat synchronization across clients** — rejected because it increases privacy/context noise and creates unnecessary coupling.
5. **Unrestricted autonomous promotion** — rejected because high-risk, credential, financial, destructive, and permission-expanding changes must remain explicitly gated.

## 3. Non-negotiable invariants

| Invariant | Contract |
|---|---|
| Single Brain authority | `GITHUB_BRAIN_V4` remains the sole routing/reasoning authority. Clients, models, providers, plugins, and upstream repos are adapters/workers/evidence only. |
| Mandatory canonical routing | STANDARD/DEEP requests pass through `task_router`, exactly one profile, one primary skill, and the validated execution capsule before provider/model selection. |
| FAST zero-RTT | FAST uses only the last verified exact-SHA HOT snapshot for route/skill/capsule selection. No synchronous GitHub/provider/network routing call. |
| Safe degraded fallback | If the cloud Brain is unavailable, only safe requests may continue from the last verified Stable snapshot. Live/trading/deploy/credential/high-impact requests fail closed or defer according to policy. |
| No majority vote | Conflicting model/provider outputs do not gain truth by vote count. |
| No parallel skill authority | New capabilities strengthen an existing canonical skill first; aliases/adapters are preferred over duplicate primary skills. |
| GitHub canonical authority | Code, policies, stable skill definitions, releases, promotion history, checkpoints, and permission ceilings remain GitHub-authoritative. |
| Runtime state is subordinate | Cloud state, vector indexes, caches, and telemetry are derived runtime material and cannot self-promote into canonical authority. |
| Zero-cost core | Model Mesh never uses paid fallback, auto-purchase, trial-credit-as-free, or unverified billing spillover. |
| No permission widening | Continuous learning/discovery cannot grant credential, financial, wallet-signing, destructive production, or broader write authority. |
| Trading unchanged | Universal entry and learning layers cannot silently replace Trading project authority or grant live execution. |
| No hidden reasoning persistence | Never persist chain-of-thought, private reasoning traces, credentials, secrets, or private provider payloads. |
| Cloud-first / zero-local | Normal use must not require the user's workstation, local CLI, local MCP, or local model host. |
| Exact-SHA production closure | Stable promotion requires tests, validators, release artifact generation, CI, merge, deploy, canary, and exact-main production verification. |

## 4. Universal Entry Adapter Contract

Every integrated client implements the same logical adapter contract.

Minimum request envelope:

- `client_id`
- `adapter_version`
- `session_id`
- `request_id`
- `user_input`
- declared client capabilities
- available tool classes
- optional project hint
- optional freshness requirement
- optional attachment/resource descriptors
- authentication principal and scoped permissions

Minimum response envelope:

- selected profile (`FAST`, `STANDARD`, `DEEP`)
- selected primary domain
- selected canonical primary skill ID
- execution capsule hash/version
- freshness/degraded-state metadata when material
- result payload
- bounded citations/evidence references when applicable
- sanitized observability metadata

Adapters must not choose the final reasoning authority, bypass the primary-skill contract, or self-promote client-specific instructions above Stable project/security authority.

Initial adapters:

1. ChatGPT
2. Claude
3. Gemini

The contract must support future adapters without changes to Brain core.

## 5. Hybrid routing policy

### 5.1 FAST

FAST remains local-to-adapter or edge-snapshot routing from the last verified HOT snapshot.

FAST contract:

- zero online Brain routing RTT;
- no GitHub refresh;
- no provider discovery;
- no durable-memory preload;
- no tool preload;
- no bridge node;
- exactly one primary skill + capsule;
- escalation when intent, freshness, risk, or capability requirements exceed FAST limits.

A FAST adapter may emit sanitized local route metadata asynchronously, but telemetry delivery must never become a synchronous dependency.

### 5.2 STANDARD

STANDARD goes through the cloud Brain gateway and may use bounded project/domain context, memory retrieval, tools, sources, and up to the existing policy limits for supporting skills/bridge nodes.

### 5.3 DEEP

DEEP goes through the cloud Brain gateway and may use bounded planning, task graphs, maker/checker, independent grading when required, artifact pyramids, richer retrieval, and bounded parallel workers under current V4 budgets.

### 5.4 Mandatory escalation classes

The following cannot remain cached FAST when current state materially matters:

- live market/account/runtime state;
- Trading decisions requiring current data;
- deployment/runtime mutation;
- credential-sensitive actions;
- destructive or irreversible actions;
- financial/wallet actions;
- current production health verification;
- materially time-sensitive external facts;
- permission changes;
- tasks whose primary skill/capsule cannot be proven from the verified HOT snapshot.

## 6. Safe degraded fallback

When the cloud Brain gateway is unavailable:

- FAST continues from the last verified HOT snapshot;
- safe STANDARD/DEEP informational requests may fall back to the last verified Stable snapshot with bounded local/client context;
- responses must disclose degraded/freshness state when material;
- live/trading/deploy/credential/financial/destructive/high-impact flows must not bypass the Brain;
- no candidate, stale runtime cache, or client-local guess may become substitute authority;
- recovery returns to the newest verified Stable production release, never a partially deployed candidate.

## 7. Shared Brain State

Use one **Shared Brain State** for promoted project and knowledge state, while preserving client-local session histories.

Shared state includes:

- promoted memory records;
- project authority summaries and current checkpoint pointers;
- canonical skill/capability/reputation metadata;
- runtime health overlays;
- retrieval indexes;
- approved knowledge graph/wiki representations;
- candidate memory metadata;
- sanitized route/quality telemetry;
- upstream watch state;
- promotion/eval outcomes.

Not shared by default:

- raw full conversation transcripts;
- hidden reasoning;
- private provider payloads;
- secrets/credentials;
- client-private temporary scratch state.

A client may contribute derived candidates to Shared Brain State, but candidates have zero authority until promoted by the canonical lifecycle.

## 8. Portable cloud state abstraction

GitHub remains canonical authority. Runtime speed comes from a portable storage abstraction with Cloudflare as the first backend.

Logical interfaces:

- `StateKV` — compact runtime state/cache/leases;
- `MetadataStore` — relational metadata, lifecycle records, provenance, promotion state;
- `VectorIndex` — semantic retrieval for approved memory/knowledge;
- `ObjectStore` — immutable larger evidence/snapshots/artifacts;
- `TaskQueue` — background learning, consolidation, revalidation, upstream watch;
- `LeaseLock` — dedupe/concurrency controls for update-plane workers.

Cloudflare may implement these with Workers and whichever managed primitives best fit each interface, but Brain code must depend on the abstraction rather than Cloudflare-specific semantics.

Future Postgres/Qdrant/Redis/S3-compatible adapters may be introduced without changing Brain authority logic.

## 9. Client authentication and scoped permissions

Each adapter/client receives its own credential and principal.

Required properties:

- independent revoke;
- independent rotation;
- explicit scopes;
- per-client audit identity;
- no shared master key across all clients;
- secrets held only in approved cloud secret stores;
- fail closed on unknown or excessive scope.

Representative scopes:

- `brain.route`
- `brain.read_context`
- `brain.submit_candidate_memory`
- `brain.use_research_tools`
- `brain.read_runtime_health`
- `brain.request_deploy_action`
- `brain.request_trading_read`

High-risk scopes do not imply autonomous execution permission; existing risk/authorization gates still apply.

## 10. Memory lifecycle

Every completed task may generate **candidate memory**, never immediate canonical memory.

Lifecycle:

```text
observation
→ candidate
→ normalize + provenance
→ dedupe/overlap
→ conflict check
→ evidence/freshness/importance evaluation
→ pending/confirmed decision
→ active
→ superseded / archived / tombstoned
```

Memory candidates should capture compact durable facts, preferences, project decisions, validated procedures, and reusable conclusions—not raw reasoning traces.

Promotion factors include:

- source/provenance strength;
- repetition/consistency;
- project authority;
- importance/reuse value;
- freshness contract;
- conflict status;
- risk class;
- user confirmation where required.

Current project/runtime authority outranks promoted memory. Superseded records remain traceable but must not continue routing as active truth.

## 11. RAG, knowledge consolidation, and Auto-Wiki

Shared Brain retrieval should evolve from file lookup into a bounded knowledge lifecycle:

- exact lookup first;
- hybrid semantic + lexical retrieval where useful;
- reranking under bounded budgets;
- provenance-preserving snippets;
- revision-aware knowledge nodes;
- knowledge graph links for entities, projects, capabilities, skills, decisions, and evidence;
- Auto-Wiki style synthesized pages generated only from traceable approved source material;
- rollback/revision history;
- stale/contradicted material marked rather than silently merged.

Generated summaries are derived views, not authority above their sources.

## 12. Continuous Capability Assimilation

Extend the existing Evergreen/Continuous Intelligence plane rather than adding a second update system.

### 12.1 Source classes

1. **Whitelisted upstreams** — monitored on schedule.
2. **Candidate upstreams** — newly discovered sources with zero authority until admitted.

### 12.2 Intake pipeline

```text
source discovery
→ provenance
→ license/usage status
→ maintenance status
→ security posture
→ capability extraction
→ normalization
→ overlap/duplicate scan
→ conflict scan
→ permission-ceiling scan
→ eval design
→ quarantine
→ benchmark/regression replay
→ canary
→ Evergreen promotion
```

Sources with unresolved license, hidden permission expansion, credential material, unverifiable runtime claims, duplicate reasoning authority, unbounded execution growth, or critical unresolved security risk cannot become Stable authority.

## 13. Upstream Watch and capability diff

Maintain an **Upstream Watch ledger** containing:

- upstream repository/source;
- pinned revision/version;
- license/usage state;
- maintenance state;
- last checked timestamp;
- relevant capability map;
- current assimilated capability coverage;
- newly detected capability candidates;
- conflicting/deprecated capability signals;
- eval status;
- promotion state.

Whitelisted sources are refreshed according to Continuous Intelligence policy. Candidate discovery may propose new upstreams automatically, but admission requires full harmonization gates.

The diff should answer:

- What useful capability appeared upstream?
- Do we already have an equivalent canonical capability?
- Can the existing skill be strengthened instead of creating a new skill?
- What measurable gain is expected?
- What permission/security/runtime cost changes?
- Is the source current and legally usable?

## 14. Skill Forge and self-refinement

Use the existing learning/skill-factory/skill-evo policies as one pipeline.

Inputs:

- capability gaps;
- repeated task failures;
- regression cases;
- user corrections;
- upstream capability diffs;
- observed latency/context bottlenecks;
- model/provider capability evidence.

Pipeline:

```text
gap/failure
→ improvement candidate
→ strengthen canonical skill OR create distinct skill candidate
→ generated tests/evals
→ sandbox
→ regression replay
→ benchmark
→ harmonization checks
→ canary
→ promotion class decision
```

Autonomous promotion:

- Class A: allowed when all gates pass;
- Class B: allowed when all gates pass;
- Class C: requires explicit approval;
- Class D: requires explicit approval and cannot widen protected permissions automatically.

No autonomous process may grant credential access, financial execution, wallet signing, destructive production action, or broader production writes.

## 15. Failure-driven learning

Failure intake is event-driven and stores only observable, sanitized evidence.

Minimum failure record:

- failure ID;
- domain;
- failure class;
- observable symptom;
- expected outcome;
- evidence reference;
- timestamp;
- affected release/snapshot/client/skill when known.

The system must never store hidden chain-of-thought, secrets, credentials, private tool payloads, or raw private prompts as learning data.

Failures may create candidates for:

- route correction;
- skill correction;
- retrieval correction;
- provider/model capability correction;
- new evals;
- memory supersession;
- upstream investigation.

A failure is evidence, not automatic proof of a proposed fix.

## 16. Model Mesh optimization and recovery

The Universal Brain Fabric reuses Model Mesh as the worker layer.

Required behaviors:

- per-model zero-cost eligibility;
- free→free failover only;
- provider cooldown and self-reentry;
- stale evidence quarantine;
- model-family dedupe;
- capability-correct endpoint probing;
- bounded discovery/probing;
- current pricing/entitlement revalidation;
- provider failure != Brain failure;
- no provider/model becomes routing or reasoning authority;
- non-chat capabilities are routed only through compatible execution adapters.

Provider health and capability evidence may affect worker ranking but never override project/security/permission authority.

## 17. Observability and audit

Use sanitized structured telemetry sufficient for operation and debugging without retaining sensitive payloads.

Track at least:

- client/adapter ID;
- request/profile/domain/primary-skill identifiers;
- capsule/release/snapshot hashes;
- route latency;
- tool/provider/model family used;
- cache/retrieval hit/miss;
- fallback/degraded state;
- memory candidate/promote/supersede events;
- upstream diff/promotion events;
- skill evolution/eval outcomes;
- provider failure/cooldown/recovery;
- deployment/release/canary status;
- permission/scope denials.

Do not log:

- chain-of-thought;
- secrets or credentials;
- private provider payloads;
- full raw user conversations by default;
- raw sensitive tool payloads.

Operational views should support per-client, per-domain, per-skill, per-provider, and per-release diagnosis.

## 18. Automatic recovery

Recovery is layered:

1. provider/model error → bounded failover/cooldown under Model Mesh policy;
2. retrieval/state backend error → fallback to verified cached/Stable material where safe;
3. adapter error → isolate/revoke only the affected adapter;
4. update-plane regression → rollback candidate/promotion without disturbing Stable;
5. Stable production regression → existing release rollback chain and exact-SHA verification;
6. cloud Brain outage → safe degraded fallback only for permitted classes.

Protected regression dimensions (`correctness`, `authority`, `security`, `verification`, `project_isolation`) have zero tolerance and trigger rollback/blocking according to current policy.

## 19. Data retention and privacy defaults

Use data minimization by default.

- raw client sessions remain client-local unless explicitly imported for a task;
- Shared Brain State stores normalized/promoted knowledge, compact candidate metadata, provenance, and sanitized telemetry;
- temporary execution context expires according to runtime policy;
- superseded memory is retained only as bounded audit/history metadata where needed;
- secrets never enter memory/vector indexes;
- SECRET-class material is never sent to external workers;
- retention configuration must be centrally policy-controlled rather than hard-coded in adapters.

## 20. Rollout strategy

Use staged canary rollout, not a big-bang switch.

Recommended order:

1. core contracts + schemas + validators;
2. portable state interfaces with Cloudflare backend;
3. Universal Entry gateway core;
4. FAST snapshot bootstrap compatibility;
5. ChatGPT adapter;
6. Claude adapter;
7. Gemini adapter;
8. shared memory candidate pipeline;
9. retrieval/knowledge consolidation;
10. observability dashboard/telemetry;
11. upstream watch/capability diff;
12. Skill Forge/self-refinement automation;
13. future adapter SDK/contract;
14. canary expansion and production closure.

Each stage must preserve last-known-good Stable behavior and be independently rollbackable.

## 21. Implementation boundaries

This phase may add adapters, contracts, storage abstractions, worker/background jobs, schemas, validators, tests, release metadata, and cloud runtime endpoints required by the design.

This phase may not:

- replace `task_router` with a new router;
- create a second skill registry or memory authority;
- make a provider framework the reasoning authority;
- alter Trading execution authority without a separate explicit design;
- grant new production/destructive/credential/financial permissions;
- convert paid/trial capacity into eligible zero-cost workers;
- require user-local installation for normal use;
- store hidden reasoning;
- weaken current exact-SHA deployment and release verification.

## 22. Verification strategy

Implementation uses test-first discipline.

Required verification layers:

1. unit tests for adapter envelopes, routing classification, state interfaces, memory lifecycle, scopes, and degraded behavior;
2. contract tests proving all adapters normalize into one Brain request contract;
3. regression tests preserving FAST zero-network behavior;
4. security tests for scope isolation, SECRET external=0, permission ceilings, and fail-closed unknowns;
5. memory tests for candidate-only intake, conflict handling, supersession, and no raw reasoning persistence;
6. upstream tests for provenance/license/quarantine/overlap/conflict gates;
7. skill-promotion tests for A/B autonomous and C/D approval-required behavior;
8. Model Mesh tests preserving zero-cost and family-dedupe invariants;
9. backend portability tests against interface fakes plus Cloudflare adapter;
10. CI through the single canonical validator entrypoint;
11. release artifact generation through existing release tooling;
12. canary deploy;
13. production health and route probes;
14. FAST/SECRET boundaries;
15. exact-SHA production gate;
16. rollback proof where applicable.

## 23. Definition of Done

The Universal Brain Fabric is complete only when all of the following are verified:

- ChatGPT, Claude, and Gemini adapters implement the same canonical entry contract;
- a future adapter can be added without modifying Brain core;
- FAST demonstrably keeps zero online routing RTT and uses a verified HOT snapshot;
- STANDARD/DEEP route through the cloud Brain and cannot bypass primary-skill/capsule selection;
- safe degraded fallback works and high-impact classes fail closed;
- each client has isolated scoped credentials and independent audit identity;
- GitHub remains canonical while runtime state uses the portable storage interfaces;
- Shared Brain State is accessible across clients without raw-chat merging;
- candidate memory lifecycle, supersession, provenance, and conflict handling are operational;
- retrieval/knowledge views preserve source traceability;
- upstream watch detects useful changes without auto-authorizing new sources;
- Skill Forge can generate/evaluate improvements and auto-promote only eligible low-risk classes;
- no high-risk permission expansion auto-promotes;
- Model Mesh zero-cost/no-paid-fallback invariants remain intact;
- sanitized observability makes route/skill/provider/memory/promotion/recovery state diagnosable;
- CI, canary, production health, security boundaries, and exact-SHA gates pass;
- the release is marked known-good only after post-merge production verification.

## 24. Success outcome

After completion, the user can open any supported client and receive behavior governed by the same canonical Brain state and policies without manually naming models, providers, skills, or profiles.

The system can continuously learn from validated outcomes, monitor approved upstreams, discover candidate capabilities, evolve skills, consolidate memory/knowledge, and optimize worker selection while preserving one authority chain, bounded risk, zero-cost provider rules, cloud-first operation, rollback safety, and exact-SHA production verification.
