# STACKHUB High-Value Live Markets Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make STACKHUB continuously discover and prioritize legitimate higher-value AI-suitable work, enable TaskForce's verified application/submit lifecycle, complete MoltJobs bid lifecycle support without buying credits, and deploy the safe live-capable runtime to the VPS.

**Architecture:** Keep the existing source-agnostic pool/orchestrator. TaskForce uses application -> pending award -> accepted -> solve -> verify -> submit; MoltJobs uses free-bid -> pending award -> assigned -> solve -> verify -> submit. Discovery remains broad, while ranking favors expected realized USD per worker-minute and can apply a configurable high-value preference without discarding lower-value fallback work.

**Tech Stack:** Python 3.12+, asyncio, httpx, SQLite, Typer, pytest, GitHub Actions, systemd.

**Spec:** `docs/superpowers/specs/2026-09-11-stackhub-v2-multithread-revenue-engine-design.md`

## Global Constraints
- `external_spend_limit_usd == 0` always.
- Never buy MoltJobs bid credits or pay certification/task-unlock fees automatically.
- No wallet private keys/seed phrases/spending authority.
- Only current officially documented agent APIs may mutate marketplace state.
- Every deliverable must pass verification before submission.
- Realized payout is the only authoritative revenue metric.
- Start with `max_active_claims: 1`; increase only after a real successful cycle.

---

### Task 1: Lock current official API contracts with tests
**Files:** `stackhub_v2/tests/test_external_market_adapters.py`, `stackhub_v2/src/stackhub/adapters/taskforce.py`, `stackhub_v2/src/stackhub/adapters/moltjobs.py`
- [ ] Add contract tests for TaskForce redirect-safe discovery, apply, notification award polling, submit and earnings.
- [ ] Add contract tests for MoltJobs Bearer auth, free-bid request, assignment polling, heartbeat and submit semantics supported by current official docs/CLI.
- [ ] Run focused tests; keep mutation disabled if any contract cannot be verified.

### Task 2: Enable verified TaskForce live lifecycle
**Files:** `stackhub_v2/config/sources.live.example.yaml`, `stackhub_v2/src/stackhub/adapters/taskforce.py`, deployment workflow.
- [ ] Use canonical `https://www.task-force.app` base URL and redirect-safe client.
- [ ] Enable `auto_claim`, `auto_execute`, `auto_submit`, and payout observation only in deployment/live config, not checked-in safe config.
- [ ] Preserve PENDING applications until creator accepts; never solve before acceptance.
- [ ] Poll earnings/notifications without withdrawing funds.

### Task 3: Complete MoltJobs zero-spend bid lifecycle
**Files:** `stackhub_v2/src/stackhub/adapters/moltjobs.py`, tests, live config.
- [ ] Use current official authentication contract.
- [ ] Implement free-bid request and assignment polling; if certification or free-bid allowance blocks a job, leave it eligible/read-only rather than spending.
- [ ] Implement heartbeat for assigned work and verified submit path.
- [ ] Never invoke bid-credit purchase or wallet withdrawal.

### Task 4: Prefer higher-value work without starving the queue
**Files:** `stackhub_v2/src/stackhub/revenue_scoring.py`, config/tests as needed.
- [ ] Add tests proving $10-$100+ work with comparable success/reliability outranks tiny rewards.
- [ ] Keep expected realized revenue per worker-minute, acceptance probability, competition and payout reliability in ranking.
- [ ] Do not invent a minimum reward that would cause idle time when only smaller legitimate work exists.

### Task 5: Deploy and verify one-task live gate
**Files:** `.github/workflows/deploy-stackhub-v2-vps.yml`, `CHECKPOINTS/STACKHUB_V2_CURRENT.md`.
- [ ] Deploy current branch and run account/source doctors plus read-only scan.
- [ ] Verify TaskForce agent status/auth and MoltJobs auth/availability without exposing credentials.
- [ ] Run at most one authenticated application/bid only after capability checks pass.
- [ ] Keep service running under systemd and verify restart/heartbeat.
- [ ] Record exact CI/runtime evidence in checkpoint; do not claim earnings until payout evidence exists.
