# CURRENT HANDOFF — TRADING PROJECT

Updated: 2026-08-26 UTC+7

## ACTIVE PRODUCTION AUTHORITY
Production Worker execution authority: **Bybit Auto only**.
Canonical source target: `BYBIT-AUTO-1.7.3`.
Execution: Bybit LIVE. Signal V11 execution/scheduler: disabled. Existing `TRADING_STATE` KV: preserved. Daily target/quota: OFF. AI core: Claude + Codex + DeepSeek final-entry review only.

## 1.7.3 CANONICAL CONFLICT LOCK
Entry spacing has one authority only: `BYBIT_AUTO_CONFIG.execution.cooldownSec`, default 180 seconds. Controller hard-coded spacing and hidden inner-engine cooldown overrides are forbidden. Loss-streak pause is decided only by canonical engine state.

Global closed-PnL safety is now scoped to the current Asia/Bangkok trading day. Historical ghost plans are not allowed to expand that query window or turn old reconciliation ambiguity into a global trading block.

If a LIVE plan is absent from authoritative Bybit positions and cannot be resolved from current-day closed-PnL because it belongs to an older lifecycle, it is moved to `reconcileQuarantine` as `OUTCOME_UNRESOLVED_OUTSIDE_DAILY_WINDOW`. The outcome is not fabricated. The quarantined plan is removed from `openPlans`, excluded from risk/margin, and cannot block either unrelated symbols or future same-symbol entries.

Same-day pending closed plans may still prevent same-symbol re-entry until their outcome resolves. This preserves lifecycle integrity without globally freezing the bot.

## LIVE SAFETY
- closed-PnL healthy grace: maximum 15 minutes; stale current-day safety reconciliation remains fail-closed;
- current-day closed-PnL pagination truncation remains a hard safety block because daily risk/loss-streak state would be incomplete;
- 3 consecutive realized losses: one-shot 30-minute new-entry pause;
- untracked real Bybit position: hard block;
- max positions 3; max same direction 2;
- min RR 1.5; preferred 1.8;
- max risk/trade 10% equity; max total live managed risk 20%;
- max margin/new position 42%; min free reserve 18%; portfolio margin cap 82%;
- leverage cap 10x;
- Smart CUT remains reduce-only with verified fill lifecycle;
- freshness, spread/chase, structural protection, post-AI quote, actual RR and verified SL/TP/trailing remain mandatory.

## RETIRED LEGACY BLOCKERS
The following are forbidden in production: controller 5-minute spacing, controller duplicate loss pause, ghost-plan live risk accounting, `CLOSED_PNL_LOOKBACK_EXCEEDED` as a global entry blocker, and `MAX_CLOSED_LOOKBACK_MS` expansion driven by unresolved old plans.

## PIPELINE
`Scheduler -> account/positions -> current-day PnL safety -> stale lifecycle quarantine -> management -> canonical entry spacing -> scan -> regime/adaptive edge -> correlation -> freshness/re-anchor -> sizing/risk -> 3AI -> post-AI validation -> order -> actual risk/RR -> verified protection -> lifecycle -> learning`.

## TELEMETRY
Controller persists last cycle reason, last entry blocker, scan summary, scheduler exceptions and runtime revision. Engine persists `lastLiveRiskAccounting` including live symbols, tracked plans, risk-counted plans, pending closed plans and unresolved quarantine count.

## DEPLOYMENT CONTRACT
Canonical workflow: `.github/workflows/deploy-cloudflare-worker.yml`.
Do not claim 1.7.3 LIVE until source validation, Cloudflare deployment, `/bybit/health` revision match and both VPS Bybit transports pass.
