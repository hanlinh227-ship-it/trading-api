# Adaptive Generalist Brain vNext — Approved Architecture

> **Status: APPROVED DESIGN / NOT IMPLEMENTED**
>
> Approved by the user on 2026-09-15. This document is the architectural contract for the next GitHub Brain phase. Approval of this design does **not** itself authorize production promotion, permission widening, live financial execution, or bypass of the existing implementation/test/deploy gates.

## 1. Goal

Any request — research, coding, analysis, design, artifact generation, automation, or multi-domain reasoning — must route itself to the capability that can actually serve it without the caller naming a model, provider, or profile.

vNext extends the current GitHub Brain rather than replacing it. The target is a large, dynamic, verified worker pool under one canonical reasoning/routing authority.

## 2. Architectural decision

Use **incremental canonical expansion** of the current GitHub Brain and Model Mesh.

Do not build a second Brain, second router, second skill authority, or second provider authority. Existing Stable contracts remain the base. New capabilities enter through the current harmonization, Evergreen, security, eval, release, and exact-SHA production gates.

Rejected alternatives:

1. **Big-bang Brain rewrite** — rejected because it creates unnecessary regression surface around a production-verified Model Mesh.
2. **OmniRoute-centric routing** — rejected because it would create a competing routing/reasoning authority.
3. **Parallel skill registry** — rejected because skill ownership must remain canonical with one owner per purpose/trigger.

## 3. Non-negotiable invariants

These inherit the current production contract and are not changed by vNext.

| Invariant | vNext contract |
|---|---|
| GitHub Brain is the single authority | External models, providers, plugins, graphs, and agent frameworks remain workers/evidence only. |
| `task_router` remains mandatory | Every request still resolves profile, domain, exactly one primary skill, and its validated execution capsule before provider/model selection. |
| No majority vote | Truth is never selected by counting model outputs. Disagreement escalates to checker/grader or is surfaced. |
| Family dedupe | Multiple providers or agents backed by the same model family count as one reasoner for independent verification. |
| FAST stays fast | Zero external workers, zero provider/network routing RTT, zero KV reads/preload on the FAST routing path. |
| SECRET external = 0 | Unknown data classes fail closed to SECRET. |
| FREE_ONLY core | No paid fallback, auto-purchase, trial-credit promotion, or sponsored-credit assumption. |
| Provider failure is not Brain failure | Empty/failed worker pools degrade gracefully; Brain routing remains operational. |
| Cloud-first / zero-local | No normal capability may require a user-local gateway, CLI, MCP server, or workstation. |
| Evidence providers are optional | TinyFish and future evidence sources never become hard Brain dependencies. |
| No permission widening | New capability discovery cannot grant new write, credential, financial, destructive, or security authority. |
| Trading authority is unchanged | vNext cannot self-grant live financial execution or silently replace current Trading project authority. |
| Production completion is exact-SHA verified | Local/CI green is insufficient; runtime revision must match canonical `main` through the existing gated deployment contract. |

## 4. End-to-end architecture

```text
User Request
  ↓
GITHUB BRAIN — SINGLE AUTHORITY
  ↓
task_router
  ↓
FAST | STANDARD | DEEP
  ↓
Primary Domain
  ↓
Exactly One Primary Skill + Validated Execution Capsule
  ↓
Capability Requirements
  ↓
Domain Skill Registry / Compatibility Adapters
  ↓
Canonical Active Candidate Index
  ↓
FREE_ONLY + Terms + Privacy + Permission + Health + Quota + Context Gates
  ↓
Legion Specialist Assignment (when useful)
  ↓
MODEL MESH
  ├─ Direct Providers
  ├─ GPT-OSS workers
  ├─ OpenRouter
  └─ OmniRoute Adapter [OPTIONAL]
  ↓
Family Dedupe
  ↓
Bounded Parallel Worker Execution
  ↓
Evidence / Checker / Grader
  ↓
Brain Synthesis
  ↓
Finished Result
```

Graphify lives in repository-understanding evidence, not in the authority chain. Ponytail lives in engineering review, not in the authority chain. Agent Skills is an import/compatibility format, not a new routing authority.

## 5. Capability contract

### 5.1 Capability taxonomy

The current `AI_SKILL_LIBRARY/v4/model_mesh/domain_capabilities.yaml` remains the canonical capability taxonomy and ranking source unless a separately approved migration replaces it.

Capabilities may include text reasoning, coding, math/quant, long context, multilingual, vision, structured output, tool calling, planning, creative writing, prompt media, research synthesis, data analysis, and low latency.

Capability metadata never gains routing authority. The primary skill/capsule remains the reasoning contract.

### 5.2 Capability Evidence Ledger

A model/provider capability must not be treated as verified merely because a provider or registry declares it.

vNext adds a **Capability Evidence Ledger**. Each measured record must include at least:

- canonical model fingerprint;
- provider and model ID;
- canonical `model_family`;
- capability name;
- benchmark/eval identifier and version;
- measured score/result;
- pass/fail threshold used;
- measurement timestamp;
- source/release SHA or immutable benchmark version;
- execution environment/protocol relevant to the measurement;
- evidence freshness state;
- provenance of the measurement.

Evidence states are:

- `VERIFIED` — current measured evidence satisfies the applicable contract;
- `PROVISIONAL` — declared or partially measured, usable only for ranking where policy permits;
- `UNKNOWN` — no usable evidence;
- `STALE` — previously measured evidence outside its freshness contract.

Provider marketing text and model-card claims may seed `PROVISIONAL` metadata but cannot create `VERIFIED` capability evidence.

### 5.3 Hard capability gating rollout

Hard filtering must not be enabled globally while capability coverage is incomplete.

For each domain/capability pair:

1. ranking may use current metadata immediately;
2. hard gating is enabled only after the active eligible pool has sufficient verified evidence coverage for that domain;
3. once enabled, a hard-required capability rejects `UNKNOWN` and `STALE` candidates;
4. a domain must not silently switch from healthy workers to zero workers merely because the registry is incomplete — promotion of the hard-gate configuration itself requires canary evidence proving acceptable coverage.

This prevents the current known problem where strict math/data capability enforcement could zero out domains whose admitted models do not yet declare/measure those capabilities.

## 6. Canonical Active Candidate Index

Dynamic discovery must never make request-time selection scan an unbounded model universe.

Evergreen builds a bounded **Canonical Active Candidate Index** from approved candidates. It is derived from the provider registries, Capability Evidence Ledger, entitlement/terms/privacy status, health metadata, quota metadata, and family identity.

The index must:

- canonicalize `provider → model → model_family → capabilities`;
- carry immutable source/version metadata;
- exclude quarantined, paid-only, trial-only, expired, stale-entitlement, disallowed-privacy, or permission-incompatible candidates;
- preserve enough rejection metadata for explainable selection;
- expose only a bounded candidate set per domain/capability;
- never become an authority above source registries, tests, Stable policy, or current runtime evidence.

FAST does not read this dynamic index at request time. STANDARD/DEEP may use the bounded current snapshot after canonical routing.

## 7. Dynamic Free Model Discovery

Discovery remains an **Evergreen-plane** process and cannot become a Stable request dependency.

Candidate sources may include:

- direct provider discovery;
- OpenRouter free catalog metadata;
- OmniRoute catalog/discovery metadata;
- approved first-party provider/model listings;
- future approved discovery adapters.

Every candidate enters quarantine first.

Promotion path:

```text
discover
→ provenance/license/usage check
→ canonical identity + family dedupe
→ FREE_ONLY entitlement verification
→ terms/privacy/permission check
→ protocol compatibility
→ live health/probe
→ capability measurement/eval
→ conflict/security review
→ canary
→ Evergreen promotion gate
→ active candidate index
```

Discovery never widens permission or makes a model active by itself.

Recurring FREE_ONLY does not include signup credit, trial credit, promotional credit, temporary sponsored credit, or an unverified regional offer. Account-specific free capacity may be eligible only while current entitlement is verified by policy.

## 8. Agent Skills compatibility layer

Agent Skills (`SKILL.md`) is an import/compatibility format for the existing Domain Skill Registry, not a new skill authority.

Intake flow:

```text
SKILL.md candidate
→ provenance/license/security scan
→ parse typed metadata
→ normalize domain/task/input/output/tools/permissions
→ overlap + trigger-owner scan
→ map to existing canonical skill where equivalent
→ alias/adapter when appropriate
→ sandbox + eval when executable
→ Evergreen promotion gate
```

Rules:

- Internet skills are never auto-installed directly into Stable.
- Scripts/references/assets are untrusted until audited.
- Equivalent candidates strengthen an existing canonical skill first.
- New primary skills remain exceptional and require unique task intent, unique contract, no trigger conflict, measurable eval gain, and full promotion approval.
- Imported skills inherit the Brain permission ceiling and cannot self-expand it.

## 9. GPT-OSS Agent Legion

The existing Legion policy/registry remains a bounded specialist execution layer under GitHub Brain.

Legion responsibilities:

- receive a Brain-authored task graph;
- select typed specialist roles based on domain/capability need;
- request model workers only through Model Mesh;
- preserve family identity and provenance;
- return structured worker results to Brain verification/synthesis.

Legion never:

- routes the original user request independently;
- creates its own provider registry;
- grants itself permissions;
- creates unbounded child-agent trees;
- treats same-family agents as independent verification.

Two agents running the same base family may improve throughput or role specialization, but they count as one family-level opinion.

## 10. Adaptive parallel execution

### FAST

Unchanged:

- external workers: `0`;
- no dynamic model discovery;
- no KV/provider read for routing;
- no Legion fan-out.

### STANDARD

Goal: use the **fewest workers necessary**.

Default execution:

- one maker worker when external execution is useful and permitted;
- add a checker only when the task/materiality contract requires it;
- maximum remains bounded by compiled Stable policy.

STANDARD must not fan out merely because more providers are available.

### DEEP

DEEP may use bounded multi-role parallelism up to compiled `max_parallel`, with family dedupe before independent verification is credited.

Possible roles include maker, specialist, researcher, critic/checker, and grader.

### Early-exit contract

Early exit is deterministic and **not confidence voting**.

Remaining workers may be ignored/cancelled only when all required conditions hold:

1. required output/schema checks pass;
2. required evidence/citations/tests are present;
3. the checker returns `ACCEPT` with no material unresolved conflict;
4. any mandatory high-impact independent grader required by Stable harmonization has passed;
5. permission/security checks remain satisfied.

If maker/checker materially disagree, early exit is forbidden. The task either escalates within its bounded budget or surfaces the unresolved conflict.

### Speculative execution

Speculative execution is **disabled by default** during initial vNext implementation.

It may be enabled later only after a provider has current quota telemetry and the compiled policy explicitly admits speculation. Admission requires current quota state `AVAILABLE`, provider-specific headroom above the configured speculative threshold, and no cooldown/quarantine. Speculation remains DEEP-only.

This prevents speculative fan-out from recreating the known free-tier quota exhaustion failure mode.

## 11. Multi-family verification

Independent verification requires distinct canonical model families.

Rules:

- same family through multiple providers = redundancy, not independent reasoning;
- same family through multiple Legion roles = role diversity, not independent reasoning;
- when only one family is healthy, results must be labeled single-family rather than cross-verified;
- disagreement across families is resolved by evidence/provenance/checking, never by majority vote.

## 12. Runtime state and scaling

### 12.1 KV use

Workers KV remains suitable for immutable/TTL-bounded snapshots, health evidence, and derived indexes where eventual consistency is acceptable.

Request-time selection must not perform O(total-discovered-models) KV reads. It operates from the bounded Active Candidate Index and only reads the minimum health/quota state required for shortlisted candidates.

### 12.2 Concurrency-sensitive state

State that requires compare-and-set, strict counters, admission control, or request coordination must not become load-bearing on KV read-modify-write semantics.

If such state becomes necessary, use a transactional coordination primitive such as a Durable Object, following the same isolation principle already used for bounded admission/circuit behavior elsewhere in the runtime.

Per-request ephemeral coordination should remain ephemeral unless observability/debugging requirements explicitly justify durable sanitized metadata.

### 12.3 Failure degradation

- stale capability evidence → candidate loses verified capability status;
- stale discovery catalog → Stable continues with last valid promoted snapshot;
- state/coordination failure → disable optional speculation/fan-out before failing the Brain;
- no eligible worker → graceful-zero worker plan, not Brain failure.

## 13. OmniRoute boundary

OmniRoute is approved only as an **OPTIONAL PROVIDER GATEWAY / DISCOVERY ADAPTER** after its security/compatibility audit.

Allowed uses:

- provider/model catalog;
- dynamic discovery;
- quota/health/latency metadata;
- provider fallback inside a Brain-bounded worker request;
- OpenAI-compatible transport;
- protocol compatibility metadata.

Not allowed by default:

- replacing `task_router`;
- becoming reasoning authority;
- autonomous `fusion`;
- autonomous `pipeline`;
- autonomous multi-model orchestration outside a Brain-authored task;
- paid fallback;
- auto-purchase;
- classifying trial/promotional capacity as recurring FREE_ONLY.

Production requirements include exact version pinning, supply-chain/security audit, cloud deployment or direct adapter use, secret-store isolation, sanitized logs, bounded timeouts, and failure isolation.

OmniRoute OFF, unavailable, empty, or stale must not break GitHub Brain or direct provider execution.

## 14. Graphify boundary

Graphify may be piloted as a **derived repository knowledge graph**.

Source authority remains:

```text
source code / tests / approved spec / current project authority
> generated graph
```

Required controls:

- `.graphifyignore` or equivalent exclusions for secrets, generated artifacts, vendor dependencies, `node_modules`, and irrelevant large files;
- source SHA attached to generated graph/index artifacts;
- stale detection;
- incremental rebuild where practical;
- no sensitive data committed into graph artifacts;
- graph mismatch with source always resolves in favor of source.

Graphify must prove measurable repository-navigation/token/time benefit before Stable promotion.

## 15. Ponytail boundary

Ponytail is a bounded **simplicity / anti-overengineering critic** inside engineering review.

It may ask whether a smaller design preserves the required contract. It may not:

- remove requirements;
- weaken security controls;
- bypass verification/tests;
- replace architecture authority;
- override current project authority;
- widen permissions.

A Ponytail recommendation is advisory evidence to the canonical engineering skill.

## 16. Security and privacy

Every new provider/plugin/skill/gateway must pass the checkpoint-resolved harmonization and Evergreen promotion gates.

At minimum:

- provenance;
- license/usage terms;
- dependency/supply-chain review where executable;
- outbound network behavior;
- telemetry/logging review;
- credential/token storage review;
- prompt/content logging review;
- SSRF/arbitrary-fetch/command-execution exposure where applicable;
- secret redaction;
- permission-ceiling validation;
- no credentials committed to the repository.

`SECRET` data remains external-zero. New adapters fail closed on unknown data/permission classes.

## 17. Promotion and release model

Do not create a second plugin approval framework.

Reuse the current Evergreen promotion contract:

- provenance;
- license;
- schema;
- conflict;
- security;
- authority;
- domain evals;
- global regression;
- context cost;
- canary.

Protected dimensions retain zero regression tolerance for correctness, authority, security, verification, and project isolation.

Architectural/kernel/router/security authority changes remain manual-approval class changes. Financial/credential/destructive/permission-expansion changes never auto-promote.

Every production promotion must retain rollback and exact-SHA runtime proof.

## 18. Implementation decomposition

This master architecture is intentionally decomposed. Implementation proceeds as bounded sub-projects; a sub-project needs a separate design only if it changes this approved architecture.

### Phase A — Capability Evidence + Active Candidate Index

- define ledger schema;
- define evidence freshness;
- compile bounded candidate index;
- keep hard capability gates off until coverage canaries pass.

### Phase B — Agent Skills compatibility

- parser/normalizer;
- quarantine pipeline;
- canonical-skill mapping/alias behavior;
- executable-skill sandbox/evals.

### Phase C — Graphify pilot

- repository snapshot graph;
- source-SHA/stale controls;
- benchmark navigation/token/time accuracy.

### Phase D — Ponytail bounded integration

- simplicity critic contract;
- regression tests proving no authority/security/verification weakening.

### Phase E — OmniRoute sandbox adapter

- pin/audit upstream;
- FREE_ONLY sandbox pool;
- catalog/discovery/quota/health/fallback tests;
- family dedupe and failure-isolation tests;
- no production authority.

### Phase F — Dynamic Free Model Discovery

- merge direct/OpenRouter/OmniRoute candidate feeds;
- canonicalize identity/family;
- entitlement/terms/privacy revalidation;
- promote only through Evergreen gates.

### Phase G — Legion runtime integration

- Brain-authored task graph;
- specialist assignment;
- Model Mesh worker allocation;
- structured result envelopes;
- family-level verification semantics.

### Phase H — Adaptive Parallel Execution

- STANDARD minimal-worker policy;
- DEEP bounded fan-out;
- deterministic early exit;
- optional speculation remains off until quota-telemetry acceptance criteria pass.

### Phase I — Production promotion

Promote capabilities individually after tests, CI, security review, canaries, exact-SHA deployment verification, and rollback proof.

## 19. Acceptance criteria

vNext is not production-complete unless all applicable criteria pass.

1. GitHub Brain remains the sole routing/reasoning authority.
2. `task_router` + exactly-one-primary-skill + capsule contract remains intact.
3. FAST still performs zero external routing/provider calls and zero dynamic state preload.
4. SECRET still executes zero external workers and unknown class fails closed.
5. No paid/trial/promotional fallback enters FREE_ONLY.
6. Provider/gateway failure never becomes Brain failure.
7. Dynamic discovery cannot mutate Stable directly.
8. Capability claims cannot become `VERIFIED` without measured evidence.
9. Stale capability evidence cannot satisfy hard capability gates.
10. Hard capability gating cannot promote until domain coverage canary proves it will not unintentionally zero the eligible pool.
11. Request-time selection remains bounded and does not scan/read every discovered model.
12. Same-family providers/agents do not count as independent reasoning.
13. Early exit cannot occur on maker/checker material disagreement.
14. Early exit is never based on majority voting.
15. Speculative execution remains disabled until explicit compiled policy + quota telemetry permits it.
16. Agent Skills candidates begin quarantined with zero routing authority.
17. Equivalent imported skills strengthen/map to canonical skills rather than creating duplicate primary authority.
18. Graphify graph with stale/mismatched source SHA is ignored in favor of source.
19. Ponytail cannot remove security, verification, or required behavior.
20. OmniRoute OFF → Brain and direct Model Mesh still work.
21. OmniRoute unavailable → Brain and direct Model Mesh still work.
22. OmniRoute zero models/stale catalog → graceful fallback.
23. OmniRoute paid/trial candidate → FREE_ONLY rejects it.
24. OmniRoute `fusion`/`pipeline` cannot self-activate.
25. No secrets appear in code, generated config, logs, graph artifacts, or worker output.
26. Trading/live-financial permission boundaries are unchanged.
27. All protected regression dimensions remain non-regressed.
28. Relevant unit/integration/validator/CI suites pass.
29. Production promotion emits exact-SHA evidence showing runtime revision equals canonical `main`.
30. Rollback remains available for every production promotion.

## 20. Explicit non-goals

- No Brain rewrite.
- No second router.
- No second reasoning authority.
- No automatic paid model use.
- No automatic financial/live-trading permission expansion.
- No mandatory local installation.
- No unlimited agent recursion.
- No truth-by-vote.
- No unbounded model catalog scan on the request path.
- No automatic execution of arbitrary Internet skills or plugin code.

## 21. Completion definition for this design phase

This architecture is approved, but **implementation has not started**.

The next step after written-spec review is to create a detailed implementation plan using the repository's current planning workflow, then execute Phase A first under test-first/verification discipline.
