# MASTER TRADING STATE

Updated: 2026-08-25 UTC+7
Purpose: single canonical state for the Trading project.

## CURRENT PRODUCTION AUTHORITY — BYBIT AUTO 1.2.0

GitHub `main` + deployed Cloudflare runtime are authoritative.

Current production contract:
- production hub = `BYBIT_AUTO_TRADE_ONLY`;
- production version = `BYBIT-AUTO-1.2.0`;
- exchange execution authority = Bybit Auto LIVE;
- Signal V11 runtime/scheduler on this Worker = OFF;
- runtime = `CLOUDFLARE_NATIVE`;
- private authenticated Bybit transport = `VPS_BYBIT_PRIVATE_PROXY`;
- state store = existing `TRADING_STATE` KV; never reset it;
- Telegram = automatic entry notification and AUTO status/management visibility.

Historical Signal V11 research/backtest material remains research/history only unless current `main` explicitly restores a non-execution research path. It must not compete with Bybit Auto production authority.

## LIVE AUTO PIPELINE

`Cloudflare scheduler -> Bybit public scan -> deterministic candidate ranking -> one-shot fresh/re-anchor gate -> margin-aware sizing -> risk preflight -> Claude/Codex/DeepSeek final-entry review -> post-AI fresh quote -> Bybit LIVE order -> verified SL/TP/native trailing -> HOLD/BE/profit-lock/trailing management -> Telegram -> learning telemetry`

Hard behavior:
- scanner finds candidates deterministically; AI does not search the market;
- 3 AI are final-entry reviewers only;
- quote freshness and post-AI drift remain mandatory;
- re-anchor is bounded to one attempt per candidate; never chase indefinitely;
- leverage is adaptive but capped at 5x;
- sizing is margin-aware and fail-closed;
- total open-risk and max-position limits remain enforced;
- protection must be verified after fill;
- discretionary CUT is OFF by default;
- normal exits are SL, BE stop, profit-lock stop, trailing stop, or TP;
- manager remains active even while new entries are blocked by cooldown/loss pause.

## FREQUENCY PROFILE — BALANCED-FREQUENT

Current intended production profile:
- scan every 60s;
- new-entry spacing/cooldown = 180s;
- global config floor score = 70;
- max configured spread gate = 9 bps, with symbol/profile-specific limits still authoritative where stricter;
- max configured chase = 0.60 ATR, with profile-specific limits still authoritative where stricter;
- max open positions = 3;
- max same-direction positions = 2;
- max leverage = 5x;
- margin usage budget = 80% of equity;
- risk ladder starts at $5 risk / $10 reward around $50 balance, bounded by equity/risk caps.

## POSITION MANAGEMENT

Default path:
`HOLD -> BREAKEVEN -> PROFIT_LOCK -> TRAIL -> TP/STOP`

Discretionary CUT is disabled unless `BYBIT_DISCRETIONARY_CUT_ENABLED=true` is explicitly configured. Stale-time and profit-giveback alone must never trigger a market-close. If discretionary CUT is explicitly enabled, only confirmed severe thesis invalidation may close early.

## AI CORE

AUTO production core providers:
- Claude
- Codex
- DeepSeek

AUTO policy: `FINAL_ENTRY_REVIEW_ONLY`. Qwen/OpenRouter are not required for AUTO execution.

## CI / DEPLOYMENT

Production deploy workflow: `.github/workflows/deploy-cloudflare-worker.yml`.
It validates source with `npm run check`, deploys Worker, and verifies `/bybit/health` runtime revision against the deployment commit before declaring success.

## PERMANENT INVARIANTS

Never:
- reset `TRADING_STATE`;
- fabricate quote, PnL, provider, execution or protection state;
- bypass fresh quote, structural SL, RR, risk, margin or protection gates merely to increase trade count;
- increase leverage above the configured 5x cap to force an entry;
- enable discretionary CUT implicitly;
- let AI bypass deterministic entry/risk gates;
- commit secrets/API tokens/private keys;
- allow retired Signal V11/legacy execution paths to compete with Bybit Auto production.

## STARTUP / HANDOFF ORDER

1. fresh-read GitHub `main`;
2. read this file;
3. read `CURRENT_HANDOFF.md`;
4. read `WRITE_LOCK.md`;
5. inspect current `cloudflare-worker/index.js`, `bybit-auto-config.js`, `bybit-auto-controller.js`, `bybit-auto-v1.js`, `bybit-scalp-engine.js`, `bybit-position-manager.js`, `bybit-v5-client.js` before any production write;
6. verify deployed runtime via `/bybit/health` before claiming LIVE state.
