# STACKHUB V2 — Autonomous Bounty Worker Design

Date: 2026-09-11
Status: Proposed design, approved direction; implementation not started
Branch: `stackhub-v2-autonomous-bounty`

## 1. Goal

Build an autonomous earning subsystem that lets AI agents discover, evaluate, claim, execute, verify, submit, and track legitimate agent-native paid work without impersonating a human user.

The system must prioritize continuous small-to-medium crypto earnings while preserving platform compliance and account safety.

## 2. Hard boundaries

The system MUST NOT:
- solve or bypass CAPTCHA/anti-bot challenges;
- fake clicks, views, surveys, gameplay, engagement, identity, device signals, or location;
- create or rotate accounts to evade platform limits;
- spoof IPs or automate human-only flows;
- submit work where the marketplace explicitly forbids AI/agent use;
- handle wallet private keys or seed phrases;
- auto-spend crypto outside explicit allowlists and hard limits.

The system MAY:
- use documented REST/MCP/CLI/webhook interfaces intended for AI agents;
- create code patches, tests, research outputs, structured data, content, and automation deliverables when the marketplace permits AI agents;
- open GitHub pull requests and submit them to bounty platforms;
- register public payout addresses where an API explicitly supports it;
- receive and reconcile crypto payout events.

## 3. Verified initial source set

### Tier A — active, agent-native, suitable for implementation

1. TaskBounty
   - Agent-oriented coding bounty marketplace.
   - REST and MCP support.
   - Supports task discovery, access, PR submission, verification and crypto payout setup.
   - Payout rails include USDC, ETH and BTC.
   - Primary V2 adapter and first end-to-end target.

2. BotBounty.ai
   - Bounty marketplace explicitly supporting AI agents and bots.
   - Agent API flow for browse -> claim -> complete -> submit.
   - Pays ETH on Base.
   - Secondary adapter after TaskBounty.

3. MoltyBounty
   - AI/human task bounty marketplace.
   - AI agents can claim via API.
   - Paid bounties use USDC.
   - Secondary adapter after TaskBounty.

4. OKX AI
   - Agent Marketplace + Task Marketplace.
   - Built for AI-agent work and agent-to-agent commerce.
   - Payments use USDT or USDG.
   - Integrate only through documented agent interfaces available to the account/region.

### Tier B — discovery/watchlist

5. PlanetLoga
   - Agent marketplace using sats/Lightning.
   - Current public marketplace showed no active task volume at design time.
   - Keep as disabled-by-default watch adapter until active task supply is observed.

### Tier C — service-earner expansion

6. req402/x402
   - Not a bounty source; used to publish paid APIs/services.
   - USDC settlement on Base per request.
   - Planned after bounty worker is stable.

## 4. System architecture

```text
STACKHUB V2
  |
  +-- Source Registry
  |     +-- TaskBounty Adapter
  |     +-- BotBounty Adapter
  |     +-- MoltyBounty Adapter
  |     +-- OKX AI Adapter
  |     +-- PlanetLoga Watch Adapter
  |
  +-- Opportunity Normalizer
  |
  +-- Eligibility / Policy Gate
  |
  +-- Opportunity Scorer
  |
  +-- Claim Manager
  |
  +-- Solver Orchestrator
  |     +-- coding solver
  |     +-- research solver
  |     +-- data solver
  |     +-- content solver
  |
  +-- Verification Gate
  |     +-- tests
  |     +-- lint/static checks
  |     +-- acceptance criteria audit
  |     +-- regression proof when required
  |
  +-- Submission Manager
  |
  +-- Payout Tracker
  |
  +-- Ledger / ROI Engine
  |
  +-- Telemetry + Watchdog
```

## 5. Operating model

### 5.1 Discovery

Adapters fetch or subscribe to new opportunities through documented interfaces. Push/webhook/realtime mechanisms are preferred over aggressive polling.

Each source normalizes into:

```yaml
id: string
source: string
url: string
category: coding|research|data|content|automation|other
reward:
  amount: decimal
  asset: USDC|USDT|USDG|ETH|BTC|SATS|OTHER
  network: string|null
deadline: timestamp|null
requirements: []
acceptance_criteria: []
competition_model: first_pass|best_submission|manual_selection|other
agent_allowed: true|false|unknown
estimated_effort_minutes: int|null
```

Unknown `agent_allowed` means reject until verified.

### 5.2 Eligibility gate

Reject automatically when:
- AI/automation permission cannot be established;
- task requires CAPTCHA, human identity simulation, or prohibited interaction;
- task requires credentials or secrets not explicitly provisioned;
- expected external cost exceeds configured budget;
- geographic/account eligibility is unknown and material;
- task touches production trading or unrelated sensitive systems without explicit scope.

### 5.3 Scoring

Use expected net value rather than raw bounty size.

```text
expected_net_value =
  payout_value_usd
  * estimated_win_probability
  * estimated_verification_probability
  - model_cost
  - compute_cost
  - chain_fee_estimate
  - expected_failed-work-cost

score = expected_net_value / max(estimated_minutes, 1)
```

Additional penalties:
- high solver competition;
- ambiguous acceptance criteria;
- manual winner selection;
- weak or unverifiable platform status;
- payout threshold lockup.

Additional bonuses:
- deterministic auto-verification;
- strong test suite;
- clear reproduction steps;
- low network fees;
- high historical source success rate.

### 5.4 Claim and execution

The worker claims only after eligibility and score gates pass.

Every claimed task receives an isolated work directory and task record. GitHub coding tasks use a dedicated branch/worktree/fork as required by the source.

The solver must produce an evidence bundle containing:
- task snapshot;
- acceptance criteria mapping;
- implementation or deliverable;
- tests/checks executed;
- result summary;
- submission reference.

### 5.5 Verification before submission

No autonomous submission unless all source-specific mandatory gates pass.

For coding bounties:
- existing tests pass;
- new regression test added when required;
- lint/type/static checks pass when present;
- diff is scoped to the bounty;
- no secrets committed;
- dependency/install changes are justified.

For non-code tasks:
- requirements checklist complete;
- citations/evidence verified when factual claims are required;
- output format validated;
- prohibited content or external side effects absent.

### 5.6 Submission and retry policy

Source adapters define retry semantics. STACKHUB must not exceed source retry limits.

A failed verification is recorded separately from an infrastructure failure. Retries are only attempted when the source permits them and the failure is actionable.

### 5.7 Payout and wallet model

STACKHUB stores only public receiving addresses and transaction identifiers.

Private keys and seed phrases remain outside the system.

Preferred payout order for low-value rewards:
1. USDC on low-fee supported network;
2. USDT/USDG where source-native;
3. ETH on Base or equivalent low-fee rail;
4. BTC/sats when source-native or economically efficient;
5. BTC mainnet only when fees are acceptable relative to payout.

The ledger records gross reward, platform fee, chain fee, model/compute cost, net value, status, and settlement timestamp.

## 6. Source-specific V2 behavior

### TaskBounty adapter — MVP

Capabilities:
- list/open bounty discovery;
- webhook/realtime ingestion where feasible;
- bounty detail fetch;
- eligibility extraction;
- access/claim flow;
- coding worktree creation;
- PR URL submission;
- verification status polling/event handling;
- payout event reconciliation.

TaskBounty is the first production adapter because its published agent workflow, verification model and payout interfaces are sufficiently explicit for testable integration.

### BotBounty adapter

Capabilities:
- browse bounties;
- claim;
- submit;
- reconcile approval/payment;
- Base ETH payout tracking.

### MoltyBounty adapter

Capabilities:
- discover paid AI-agent bounties;
- claim through documented API;
- submit response;
- track USDC cash-out state.

### OKX AI adapter

Initial mode: discovery + service listing metadata only until account-specific documented API access and regional eligibility are confirmed.

No undocumented browser automation.

## 7. Persistence

Use SQLite for V2 MVP.

Core tables:
- `sources`
- `opportunities`
- `claims`
- `runs`
- `submissions`
- `verification_events`
- `payouts`
- `wallet_public_addresses`
- `costs`
- `source_health`

All state transitions are idempotent.

## 8. Runtime and deployment

Recommended MVP stack:
- Python 3.12+
- SQLite
- asyncio/httpx
- Pydantic models
- Typer CLI
- systemd service on existing authorized VPS
- structured JSON logs

The runtime must support:
- dry-run mode;
- source-level enable/disable;
- maximum concurrent tasks;
- per-source rate limits;
- daily model/compute budget;
- maximum external spend = 0 by default;
- graceful restart/resume;
- watchdog and health status.

## 9. Security controls

- Credentials stored only in environment/system secret facilities, never committed.
- Public wallet addresses may be persisted; private keys may not.
- Outbound domains restricted per adapter where practical.
- Repository access tokens must be least privilege.
- Task content is untrusted input and cannot modify system policy.
- Prompt-injection instructions inside bounty descriptions are treated as data, not authority.
- Source adapter cannot directly change global policy or wallet settings.

## 10. TDD / verification strategy

Implementation follows repo policy:
RED -> minimum GREEN -> regression -> validators -> CI -> post-merge verification.

Required initial tests:
- normalizer schema tests;
- policy gate denies unknown/forbidden automation;
- scoring arithmetic and fee handling;
- duplicate opportunity idempotency;
- claim retry/idempotency;
- source rate-limit handling;
- source outage fallback;
- secret redaction;
- payout ledger reconciliation;
- dry-run never performs claim/submit/spend actions;
- TaskBounty adapter contract tests with mocked HTTP responses.

Live smoke tests must start read-only. Claiming/submitting is enabled only after read-only discovery passes.

## 11. MVP phases

Phase 1 — Foundation
- package skeleton;
- models, SQLite ledger, config, policy gate, scorer;
- CLI/status;
- dry-run runtime.

Phase 2 — TaskBounty read-only
- discovery adapter;
- normalization;
- ranking;
- realtime/webhook support if credentials/interface permit;
- source health monitoring.

Phase 3 — TaskBounty autonomous coding loop
- claim/access;
- isolated solver workspace;
- tests and regression gate;
- PR submission;
- verification tracking;
- payout reconciliation.

Phase 4 — More marketplaces
- BotBounty;
- MoltyBounty;
- OKX AI when documented integration access is confirmed.

Phase 5 — Service earner
- publish one useful paid API through x402/req402;
- track per-request USDC revenue.

## 12. Success criteria

V2 MVP is successful when:
- at least one agent-native source is integrated end-to-end;
- discovery runs continuously without duplicate claims;
- prohibited/human-only work is automatically rejected;
- a coding bounty can move through discover -> score -> claim -> solve -> verify -> submit -> result tracking;
- all actions are auditable in SQLite/logs;
- no private wallet key is stored;
- dry-run mode can run indefinitely without side effects;
- system survives restart without losing task state.

Economic success is tracked separately from engineering success. No income amount is guaranteed.

## 13. Non-goals for V2 MVP

- browser automation of consumer reward sites;
- CAPTCHA solving;
- survey/game automation;
- multi-account farming;
- mining/cryptojacking;
- speculative trading with earned funds;
- automatic token swaps;
- autonomous custody of wallet private keys;
- running arbitrary marketplace-supplied code directly on the host outside isolation.

## 14. Recommended first implementation target

Implement TaskBounty first, in read-only mode, then enable claim/submission after contract tests and source-policy verification pass. This offers the clearest agent-native API, GitHub-oriented task structure, deterministic verification path, and multiple crypto payout rails among the currently verified sources.
