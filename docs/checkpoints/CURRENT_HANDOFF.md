# CURRENT HANDOFF — TRADING PROJECT

Updated: 2026-08-26 UTC+7

## ACTIVE PRODUCTION AUTHORITY
Production Worker execution authority: **Bybit Auto only**.
Canonical source target: `BYBIT-AUTO-1.7.2`.
Execution: Bybit LIVE. Signal V11 execution/scheduler: disabled. Existing `TRADING_STATE` KV: preserved. Daily target/quota: OFF. AI core: Claude + Codex + DeepSeek final-entry review only.

## 1.7.2 CONFLICT CLEANUP
The old controller-level 5-minute entry spacing has been removed. Entry spacing now has one config authority: `BYBIT_AUTO_CONFIG.execution.cooldownSec`, default 180 seconds. The controller no longer injects an inner-engine cooldown override and no longer duplicates the loss-streak pause decision before the engine runs.

Closed or missing live positions may leave `openPlans` temporarily pending while Bybit closed-PnL is reconciled. Those plans remain for lifecycle/learning integrity but are excluded from current LIVE risk and margin capacity when the authoritative Bybit positions endpoint confirms the position is absent. Risk accounting authority is `BYBIT_LIVE_POSITIONS_ONLY`.

A pending plan can still prevent re-entry into the same symbol until reconciliation completes, but it must not block unrelated symbols through false open-risk or portfolio-margin calculations.

## LIVE SAFETY
- closed-PnL healthy grace: maximum 15 minutes; stale beyond grace remains fail-closed;
- 3 consecutive realized losses: one-shot 30-minute new-entry pause;
- untracked real Bybit position: hard block;
- max positions 3; max same direction 2;
- min RR 1.5; preferred 1.8;
- max risk/trade 10% equity; max total live managed risk 20%;
- max margin/new position 42%; min free reserve 18%; portfolio margin cap 82%;
- leverage cap 10x;
- Smart CUT remains reduce-only with verified fill lifecycle;
- freshness, spread/chase, structural protection, post-AI quote, actual RR and verified SL/TP/trailing remain mandatory.

## PIPELINE
`Scheduler -> account/positions -> PnL reconcile -> management -> canonical entry spacing -> scan -> regime/adaptive edge -> correlation -> freshness/re-anchor -> sizing/risk -> 3AI -> post-AI validation -> order -> actual risk/RR -> verified protection -> lifecycle -> learning`.

## TELEMETRY
Controller persists last cycle reason, last entry blocker, scan summary, scheduler exceptions and runtime revision. Engine persists `lastLiveRiskAccounting` including live symbols, tracked plans, risk-counted plans and pending closed plans so ghost-plan blocking can be diagnosed directly.

## DEPLOYMENT CONTRACT
Canonical workflow: `.github/workflows/deploy-cloudflare-worker.yml`.
Do not claim 1.7.2 LIVE until source validation, Cloudflare deployment, `/bybit/health` revision match and both VPS Bybit transports pass.
