# STACKHUB V2 — Multithread Zero-Cost Revenue Engine Design

Date: 2026-09-11
Status: Approved in chat; written spec pending user review

## 1. Objective

Extend STACKHUB V2 from a single-source bounty scanner/worker into a continuous, multi-worker revenue engine that prioritizes legitimate paid work which AI agents are explicitly allowed to perform.

Primary business objective: maximize realized payout and payout frequency, not task count. The system targets recurring revenue opportunities but does not promise a fixed daily income.

Hard constraint: external spend is always USD 0. The system must never require funding a marketplace, paying gas from the user's wallet, purchasing ads, buying leads, staking, trading, or paying to unlock a task.

## 2. Non-goals and hard safety boundaries

The engine must not:
- use CAPTCHA bypass, fake-human interaction, fake clicks/views, survey farming, game farming, identity spoofing, IP evasion, or multi-account evasion;
- automate work on platforms whose terms require a human worker or prohibit agents/bots;
- request, store, log, or use wallet seed phrases/private keys;
- transfer funds or tokens from the user's wallet;
- auto-spend money, crypto, credits, or paid API quota;
- claim revenue or payout that is not evidenced by platform/runtime data.

Only public receiving wallet addresses may be stored for payout routing.

## 3. Revenue strategy

STACKHUB runs two independent revenue loops.

### 3.1 Active Job Loop

Discover -> normalize -> policy gate -> profitability score -> reserve/claim -> solve -> verify -> submit -> reconcile payout.

Initial source family:
- TaskBounty
- additional agent-native marketplaces only after their current API/terms are verified
- legitimate paid open-source issues where autonomous agents are explicitly permitted

Each source adapter is disabled until its contract, authentication, rate limits, claim semantics, submission semantics, and payout model have been verified.

### 3.2 Passive Service Loop

Build and publish zero-cost-to-operate services where a marketplace/protocol supports agent providers and payment-per-result or payment-per-call without requiring user-funded transactions.

Candidate services:
- repository audit
- code review / issue triage
- website technical audit
- structured research
- data normalization / cleanup

A service is promoted only after it can produce deterministic/verifiable output and can be hosted within existing free/authorized infrastructure.

## 4. Architecture

### 4.1 Source Scouts

Independent asynchronous scouts poll enabled sources at source-specific safe intervals. Scouts never mutate marketplace state. They emit normalized Opportunity records into the opportunity queue.

### 4.2 Opportunity Normalizer

Converts source-specific payloads into a common schema:
- source
- external_id
- title/summary
- reward amount and asset
- estimated USD value when safely available
- task class
- requirements
- deadline
- claim mechanism
- submission mechanism
- payout mechanism
- agent_allowed evidence
- source URL/reference

### 4.3 Policy Gate

Rejects opportunities that violate zero-spend or agent-native requirements. It also rejects tasks requiring secrets, deposits, purchases, human impersonation, prohibited automation, or wallet signing/spending.

### 4.4 Revenue Scorer

Ranking is revenue-first rather than volume-first.

Conceptual score:

`priority = expected_reward_usd * success_probability * source_reliability * payout_probability / estimated_worker_minutes`

The scorer additionally penalizes uncertain acceptance criteria, poor platform history, long payout latency, duplicate tasks, and tasks that monopolize scarce worker capacity.

Tiny tasks may be accepted for initial reputation only when idle capacity exists; they cannot displace higher expected-value work.

### 4.5 Reservation / Claim Manager

Uses a single durable ownership record so two workers cannot claim the same opportunity. Source mutations are performed only by an adapter whose mutation path is explicitly enabled.

Lifecycle:

DISCOVERED -> ELIGIBLE -> RESERVED -> CLAIMED -> SOLVING -> VERIFIED -> SUBMITTED -> PAID

Failure states:

FAILED_RETRYABLE / FAILED_PERMANENT / EXPIRED / REJECTED

### 4.6 Worker Pools

Initial concurrency ceilings:
- Scout workers: 3
- Code-fix workers: 2
- Research/data workers: 2
- Service workers: 2
- Verification workers: 2
- Submission workers: 1
- Global active paid-task ceiling: 4

These are ceilings, not guaranteed threads. Async workers remain idle when no legitimate paid work exists. Source rate limits override all concurrency settings.

### 4.7 Solver Interface

Every solver returns an artifact plus structured evidence. Solver types are isolated:
- code solver
- research solver
- data solver
- service-response solver

A solver cannot submit directly. Submission requires Verification Gate approval.

### 4.8 Verification Gate

For code tasks:
- task acceptance criteria
- repository tests
- lint/type checks when available
- non-empty diff
- secret scan
- workspace boundary validation

For research/data/service tasks:
- required schema
- citation/source checks where applicable
- completeness checks
- deterministic validation where possible
- secret/PII leakage checks

Failed verification never reaches auto-submit.

### 4.9 Submission Manager

Submits only previously verified artifacts, records source response IDs/status, uses idempotency/deduplication, and applies bounded retries to transient failures. It must not spam repeated submissions.

### 4.10 Payout Reconciler

Tracks SUBMITTED -> ACCEPTED/REJECTED -> PAID using platform evidence. Ledger fields include gross reward, asset, realized USD estimate, submitted time, accepted time, paid time, and platform reference.

No task is counted as revenue until payout is evidenced.

### 4.11 Passive Service Factory

When paid-job queues are empty, spare workers may improve or execute approved reusable services. This is lower priority than claimable high-EV paid work.

The service factory may generate service definitions and artifacts but publication adapters must obey the same zero-spend and agent-native gates.

### 4.12 Revenue Optimizer

Maintains per-source and per-task-class metrics:
- discovered opportunities
- eligibility rate
- claim success
- completion success
- verification pass rate
- acceptance rate
- payout rate
- realized revenue
- revenue per worker-minute
- median payout latency

It adjusts queue weights within configured bounds. It cannot loosen safety/policy constraints or enable spending.

## 5. Scheduling and continuous operation

The orchestrator is event-driven with periodic source polling. Priority order:
1. already-claimed tasks near deadline;
2. high-EV claimable paid tasks;
3. normal paid tasks;
4. payout reconciliation;
5. passive service requests;
6. service/product improvement while otherwise idle.

Backpressure prevents new claims when active capacity is full. Watchdog health checks detect stalled workers and release only reservations that are safe to release.

## 6. Persistence

SQLite remains the initial durable store. New tables/entities cover:
- opportunities
- reservations/claims
- worker runs
- verification events
- submissions
- payouts
- source health
- revenue metrics
- service requests

State transitions are transactional. Restarting the process must not duplicate claims or submissions.

## 7. Configuration

Required invariants:
- `external_spend_limit_usd = 0`
- wallet spend permission = none
- each source independently enabled/disabled
- mutation disabled by default for newly added sources
- source-specific poll interval and rate limit
- global active-task ceiling
- worker-pool ceilings
- bounded retry policy

Secrets are supplied only through environment/system secret storage and are never committed.

## 8. Observability

CLI/status must show real runtime state rather than a fixed dry-run banner:
- worker mode and health
- source health
- queue depths
- active claims
- tasks awaiting verification/submission
- payout pending
- paid today / 7d / 30d
- realized revenue by source/task class
- failures and last error category

Logs are structured JSON and redact credentials.

## 9. Rollout

Phase 1: finish the existing TaskBounty worker runtime wiring (CLI/orchestrator/solver boundary) while preserving zero-spend controls.

Phase 2: introduce shared queues, durable reservations, worker pools, revenue scoring, and payout reconciliation.

Phase 3: add the next verified agent-native source adapter one at a time, with contract tests and mutation disabled until verified.

Phase 4: add passive service-provider adapters only where publication/execution can remain zero-spend.

Phase 5: enable adaptive revenue weighting after enough real completion/payout observations exist.

## 10. Testing and release gates

Engineering changes follow RED -> minimum GREEN -> regression suite -> validators -> CI -> release verification.

Required test families:
- policy and zero-spend invariants
- concurrency / duplicate reservation tests
- restart recovery
- source adapter contract tests
- solver isolation
- verification failures
- submission idempotency
- payout reconciliation
- rate-limit/backoff behavior
- secret redaction
- revenue metric correctness

Live mutation for a source is allowed only when tests pass, current source terms/API are verified, required credentials are present through secret storage, and a deliberately small live-task cap is configured.

## 11. Success criteria

The system is successful when it can continuously discover legitimate agent-allowed paid opportunities, prioritize by expected realized revenue, execute multiple independent jobs concurrently within safe limits, verify before submission, reconcile actual payouts, and use idle capacity for approved passive services — all with zero external spend and no wallet spending authority.

Revenue goals are optimization targets, not guarantees. The authoritative revenue number is realized payout recorded by the reconciler.