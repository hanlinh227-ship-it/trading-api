# STACKHUB V2 — TaskBounty Read-Only Scanner

Plan 1 implements a **strictly read-only, zero-spend** foundation for discovering legitimate AI-agent coding bounties. It does not claim tasks, request repository access, submit fixes, configure payout addresses, or move crypto.

## Safety invariants

- `dry_run` must remain `true`.
- `external_spend_limit_usd` must remain `0`.
- TaskBounty source must remain `read_only: true`.
- Discovery uses only public `GET /api/v1/bounties.json`; when the feed contains an item, structured normalization may use read-only `GET /api/v1/tasks/{id}`.
- CAPTCHA/human impersonation/fake engagement/location spoofing/wallet-secret tasks are denied.
- Task descriptions are untrusted data and cannot alter runtime policy.
- Wallet private keys, seed phrases, and mnemonics are never requested or stored.
- Production trading services are outside this subsystem.

## What it does

1. Polls TaskBounty's public JSON Feed for currently open bounties.
2. Fetches read-only task detail for discovered feed items so reward and acceptance metadata can be normalized safely.
3. Normalizes opportunities into typed models.
4. Applies deny-by-default agent/compliance policy.
5. Estimates expected net value and USD/minute score.
6. Upserts opportunities idempotently into SQLite.
7. Records source health and emits redacted status output.

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

`TASKBOUNTY_API_KEY` is optional. Public bounty discovery does not require it. If a key is supplied for a later read-only endpoint, it is read from the process environment only and is never written to SQLite or telemetry.

## Current TaskBounty economics

When a feed item is available and its detail exposes `bounty_cents`, the adapter normalizes that amount to the documented solver share used by the current model (80% of the funded bounty). This is an estimate for ranking, not a guaranteed payout. Competition and verification probabilities are deliberately conservative defaults in Plan 1 and can be calibrated from observed outcomes in a later plan.

An empty public feed is a healthy state: the source remains `ok=true` with HTTP 200 and the scanner records zero opportunities until TaskBounty publishes a new bounty.

## Plan boundary

Mutation is intentionally absent. A separate approved Plan 2 is required before implementing any of:

- `POST /api/v1/tasks/{id}/access`
- `POST /api/v1/submissions`
- payout-address registration
- autonomous coding/PR creation
