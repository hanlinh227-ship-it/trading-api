# MASTER TRADING STATE

Updated: 2026-08-26 UTC+7
Purpose: single canonical state for the Trading project.

## CURRENT PRODUCTION AUTHORITY — BYBIT AUTO 1.7.2

GitHub `main` + successfully verified Cloudflare runtime are authoritative.

Current production contract:
- production execution authority = Bybit Auto LIVE only;
- canonical source version = `BYBIT-AUTO-1.7.2`;
- Signal V11 execution/scheduler on this Worker = OFF;
- private authenticated Bybit transport = `VPS_BYBIT_PRIVATE_PROXY`;
- market transport = `VPS_BYBIT_MARKET_PROXY`;
- existing `TRADING_STATE` KV is preserved; never reset it;
- daily profit target = OFF; trading is continuous subject only to canonical safety/risk/quality gates;
- Telegram surface = Unified Trading Hub;
- MEME remains PAPER_ONLY / NO WALLET / NO SIGNING / NO REAL EXECUTION;
- Forex remains PAPER_ONLY unless separately promoted by its own validated authority.

## BYBIT LIVE PIPELINE
`Scheduler -> live positions/account -> canonical PnL reconciliation -> position management -> single-source entry spacing -> liquid universe -> deterministic setup -> Regime Engine -> Adaptive Edge -> correlation gate -> fresh/re-anchor -> sizing -> live-position-only risk preflight -> 3AI review -> post-AI fresh quote -> LIVE order -> actual RR/risk verification -> verified SL/TP/trailing -> lifecycle management -> Telegram -> bounded learning`.

## ENTRY-GATE CONFLICT LOCK — 1.7.2
- Global entry spacing no longer has a separate hard-coded 5-minute controller authority.
- Controller and engine derive entry timing from `BYBIT_AUTO_CONFIG.execution.cooldownSec`; default is 180 seconds.
- Controller no longer injects a hidden `BYBIT_ENTRY_COOLDOWN_SEC=180` override into the inner engine.
- Loss-streak pause authority lives in the canonical engine state; controller only reports it.
- `maxTradesPerDay` remains effectively unlimited; there is no daily target/quota gate.
- Quality, freshness, RR, risk, correlation, live-account and protection gates remain mandatory.

## CLOSED-PNL / GHOST-PLAN RESILIENCE — 1.7.2
- Closed-PnL reconciliation remains canonical and fail-closed when stale beyond the 15-minute healthy grace window.
- If Bybit live positions confirm a symbol is no longer open, its retained plan may remain in state for reconciliation/learning but MUST NOT count toward current open risk or initial-margin capacity.
- Live entry risk accounting authority is `BYBIT_LIVE_POSITIONS_ONLY`.
- A pending closed plan may still block re-entry into the same symbol until outcome reconciliation completes, preventing duplicate lifecycle ambiguity, but it must not block unrelated symbols through false `TOTAL_OPEN_RISK_CAP` or `PORTFOLIO_MARGIN_HEADROOM`.
- Untracked real Bybit positions remain a hard safety block.

## LOSS-STREAK SAFETY
- Canonical Bybit closed-PnL history computes loss streak.
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
Never reset state, fabricate live data, bypass freshness/SL/RR/risk/capital/protection gates, count closed ghost plans as live exposure, resurrect a second controller-level loss-pause authority, resurrect hard-coded 5-minute spacing, enable adaptive auto-promote, or allow retired Signal V11 execution to compete with Bybit Auto.

## DEPLOYMENT
Canonical workflow: `.github/workflows/deploy-cloudflare-worker.yml`.
Do not declare a source change LIVE until `npm run check`, Cloudflare deployment, `/bybit/health` revision verification and Bybit VPS transport checks all pass.
