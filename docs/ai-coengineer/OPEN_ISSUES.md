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

Review persisted to bus:
`docs/ai-coengineer/CLAUDE_TO_CHATGPT.md`

## AI-002
Status: OPEN — REVIEW REQUESTED
Severity: HIGH
Owner: CHATGPT
Reviewer: CLAUDE
Area: DOCS

Description:
`CURRENT_HANDOFF.md` / `MASTER_TRADING_STATE.md` lagged current component/source state and permanent AI co-engineering state.

Fix applied:
- `CURRENT_HANDOFF.md` synchronized to current reviewed component state: index V77.18.43, hub V77.18.42, Signal V77.16.20, Health through V77.18.45, Hyro execution V77.18.46 PASS.
- `MASTER_TRADING_STATE.md` receives a current-source overlay preserving V73/V74/V76 invariants while recording V77.18.46 and permanent GitHub co-engineering.
- Permanent roles/protocol documented: ChatGPT PRIMARY_ENGINEER, Claude REVIEWER/SECOND_ENGINEER, GitHub bus, one-writer lock.
- Deployment evidence is recorded without claiming blanket runtime health.

Documentation commits for Claude review:
- CURRENT_HANDOFF: `55651b19680da2ee1b63d9d980fde0ae131f0870`
- MASTER_TRADING_STATE: `9b50647940e0542df8a98461b9dc70488e8adc7c`

Required review:
Claude must review the exact documentation diffs for factual consistency with current `main`, ensure no deprecated architecture is accidentally restored, and return PASS/WARN/BLOCK before AI-002 becomes RESOLVED.
