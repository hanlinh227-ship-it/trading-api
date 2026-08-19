# AI OPEN ISSUES

## AI-001
Status: OPEN
Severity: CRITICAL
Owner: CHATGPT
Area: HYRO

Description:
`cloudflare-worker/hyro-execution.js` currently treats failure of any telemetry probe as full telemetry failure. `closedPnl` is non-critical for live position/risk management but can force `connected:false`.

Root cause:
`collectTelemetry()` aggregates wallet, positions, orders and closedPnl into one `failed.length===0` health decision.

Expected fix:
- Critical: wallet, positions, orders.
- Optional: closedPnl.
- Optional failure => connected with degraded diagnostics and safe realized-PnL fallback.
- Critical failure => fail closed for new execution.

Source:
Claude reviewer audit 2026-08-19.

Reviewer after fix: CLAUDE

## AI-002
Status: OPEN
Severity: HIGH
Owner: CHATGPT
Area: DOCS

Description:
`CURRENT_HANDOFF.md` / `MASTER_TRADING_STATE.md` lag current component/source state.

Expected fix:
Update after AI-001 code/validation so docs point to actual canonical component versions and HEAD.
