# AI SHARED STATE

Canonical repository: `hanlinh227-ship-it/trading-api`
Branch: `main`
HEAD at bus initialization: `807ee835f8a5f812383f5afc6a647314c189e879`

Runtime component versions observed by Claude audit 2026-08-19:
- `cloudflare-worker/index.js`: V77.18.43
- `cloudflare-worker/hub-v77171.js`: V77.18.42
- `cloudflare-worker/engine-v77168.js`: V77.16.20
- Health fixes present through commit V77.18.45

Roles:
- ChatGPT: PRIMARY_ENGINEER / source writer when lock owner
- Claude: REVIEWER / second engineer; source write only when explicitly assigned

Current critical issue:
- AI-001: Hyro `closedPnl` probe can force full telemetry disconnected even when wallet/positions/orders are healthy.

Next owner: CHATGPT

Rules:
- `main` source is authority over stale docs.
- One writer at a time.
- Read `WRITE_LOCK.md` before source writes.
- Never reset `TRADING_STATE` or delete `v775:books`.
- Never restore legacy Futures Signal or Hyro TK2.
- Never commit secrets or bypass hard risk/freshness/structural-SL gates.
