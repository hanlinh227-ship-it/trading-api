# Brain V4.8 Continuous Intelligence & Autonomous Improvement — Design

## Status

Approved for implementation on 2026-09-14.

## Goal

Upgrade `GITHUB_BRAIN_V4` from an Evergreen system that can discover and promote bounded candidates into a continuously operating intelligence-improvement loop that can refresh knowledge, detect capability gaps, create candidate improvements, benchmark them against the current Stable release, convert verified failures into regression evidence, age stale knowledge, and promote only improvements that pass explicit safety and quality gates.

The system must operate without requiring the user to repeatedly request updates, while preserving the existing canonical authority chain, the `109` routed skills / `109` execution capsules baseline, zero-local operation, Cloudflare Skill Gateway contract, separate Railway live-price authority, and Trading project authority.

## Non-goals

- Do not retrain or mutate foundation-model weights.
- Do not create a second reasoning authority or independent competing Brain.
- Do not give imported repositories, external agents, plugins, providers, or models routing authority.
- Do not automatically widen financial, credential, wallet, destructive, production-write, security-bypass, or secret-access permissions.
- Do not execute untrusted upstream code merely because a source was discovered.
- Do not make the Stable request path depend on Evergreen availability.
- Do not persist hidden chain-of-thought, raw private prompts, secrets, or private tool payloads.
- Do not claim learning from production failures unless sanitized telemetry or verified failure evidence is actually available.

## Baseline

The baseline is Brain `4.7.0` on canonical `main` SHA `c561c9f29b131d20e6ac8c7c1a7beddd45c0b039`.

Brain 4.7 already provides:

- Stable Runtime Plane and Evergreen Update Plane separation.
- Scheduled GitHub discovery scan.
- Scheduled Class A candidate workflow.
- Quarantine-first admission.
- Provenance, license, security, authority, eval, canary, context-cost and regression gates.
- Atomic release pointer and rollback history.
- Skill-Mandatory Fast Gateway with exact-SHA validation.

The 4.8 change strengthens this existing architecture rather than replacing it.

## Core invariant

The Stable Runtime Plane serves requests from the last known-good immutable release. The Continuous Intelligence Engine runs only on the Evergreen Update Plane.

No Evergreen cycle may mutate an in-flight Stable request. Stable behavior changes only through a validated immutable release promotion and exact-SHA deployment verification.

## Architecture

```text
verified sources / official docs / GitHub / plugin metadata
verified user corrections / sanitized telemetry / CI failures
                         |
                         v
              Continuous Intelligence Engine
                         |
        +----------------+----------------+
        |                |                |
        v                v                v
   Source Aging      Gap Detector    Failure Intake
        |                |                |
        +----------------+----------------+
                         v
                 Research Priorities
                         v
               Discovery + Quarantine
                         v
              Normalize / Dedupe / Risk
                         v
                 Candidate Proposal
                         v
            Baseline-vs-Candidate Eval
                         v
            Security / Authority / Cost
                         v
                  Canary / Sandbox
                  /             \
               PASS             FAIL
                |                 |
                v                 v
          Eligible Promote    Reject / Record
                |                 |
                +--------+--------+
                         v
                 Evidence Memory
                         |
                         v
                    next cycle
```

## Continuous operating modes

The Engine has four distinct operating modes.

### 1. Source refresh

Purpose: keep approved knowledge and upstream references current.

Inputs:
- official documentation;
- approved GitHub repositories;
- scientific primary sources;
- plugin/tool metadata;
- source registry metadata.

Actions:
- verify provenance;
- verify license/usage status;
- compare update timestamp/version where available;
- mark sources as `active`, `stale`, `reverify`, `deprecated`, or `archived`;
- never automatically convert source popularity into trust or authority.

### 2. Gap detection

Purpose: direct research toward weaknesses instead of indiscriminately accumulating repositories.

Evidence may include:
- verified task failures;
- retry rate;
- low-quality eval cases;
- repeated tool fallbacks;
- missing verification coverage;
- stale source coverage;
- explicit benchmark weakness;
- verified user corrections.

A gap record contains only decision metadata and evidence references, not hidden reasoning.

Required fields:
- `gap_id`;
- `domain`;
- `signal_type`;
- `severity`;
- `evidence_refs`;
- `recommended_capability`;
- `created_at`.

Gap detection must fail closed when evidence is missing or fabricated.

### 3. Candidate improvement

Purpose: convert a verified gap or source update into a bounded candidate.

Candidate forms include:
- knowledge/reference refresh;
- eval additions;
- skill guidance refinement;
- retrieval improvement;
- tool-selection policy refinement;
- safe adapter/helper improvement;
- verification rule improvement.

A candidate does not gain routing authority merely by existing.

Default strategy is to strengthen an existing canonical skill or contract. A new primary skill remains exceptional and must satisfy existing uniqueness, trigger ownership, eval gain, capsule, security and authority requirements.

### 4. Candidate comparison and promotion

Every candidate is compared to the current Stable baseline.

Protected dimensions retain zero-regression tolerance:
- correctness;
- authority;
- security;
- verification;
- project isolation.

Non-protected dimensions may use bounded tolerances defined in the Continuous Intelligence contract, including latency and execution cost.

A candidate must have a measurable primary-quality gain or close a verified gap without a protected regression.

## Promotion classes

### Class A — declarative low risk

Examples:
- source metadata refresh;
- bounded knowledge refinement;
- eval cases;
- non-executable guidance;
- safe retrieval metadata.

Eligible for unattended promotion after all required gates and canary evidence pass.

### Class B — sandboxed helper/tool adapter

Examples:
- read-only helper;
- parser adapter;
- non-privileged executable verification helper.

Eligible for unattended promotion only after sandbox execution, all required gates, and canary evidence pass. No permission widening is allowed.

### Class C — kernel/router/security/authority

Examples:
- routing authority changes;
- permission-model changes;
- security-policy changes;
- kernel orchestration changes.

Brain 4.8 must not unattended-promote Class C. It may autonomously research, prepare, test, benchmark, and open an isolated candidate PR, but explicit human authorization is required before Stable promotion.

This is stricter than the prior bounded automatic Class C contract and is intentional.

### Class D — financial/credential/destructive permission expansion

Never auto-promotes. Explicit authorization remains mandatory. Continuous intelligence cannot convert a Class D capability into Class A/B/C through relabeling.

## Knowledge aging contract

Every managed source class has a freshness policy.

Default intervals:
- official docs: stale after 48 hours without revalidation when used for fast-changing software/runtime facts;
- approved GitHub repositories: stale after 48 hours for maintenance/update metadata;
- plugin metadata: stale after 48 hours;
- scientific primary sources: stale after 14 days for discovery metadata, while publication content itself remains historically valid;
- stable telemetry: event-driven and evidence-timestamped;
- user failure patterns: event-driven and evidence-timestamped.

Lifecycle states:

```text
active -> stale -> reverify -> active
                     |
                     +-> deprecated -> archived
```

A stale source can remain historical evidence but cannot masquerade as current runtime or current API truth.

## Failure-to-regression contract

Verified failures may be transformed into durable regression evidence.

Accepted input must be sanitized and contain:
- failure identifier;
- domain;
- failure class;
- observable symptom;
- expected outcome;
- evidence reference;
- timestamp.

Forbidden input:
- hidden chain-of-thought;
- secrets;
- raw private provider payloads;
- credentials;
- unsupported inferred root causes presented as fact.

The generated regression record must preserve the observable failure and expected behavior while separating verified evidence from hypotheses.

## Gap prioritization

Gap priority is determined by bounded evidence, not model intuition alone.

Minimum priority factors:
- severity;
- recurrence count;
- affected domain importance;
- verification weakness;
- source staleness;
- whether the gap blocks completion.

Security and authority failures outrank convenience, latency and token-cost improvements.

Trading and other high-consequence domains retain their project-specific authority and risk controls.

## Candidate comparison contract

The canonical Continuous Intelligence contract defines these defaults:

- `min_primary_quality_gain = 0.01` for quality-scored candidates unless the candidate fully closes a verified binary gap;
- protected regression tolerance = `0.0`;
- max relative latency regression = `0.10` unless explicitly justified by a stronger protected-quality gain;
- max relative execution-cost regression = `0.05` unless explicitly justified by a stronger protected-quality gain;
- any authority or permission expansion blocks unattended promotion;
- missing baseline evidence blocks promotion;
- missing candidate evidence blocks promotion.

Comparison output is one of:
- `promote`;
- `hold`;
- `reject`;
- `manual_authorization_required`.

## Scheduling

Brain 4.8 must operate without user prompting through GitHub Actions.

Required cadence:

- Every 6 hours: source/discovery scan and freshness report.
- Daily: candidate materialization, gap-led prioritization where evidence exists, Class A/B eligibility analysis, validation, and isolated candidate publication when there is a real diff.
- Weekly: deep intelligence audit covering stale sources, unresolved gaps, candidate backlog, protected regressions, duplicate capabilities, release health, and promotion-policy compliance.
- Event-driven: verified failure intake and regression generation when sanitized telemetry/failure evidence is provided.

Scheduled jobs must not push directly to `main`.

## Versioning

Brain 4.8 itself is release `4.8.0`.

After 4.8.0, unattended Evergreen capability releases increment the patch number within the active 4.x minor line:

- `4.8.0 -> 4.8.1 -> 4.8.2`;
- future `4.9.0 -> 4.9.1`.

The previous `4.0.x`-only automatic release increment rule is invalid once Stable is beyond `4.0.x` and must be removed.

Automatic release generation must never cross a minor version boundary. Minor-version promotion remains an explicit architectural release.

## Stable contract file

Add:

`AI_SKILL_LIBRARY/v4/stable/continuous_intelligence.yaml`

It is immutable release content and must define:
- engine mode;
- plane separation;
- schedules;
- source aging;
- gap detection fields;
- failure intake fields;
- candidate comparison thresholds;
- promotion-class autonomy;
- protected dimensions;
- permission ceiling;
- evidence/privacy constraints.

`checkpoint.json` must expose this file as `stable_continuous_intelligence_path`.

`release.py` must include this file in release manifests.

## Evergreen tool changes

`AI_SKILL_LIBRARY/v4/tools/evergreen.py` must expose pure/testable helpers for:

1. `next_patch_version(version: str) -> str`
   - accepts valid `4.x.y`;
   - increments only patch;
   - rejects non-V4 versions and malformed versions.

2. `source_lifecycle(...) -> str`
   - returns `active`, `stale`, `reverify`, `deprecated`, or `archived` from explicit metadata;
   - does not use repository popularity as trust.

3. `detect_gaps(evidence: list[dict]) -> list[dict]`
   - emits gaps only from verifiable evidence;
   - rejects rows without domain/signal/evidence reference;
   - deterministic ordering.

4. `failure_to_regression(failure: dict) -> dict`
   - emits sanitized regression evidence;
   - rejects secret/private/hidden-reasoning fields.

5. `compare_candidate(baseline: dict, candidate: dict, policy: dict) -> str`
   - enforces protected zero-regression dimensions;
   - enforces minimum gain / bounded cost and latency tolerances;
   - returns deterministic promotion decision.

The existing scan/materialize/promote flow remains available and uses the new patch-version function.

## Workflow changes

### Evergreen scan

Keep read-only permissions. Extend it to produce a freshness/intelligence-cycle report in addition to quarantine scan output.

### Evergreen candidate

Keep isolated branch + PR behavior. Before candidate publication it must:
- run the Continuous Intelligence cycle;
- run unit tests;
- run V4 validation;
- run the canonical CI validation entrypoint where practical;
- never push directly to `main`.

Class C/D candidates must not be auto-promoted.

### Weekly intelligence audit

Add a read-only scheduled workflow that validates:
- source lifecycle policy;
- unresolved gaps/candidate backlog report;
- current release freshness;
- duplicate capability protections;
- authority/permission invariants;
- release pointer consistency.

## Release and checkpoint updates

Brain 4.8 release must:
- keep `109` canonical routed skills and `109` capsules unless a separately validated capability requires otherwise;
- keep FAST zero external routing calls;
- preserve existing project authority;
- preserve separate Railway live-price research authority;
- preserve Cloudflare Skill Gateway exact-SHA deployment contract;
- include the Continuous Intelligence stable contract in the immutable release manifest;
- update the global checkpoint to describe 4.8 and continuous autonomy boundaries.

## Tests

Add a dedicated Brain 4.8 regression test module covering at minimum:

- 4.8 contract file exists and is checkpoint-resolved;
- stable vs Evergreen plane isolation;
- automatic promotion only for Class A/B;
- Class C/D manual authorization;
- `4.7.0 -> 4.7.1` and `4.8.0 -> 4.8.1` patch increments;
- malformed/non-V4 release rejection;
- source aging transitions;
- gap detector rejects unsupported evidence;
- failure-to-regression sanitization;
- candidate comparison rejects protected regression;
- candidate comparison requires evidence and measurable gain;
- workflows are scheduled and never push directly to `main`;
- release manifest includes Continuous Intelligence contract;
- current release target is `4.8.0` after final release generation.

Existing V4 tests, skill gateway tests, authority tests, routing tests and release validation must remain green.

## Rollback

The previous verified Stable `4.7.0` remains the rollback target until 4.8.0 is fully validated and deployed.

A protected regression after promotion triggers rollback without requiring root-cause completion first.

Continuous Intelligence failure must not take down Stable Runtime. If the update plane fails, the system continues from the last known-good Stable release and records the update-plane failure for later repair.

## Security and privacy

- External code remains untrusted by default.
- Source discovery never grants execution permission.
- No secrets or credentials in repository candidate state.
- No hidden reasoning is persisted.
- Sanitized telemetry only.
- Financial, wallet, credential, destructive and production-write capabilities retain explicit authorization requirements.
- Trading execution authority remains project-specific and is not modified by Brain 4.8.

## Success criteria

Brain 4.8 is complete only when all of the following are true:

1. Official spec and implementation plan are committed on the isolated feature branch.
2. Dedicated 4.8 tests demonstrate RED against the old behavior and GREEN after implementation.
3. Continuous Intelligence contract is checkpoint-resolved and included in immutable release content.
4. Evergreen patch versioning works for any active Brain 4.x minor line.
5. Scheduled scan/candidate/audit workflows operate without direct pushes to `main`.
6. Class A/B unattended autonomy is explicit; Class C/D cannot unattended-promote.
7. Source aging, gap detection, failure-to-regression and candidate comparison helpers are tested.
8. Canonical release is generated as `4.8.0` by the release tool, not by manual hashes.
9. Full Brain CI/validators pass on the feature head.
10. After merge, production deployment must be verified against exact `main` SHA before 4.8 is called production-live.
