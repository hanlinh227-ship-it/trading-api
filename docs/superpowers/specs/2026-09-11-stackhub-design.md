# STACKHUB Design

## Goal
Build a zero-new-cost crypto earning orchestrator that aggregates legitimate passive earning sources and human-required microtasks, ranks opportunities by expected value per minute, tracks payout thresholds, and never automates actions that platform terms require a human to perform.

## Scope
STACKHUB is an earning coordinator, not a bot farm. It may automate monitoring, scheduling, local service health, API-based data collection, passive clients that are explicitly designed to run unattended, and accounting. It must not bypass CAPTCHA, anti-bot controls, rate limits, KYC, device restrictions, offer requirements, or platform terms.

## Source classes
### PASSIVE_ALLOWED
Sources whose normal product behavior is unattended resource sharing or background earning. STACKHUB may monitor the local client/service and earnings through documented interfaces. Initial registry: Grass, Honeygain, Pawns.app.

### DISCOVERY_ONLY
Sources with paid tasks but no clear documented bot API for task execution. STACKHUB may list, rank, and remind, but must not perform the task or submit answers automatically. Initial registry: JumpTask.

### HUMAN_REQUIRED
Surveys, CAPTCHA, games, offers, account verification, KYC, purchase/install tasks, and any task requiring an attestation of human activity. STACKHUB can queue them and estimate ROI only.

## Deployment policy
- VPS: orchestration, source polling where documented, accounting, dashboard/status, alerts, watchdogs.
- Residential devices: passive bandwidth-sharing apps only when the source terms and the user's ISP/device ownership allow it.
- Never deploy Pawns.app traffic sharing on a server/VPS because its current terms require a residential IP and disallow servers/VPN/proxy services.
- Honeygain may only run on devices exclusively owned by the user and connections the user is authorized to share. STACKHUB does not attempt to increase traffic artificially or exceed device limits.
- Grass integration starts as monitoring/config guidance until an official automation interface is verified.

## Architecture

```
Source Registry
    -> Compliance Gate
    -> Collectors
    -> Normalized Opportunity Store
    -> ROI Ranker
    -> Action Router
         -> AUTO_ALLOWED queue
         -> HUMAN_REQUIRED queue
    -> Earnings Ledger
    -> Payout Planner
    -> Status API / CLI
```

## Core components
- `registry.py`: static source metadata, automation class, payout method, minimum payout, device/network constraints.
- `compliance.py`: hard gate preventing forbidden automation modes.
- `models.py`: normalized source/opportunity/earning models.
- `ranker.py`: deterministic expected-value-per-minute scoring.
- `ledger.py`: SQLite earnings and payout ledger.
- `collectors/`: documented-interface collectors. Initial collectors are conservative and may use user-supplied export/manual snapshots when no official API exists.
- `scheduler.py`: periodic refresh and health checks.
- `status.py`: redacted JSON status output.
- `cli.py`: `sources`, `opportunities`, `status`, `record`, `payouts`, `run-once`.

## ROI model
Base score:

`score = expected_reward_usd * approval_probability / max(estimated_minutes, 1)`

Penalties:
- payout threshold distance
- uncertain geographic eligibility
- requires purchase/deposit
- high rejection probability

Hard reject:
- nonzero required deposit
- CAPTCHA automation
- bot-prohibited execution
- unsupported geography when known
- residential-only source on VPS

## Initial source registry
- Grass: passive background bandwidth contribution; Stage 2 rewards described by Grass as USDC distributions. Monitoring only until a documented machine interface is verified.
- Honeygain: passive bandwidth sharing; JumpTask payout integration supported by current terms. Local-client health monitoring only; no artificial traffic generation.
- Pawns.app: passive traffic sharing + manual tasks; Bitcoin payout advertised. Traffic sharing restricted to residential IPs and explicitly not servers/VPN/proxies, so VPS execution is blocked by policy.
- JumpTask: discovery/ranking of microtasks and AI-training tasks; execution remains HUMAN_REQUIRED unless an official automation API explicitly permits otherwise.

## Security
- No wallet seed/private key storage.
- Tokens stored only in environment variables or local secret files excluded from Git.
- Status output never prints secrets.
- No withdrawal automation in MVP.
- Payout planner provides thresholds and recommended action; user confirms withdrawals.

## Testing
Test-first implementation:
1. compliance blocks HUMAN_REQUIRED automation;
2. Pawns.app passive mode is rejected on VPS;
3. ROI ranking is deterministic;
4. zero-cost filter rejects deposit-required opportunities;
5. ledger sums earnings correctly;
6. status serialization redacts secret-like fields;
7. registry contains only known automation classes.

## MVP success criteria
- CLI can list sources and their automation policy.
- CLI can ingest sample/manual earning snapshots.
- ROI ranker produces a sorted queue.
- Compliance gate prevents auto execution of restricted tasks.
- SQLite ledger persists earnings.
- `status.json` can be generated without secrets.
- Unit tests pass in GitHub Actions.

## Non-goals for MVP
- CAPTCHA solving.
- Automated survey/game/offer completion.
- Browser click automation against third-party earning sites.
- Automated withdrawals.
- Circumventing geographic/device/network restrictions.
