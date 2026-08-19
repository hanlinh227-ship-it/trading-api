# AI SHARED STATE

Canonical repository: `hanlinh227-ship-it/trading-api`
Branch: `main`

Permanent AI coordination:
- GitHub is the communication bus between ChatGPT and Claude.ai.
- Root entrypoints: `/CLAUDE.md`, `/AGENTS.md`.
- Protocol: `/docs/ai-coengineer/PROTOCOL.md`.
- ChatGPT inbox: `/docs/ai-coengineer/CLAUDE_TO_CHATGPT.md`.
- Claude inbox: `/docs/ai-coengineer/CHATGPT_TO_CLAUDE.md`.
- One writer at a time via `/docs/ai-coengineer/WRITE_LOCK.md`.

Current reviewed component state:
- `cloudflare-worker/index.js`: V77.18.43
- `cloudflare-worker/hub-v77171.js`: V77.18.42
- `cloudflare-worker/engine-v77168.js`: V77.16.20
- Health fixes present through V77.18.45
- `cloudflare-worker/hyro-execution.js`: V77.18.46 telemetry degradation repair, commit `1d6db32155c06d464f4da94746df73e110b9b294`

Review state:
- AI-001 Hyro optional `closedPnl` isolation: CLAUDE PASS 2026-08-19T11:40:00Z
- wallet/positions/orders remain critical fail-closed
- closedPnl-only failure keeps telemetry connected with degraded diagnostics
- realized-PnL freshness is explicit; no fabricated realized profit/loss

Deployment evidence:
- Cloudflare Deployments UI showed `V77.18.46 isolate Hyro closedPnl telemetry degradation` in deployed version history.
- Subsequent AI communication/shared-state commits were also deployed from `main`.
- User requested no additional ad-hoc testing at this time.

Roles:
- ChatGPT: PRIMARY_ENGINEER / source writer when lock owner
- Claude: REVIEWER / SECOND_ENGINEER; source write only when explicitly assigned

Current open issue:
- AI-002: checkpoint/docs lag current component state. Documentation synchronization remains separate from production source behavior.

Next owner: CHATGPT unless an explicit bus message reassigns ownership.

Production/source status:
- SOURCE REVIEW: PASS for V77.18.46 telemetry repair
- CLOUDFLARE DEPLOYMENT: observed in Deployments UI
- RUNTIME HEALTH CLAIM: do not elevate beyond available evidence; no extra testing requested

Rules:
- `main` source is authority over stale docs.
- One writer at a time.
- Read `WRITE_LOCK.md` before source writes.
- Never reset `TRADING_STATE` or delete `v775:books`.
- Never restore legacy Futures Signal or Hyro TK2.
- Never commit secrets or bypass hard risk/freshness/structural-SL gates.
