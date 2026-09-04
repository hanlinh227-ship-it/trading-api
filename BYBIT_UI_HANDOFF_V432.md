# Bybit Bot V4.3.3 — FINAL CORE FREEZE / UX/UI Handoff

## Runtime baseline
- Auto version: `BYBIT-MULTI-STATEFLOW-4.3.3`
- Runtime contract: `BYBIT_MULTI_ASSET_RUNTIME_V19_FINAL_CORE_FREEZE_UI_READY`
- UI schema: `BYBIT_UI_SCHEMA_V1`
- Execution remains event-driven from VPS WebSocket market-state changes.
- The UI layer is read-only. It does **not** get order/close/leverage write endpoints.

## Read-only endpoints
- `GET /bybit/ui/bootstrap` — public static UI contract, universe, policy, capability metadata.
- `GET /bybit/ui/snapshot` — authenticated live account/controller snapshot.
- `GET /bybit/health` — transport/runtime health.
- `GET /bybit/entry-health` — current entry infrastructure readiness.
- `GET /runtime/contract` — canonical runtime contract.

## Authentication
`/bybit/ui/snapshot` requires the existing action key or VPS bridge secret. Do not embed either secret directly in a browser bundle. A production UI should call the snapshot through a trusted server-side/BFF layer.

## Portfolio semantics
- Base concurrent positions still scale with equity.
- A position with a native stop at/through breakeven is treated as protected active risk and consumes only a fractional risk slot.
- A physical hard cap of `base max + 1` remains, so protected-slot reuse cannot create an unlimited number of positions.
- Correlation limits use the same protected-risk weighting.
- There is no forced opportunity replacement: the controller does not close a healthy winner merely to make room for a new candidate.

## Profit objective semantics
- New risk is rejected if the planned net profit floor after estimated costs is not feasible inside the permitted runner geometry.
- At low equity the configured planned floor begins at `$1.05` net before per-symbol multipliers and the planning buffer.
- After the live position reaches its profit floor, V4.3.3 targets a 100% floor-retention lock when exchange geometry permits, while keeping native TP/SL and runner logic.
- This is an objective/protection rule, **not a guarantee of realized profit**. Gaps, slippage, liquidation conditions, exchange failures, or market movement can still produce less profit or a loss.

## UI fields to prioritize
1. Runtime: version, mode, ready, blockers, checkedAt.
2. Account: equity, wallet balance, available balance.
3. Portfolio: positions, active risk, protected status, risk-slot weight, slots used/available, hard physical cap.
4. Profit: planned floor ladder, floor retention %, live PnL, TP/SL.
5. Candidates: ranking, final block reason, recheck result, executed state.
6. Risk: leverage policy, active-risk cap, margin cap, reserve.

## UX safety
- Clearly label LIVE vs PAPER/DEMO.
- Never imply guaranteed profit.
- Any future write controls should be a separate authenticated control plane with confirmation, audit log, and server-side authorization; do not bolt them onto the read-only snapshot contract.

## Final core-freeze correction
- Risk-slot admission now reserves the full pending slot before opening a new position. This prevents a new order from pushing weighted risk slots or correlation slots above their configured caps.
- Runtime metadata now points to the actual V4 portfolio authority and floor-lock scalp authority.
- `BYBIT_UI_SCHEMA_V1` remains stable for the UX/UI project.
