# MASTER TRADING STATE

Updated: 2026-08-26 UTC+7
Purpose: single canonical state for the Trading project.

## CURRENT PRODUCTION AUTHORITY — BYBIT AUTO 1.7.3

GitHub `main` + successfully verified Cloudflare runtime are authoritative.

Current production contract:
- production execution authority = Bybit Auto LIVE only;
- canonical source version = `BYBIT-AUTO-1.7.3`;
- Signal V11 execution/scheduler on this Worker = OFF;
- private authenticated Bybit transport = `VPS_BYBIT_PRIVATE_PROXY`;
- market transport = `VPS_BYBIT_MARKET_PROXY`;
- existing `TRADING_STATE` KV is preserved; never reset it;
- daily profit target = OFF; trading is continuous subject only to canonical safety/risk/quality gates;
- Telegram surface = Unified Trading Hub;
- MEME remains PAPER_ONLY / NO WALLET / NO SIGNING / NO REAL EXECUTION;
- Forex remains PAPER_ONLY unless separately promoted by its own validated authority.

## BYBIT LIVE PIPELINE
`Scheduler -> live positions/account -> current-day canonical PnL safety reconciliation -> stale lifecycle quarantine -> position management -> single-source entry spacing -> liquid universe -> deterministic setup -> Regime Engine -> Adaptive Edge -> correlation gate -> fresh/re-anchor -> sizing -> live-position-only risk preflight -> 3AI review -> post-AI fresh quote -> LIVE order -> actual RR/risk verification -> verified SL/TP/trailing -> lifecycle management -> Telegram -> bounded learning`.

## CANONICAL ENTRY-GATE LOCK — 1.7.3
- Global entry spacing has exactly one authority: `BYBIT_AUTO_CONFIG.execution.cooldownSec`, default 180 seconds.
- Controller has no hard-coded 5-minute spacing and cannot inject a hidden inner-engine cooldown override.
- Loss-streak pause authority lives in canonical engine state; controller only reports it.
- `maxTradesPerDay` is effectively unlimited; no daily profit target/quota gate exists.
- Quality, freshness, RR, risk, correlation, live-account and protection gates remain mandatory.

## CLOSED-PNL / LEGACY STATE QUARANTINE — 1.7.3
- Global PnL safety reconciliation is scoped to `CURRENT_TRADING_DAY_ONLY` so old ghost plans cannot expand the safety query window.
- Transient closed-PnL failure may use a maximum 15-minute last-known-healthy grace window. Stale current-day safety reconciliation remains fail-closed.
- If a LIVE plan is absent from authoritative Bybit positions and its outcome cannot be resolved inside the current-day window, an older plan is moved to `reconcileQuarantine` with unresolved outcome rather than treated as WIN/LOSS.
- Quarantined plans are removed from `openPlans`; they cannot consume risk/margin, cannot block unrelated symbols, and cannot block same-symbol re-entry.
- Same-day pending closed plans may temporarily block only that same symbol until reconciliation completes.
- Live entry risk accounting authority remains `BYBIT_LIVE_POSITIONS_ONLY`.
- Untracked real Bybit positions remain a hard safety block.
- `CLOSED_PNL_LOOKBACK_EXCEEDED` global blocking and ghost-driven `MAX_CLOSED_LOOKBACK_MS` history expansion are retired and forbidden.

## LOSS-STREAK SAFETY
- Canonical current-day Bybit closed-PnL history computes loss streak.
- 3 consecutive realized losses trigger a 30-minute new-entry pause once per newest loss event.
- The same historical streak cannot repeatedly re-arm the pause every scheduler cycle.
- Position management remains active during the pause.

## CAPITAL / QUALITY DEFAULTS
- leverage cap 10x;
- max open positions 3;
- max same direction 2;
- base risk $5 at $50 balance, scaled and capped by equity/risk rules;
- max risk/trade 10% equity; max total managed open risk 20%;
- max margin/new position 42%; minimum free reserve 18%; max portfolio margin 82%;
- minimum RR 1.5; preferred RR 1.8;
- adaptive base score 68, bounded 66–84;
- spread ceiling 12 bps; chase ceiling 0.80 ATR;
- Smart CUT enabled with verified reduce-only/full-fill lifecycle.

## PERMANENT INVARIANTS
Never reset state, fabricate live data, bypass freshness/SL/RR/risk/capital/protection gates, count closed ghost plans as live exposure, allow unresolved historical plans to globally block entry, expand current-day PnL safety history because of ghost plans, resurrect a second controller-level loss-pause authority, resurrect hard-coded 5-minute spacing, enable adaptive auto-promote, or allow retired Signal V11 execution to compete with Bybit Auto.

## DEPLOYMENT
Canonical workflow: `.github/workflows/deploy-cloudflare-worker.yml`.
Do not declare a source change LIVE until `npm run check`, Cloudflare deployment, `/bybit/health` revision verification and Bybit VPS transport checks all pass.
