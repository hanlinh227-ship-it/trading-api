# AI SHARED STATE

Canonical repository: `hanlinh227-ship-it/trading-api`
Branch: `main`

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

Roles:
- ChatGPT: PRIMARY_ENGINEER / source writer when lock owner
- Claude: REVIEWER / second engineer; source write only when explicitly assigned

Current open issue:
- AI-002: checkpoint/docs lag current component state; update only after Cloudflare deploy/runtime for V77.18.46 is confirmed.

Next owner: CHATGPT

Production status:
- SOURCE REVIEW: PASS for V77.18.46 telemetry repair
- CLOUDFLARE DEPLOY/RUNTIME: NOT YET VERIFIED
- Do not claim production healthy until runtime is checked.

Rules:
- `main` source is authority over stale docs.
- One writer at a time.
- Read `WRITE_LOCK.md` before source writes.
- Never reset `TRADING_STATE` or delete `v775:books`.
- Never restore legacy Futures Signal or Hyro TK2.
- Never commit secrets or bypass hard risk/freshness/structural-SL gates.
