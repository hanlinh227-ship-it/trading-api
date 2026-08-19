# AI OPEN ISSUES

## AI-001
Status: RESOLVED
Severity: CRITICAL
Owner: CHATGPT
Area: HYRO

Description:
`cloudflare-worker/hyro-execution.js` previously treated failure of any telemetry probe as full telemetry failure. `closedPnl` is non-critical for live position/risk management but could force `connected:false`.

Root cause:
`collectTelemetry()` aggregated wallet, positions, orders and closedPnl into one health decision.

Fix:
- Critical: wallet, positions, orders.
- Optional: closedPnl.
- Optional failure => connected with degraded diagnostics.
- Critical failure => fail closed for new execution.
- Stale realized stats are not fabricated; last-known stats/null availability state is preserved.

Repair commit:
`1d6db32155c06d464f4da94746df73e110b9b294`

Reviewer:
CLAUDE

Review result:
PASS — 2026-08-19T11:40:00Z

## AI-002
Status: OPEN
Severity: HIGH
Owner: CHATGPT
Area: DOCS

Description:
`CURRENT_HANDOFF.md` / `MASTER_TRADING_STATE.md` lag current component/source state.

Expected fix:
Update after V77.18.46 Cloudflare deployment/runtime is confirmed so docs point to actual canonical component versions and production state.
