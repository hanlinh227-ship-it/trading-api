# STACKHUB V2 — Continuous Multi-Source Autonomous Revenue Engine Design

Date: 2026-09-11
Status: Approved by user in chat

## 1. Objective

STACKHUB V2 is a continuous, source-agnostic, multi-worker revenue engine. It must continuously discover legitimate paid work that AI agents are explicitly allowed to perform, rank opportunities by expected realized revenue, execute multiple independent jobs concurrently, verify results, submit through permitted APIs, and reconcile real payouts.

TaskBounty is only one source adapter. No marketplace, bounty site, API marketplace, service platform, or digital-asset platform is the architectural center of the system.

Primary business objective: maximize realized payout, payout frequency, revenue per worker-minute, and source diversity while minimizing idle worker time.

Hard constraint: `external_spend_limit_usd == 0` at all times.

## 2. Continuous-work invariant

`NO_EXTERNAL_JOB != IDLE`.

When one source has no eligible job, workers switch to another source. When no external paid job has positive expected value, spare capacity moves to approved revenue-producing fallback work: paid service execution, zero-cost service/API improvement, reusable digital-asset production, listing/product improvement, or discovery of new agent-native revenue sources.

The engine may be continuously productive, but it must never claim that money is being earned continuously unless payout evidence exists.

## 3. Safety and policy boundaries

The engine must not:
- bypass CAPTCHAs or anti-bot controls;
- impersonate a human worker or falsify human activity;
- create fake clicks/views/reviews/engagement;
- evade identity, IP, account, geographic, or rate-limit restrictions;
- automate platforms whose current rules prohibit agent/bot execution;
- request, store, log, or use wallet seed phrases/private keys;
- transfer funds or tokens from the user's wallet;
- auto-spend money, crypto, credits, or paid API quota;
- pay deposits, gas, listing fees, leads, subscriptions, or task-unlock fees;
- count estimated rewards, submitted work, or pending balances as realized revenue.

Only public receiving addresses and platform payout identifiers may be stored for payout routing.

## 4. Revenue lanes

STACKHUB runs three independent but coordinated revenue lanes.

### 4.1 External Job / Bounty Lane

Discover -> normalize -> policy gate -> score -> reserve -> claim -> solve -> verify -> submit -> reconcile payout.

Examples of source classes:
- agent-native bounty marketplaces;
- agent-native task marketplaces;
- legitimate open-source bounties/issues where autonomous agent work is explicitly allowed;
- approved freelance APIs where the user's account/API permission explicitly permits automation.

Every source adapter remains read-only until current API/terms, auth, rate limits, claim semantics, submission semantics, payout semantics, and automation permission are verified.

### 4.2 Paid Service / API Lane

Build and operate zero-external-spend services where a marketplace/protocol supports providers and payment per result, request, call, or subscription without requiring user-funded transactions.

Candidate service classes:
- repository audit;
- code review / issue triage;
- website technical audit;
- structured research;
- data normalization / cleanup;
- document extraction/transformation;
- deterministic AI utilities with testable outputs.

Publication and billing adapters must obey the same policy gate as job adapters.

### 4.3 Reusable Digital Asset Lane

When higher-EV paid work is unavailable, spare workers may create or improve reusable assets that can be sold repeatedly on platforms that explicitly permit the content and automation workflow involved.

Candidate asset classes:
- code utilities/templates;
- structured datasets created from permitted inputs;
- templates and digital packs;
- stock media only where the platform explicitly permits the relevant AI-generated content and contributor workflow.

Human onboarding/KYC/tax/account actions remain human steps when required by a platform.

## 5. Source capability model

Every source has an explicit capability manifest:

- `source_id`
- `source_class`
- `agent_allowed`
- `auto_discovery`
- `auto_claim`
- `auto_execute`
- `auto_submit`
- `auto_publish`
- `auto_payout_observation`
- `requires_human_onboarding`
- `requires_kyc`
- `requires_tax_setup`
- `requires_manual_review`
- `external_spend_required`
- `mutation_verified_at`
- `terms_verified_at`
- `rate_limit_policy`

Any source with `external_spend_required=true` is ineligible. Any mutation capability defaults to false until independently verified.

## 6. Global opportunity model

All source-specific opportunities are normalized into a common schema:

- source / external_id;
- title / summary;
- task class;
- reward amount / asset / safely estimated USD;
- deadline;
- estimated worker minutes;
- requirements;
- agent-allowed evidence;
- claim/submission/payout mechanisms;
- source URL/reference;
- automation capability flags;
- source reliability and payout history.

## 7. Revenue scoring

Primary ranking concept:

`priority = expected_reward_usd * success_probability * source_reliability * payout_probability / estimated_worker_minutes`

Additional penalties:
- uncertain acceptance criteria;
- high competition;
- long payout latency;
- duplicate work;
- poor historical acceptance;
- scarce worker monopolization;
- manual intervention burden.

The optimizer may adjust ranking weights, but it may never weaken policy or zero-spend constraints.

## 8. Durable lifecycle

Canonical lifecycle:

`DISCOVERED -> ELIGIBLE -> RESERVED -> CLAIMED -> SOLVING -> VERIFIED -> SUBMITTED -> PAID`

Failure states:

`FAILED_RETRYABLE / FAILED_PERMANENT / EXPIRED / REJECTED`

Reservation and transition ownership are source-agnostic. Restarting the runtime must not duplicate reservations, claims, submissions, publications, or payout records.

## 9. Worker pools

Initial ceilings:
- scouts: 3;
- code-fix workers: 2;
- research/data workers: 2;
- service/content/asset workers: 2;
- verification workers: 2;
- submission/publication workers: 1;
- global active paid-task ceiling: 4.

These are ceilings, not guaranteed threads. Source-specific rate limits and policy override concurrency.

## 10. Continuous source scanners

Scouts operate independently of execution workers.

Suggested functional split:
- Scout A: coding/bounty/task markets;
- Scout B: research/data/service markets;
- Scout C: new-source discovery and health/terms refresh.

Scouts never mutate external marketplace state. They emit normalized opportunities into a global opportunity pool.

## 11. Solver isolation

Solver classes:
- code solver;
- research solver;
- data solver;
- service-response solver;
- content/asset solver where allowed.

A solver returns an artifact plus structured evidence. Solvers cannot claim, submit, publish, or access payout credentials directly.

## 12. Verification gate

Code work:
- acceptance criteria;
- repository tests;
- lint/type checks when available;
- non-empty relevant diff;
- secret scan;
- workspace-boundary validation.

Research/data/service/content work:
- required schema;
- source/citation checks where applicable;
- completeness checks;
- deterministic validation where possible;
- copyright/licensing checks when relevant;
- secret/PII leakage checks.

Failed verification never reaches auto-submit/publication.

## 13. Submission / Publication manager

Submits or publishes only verified artifacts. It records external IDs/status, uses idempotency/deduplication, applies bounded retries to transient failures, and never spams repeated submissions.

Mutation is permitted only for adapters whose mutation capability has been verified and explicitly enabled in runtime secret/config state.

## 14. Payout reconciler

Tracks platform evidence from submitted/accepted state to paid state.

Ledger fields include:
- source;
- opportunity/service/asset ID;
- gross reward;
- asset/currency;
- realized USD estimate;
- submitted/published time;
- accepted/sold time;
- paid time;
- platform reference.

No task, service, or asset sale is counted as revenue until payout evidence exists.

The runtime stores no wallet signing authority. Receiving-wallet support is public-address-only.

## 15. Revenue optimizer

Tracks per-source and per-task-class:
- opportunities discovered;
- eligibility rate;
- claim success;
- completion success;
- verification pass rate;
- acceptance rate;
- payout rate;
- realized revenue;
- revenue per worker-minute;
- median payout latency;
- worker idle percentage;
- source revenue concentration.

Source diversification is an optimization objective. The system should detect over-concentration and use spare discovery capacity to find independently verified alternatives.

## 16. Scheduling priority

1. already-claimed work near deadline;
2. high-EV claimable paid work;
3. normal paid work;
4. payout reconciliation;
5. paid service requests;
6. reusable asset/service execution with positive expected value;
7. service/product/listing improvement;
8. discovery and evaluation of new legitimate sources.

Backpressure prevents new claims when capacity is full. Watchdogs detect stalled workers and release only reservations safe to release.

## 17. Account and credential model

Platform accounts may require a one-time human step for registration, email/phone verification, KYC, tax forms, payout setup, account acceptance, CAPTCHA, or explicit API approval.

STACKHUB may automate post-onboarding operations only to the extent allowed by the platform's current API and terms.

Secrets are supplied only through environment/system secret storage and are never committed. The repository may store only secret names, public receiving addresses when required, and non-sensitive source configuration.

## 18. Observability

Status surfaces must show truthful runtime state:
- worker/runtime health;
- source health;
- scanner freshness;
- queue depths;
- active reservations/claims;
- verification/submission/publication queues;
- payout pending;
- paid today / 7d / 30d;
- realized revenue by source/lane/task class;
- idle worker percentage;
- source concentration;
- failure/error categories.

Logs are structured and credential-redacted.

## 19. Rollout

Phase A: make reservation/lifecycle/orchestration source-agnostic.

Phase B: enable multiple verified External Job Lane adapters one at a time.

Phase C: add Paid Service/API adapters with zero-spend provider operation.

Phase D: add reusable Digital Asset adapters where AI content and contributor automation are explicitly allowed.

Phase E: unify payout reconciliation across lanes.

Phase F: enable adaptive revenue weighting and source-diversity optimization after enough real payout observations exist.

Phase G: deploy 24/7 runtime with watchdog, crash recovery, source-health checks, and independently verified runtime status.

## 20. Testing and release gates

Engineering changes follow RED -> minimum GREEN -> focused regression -> full suite -> validators -> CI -> release verification.

Required tests:
- policy and zero-spend invariants;
- source capability gating;
- concurrency / duplicate reservation;
- restart recovery;
- source-adapter contracts;
- rate-limit/backoff behavior;
- solver isolation;
- verification failure handling;
- submission/publication idempotency;
- payout reconciliation;
- secret redaction;
- revenue metrics and source concentration;
- fallback from external work to service/asset queues.

Live mutation for any source is allowed only when tests pass, current API/terms and agent permission are verified, required credentials exist in secret storage, and a deliberately small live-task cap is configured.

## 21. Success criteria

STACKHUB V2 is successful when it can continuously search multiple legitimate revenue sources, automatically switch sources when one runs dry, execute multiple independent AI-suitable jobs concurrently, use idle capacity for approved revenue-producing fallback work, verify before any mutation/submission, reconcile actual payouts, and recover safely across restarts — with zero external spend and no wallet spending authority.
