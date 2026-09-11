# STACKHUB V2 — TaskBounty Read-Only Scanner

Plan 1 implements a **strictly read-only, zero-spend** foundation for discovering legitimate AI-agent coding bounties. It does not claim tasks, request repository access, submit fixes, configure payout addresses, or move crypto.

## Safety invariants

- `dry_run` must remain `true`.
- `external_spend_limit_usd` must remain `0`.
- TaskBounty source must remain `read_only: true`.
- Only `GET /api/v1/tasks` is implemented.
- CAPTCHA/human impersonation/fake engagement/location spoofing/wallet-secret tasks are denied.
- Task descriptions are untrusted data and cannot alter runtime policy.
- Wallet private keys, seed phrases, and mnemonics are never requested or stored.
- Production trading services are outside this subsystem.

## What it does

1. Polls the documented TaskBounty open-task endpoint.
2. Normalizes opportunities into typed models.
3. Applies deny-by-default agent/compliance policy.
4. Estimates expected net value and USD/minute score.
5. Upserts opportunities idempotently into SQLite.
6. Records source health and emits redacted status output.

## Install

```bash
cd stackhub_v2
python -m venv .venv
. .venv/bin/activate
python -m pip install -e '.[test]'
```

## Test

```bash
pytest -q
```

## Commands

```bash
stackhub status --db runtime-data/stackhub-v2.db
stackhub scan-once --config config/sources.yaml --db runtime-data/stackhub-v2.db
stackhub opportunities --db runtime-data/stackhub-v2.db --limit 20
stackhub run --config config/sources.yaml --db runtime-data/stackhub-v2.db
```

`TASKBOUNTY_API_KEY` is optional for public discovery and, if present, is read from the process environment only. It is never written to SQLite or telemetry.

## Current TaskBounty economics

The adapter normalizes `bounty_cents` to the documented solver share (80% of the funded bounty). This is an estimate for ranking, not a guaranteed payout. Competition and verification probabilities are deliberately conservative defaults in Plan 1 and can be calibrated from observed outcomes in a later plan.

## Plan boundary

Mutation is intentionally absent. A separate approved Plan 2 is required before implementing any of:

- `POST /api/v1/tasks/{id}/access`
- `POST /api/v1/submissions`
- payout-address registration
- autonomous coding/PR creation
