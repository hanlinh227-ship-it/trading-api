# MASTER TRADING STATE

Updated: 2026-08-25 UTC+7
Purpose: single canonical state for the Trading project.

## CURRENT PRODUCTION AUTHORITY — BYBIT AUTO 1.3.0

GitHub `main` + deployed Cloudflare runtime are authoritative.

Current production contract:
- production hub = `BYBIT_AUTO_TRADE_ONLY`;
- production version = `BYBIT-AUTO-1.3.0`;
- exchange execution authority = Bybit Auto LIVE;
- Signal V11 runtime/scheduler on this Worker = OFF;
- runtime = `CLOUDFLARE_NATIVE`;
- private authenticated Bybit transport = `VPS_BYBIT_PRIVATE_PROXY`;
- state store = existing `TRADING_STATE` KV; never reset it;
- Telegram = automatic entry notification and AUTO status/management visibility;
- daily profit target = OFF;
- trading policy = continuous, constrained by safety/risk/capital gates.

## VERSIONING — MANDATORY

Every production update must increment `BYBIT_AUTO_VERSION` in `cloudflare-worker/bybit-auto-config.js`.
Format: `BYBIT-AUTO-MAJOR.MINOR.PATCH`.
PATCH = fix/hygiene, MINOR = backward-compatible trading/risk/execution-policy change, MAJOR = incompatible architecture/authority change.
A source version is LIVE only after `/bybit/health` reports the deployment revision and readiness is valid.

## VERSION HISTORY

- `BYBIT-AUTO-1.3.0` — Continuous Capital Allocation: slot-based capital sizing, 30% reserve target, ≤20% equity initial-margin budget per new position before fee buffer, 4% single-risk cap, 10% total open-risk cap, base $1.50/$3 risk/reward around $50 equity, 5x leverage cap used for margin efficiency, Smart CUT retained, Telegram capital telemetry added.
- `BYBIT-AUTO-1.2.8` — Smart CUT multi-signal thesis-invalidation engine.
- `BYBIT-AUTO-1.2.7` — continuous trading/daily target OFF validation alignment.
- `BYBIT-AUTO-1.2.x` — production versioning, Telegram version visibility and target-policy cleanup.

## LIVE AUTO PIPELINE

`Cloudflare scheduler -> Bybit public scan -> deterministic candidate ranking -> one-shot fresh/re-anchor gate -> Continuous Capital Allocation sizing -> risk preflight -> Claude/Codex/DeepSeek final-entry review -> post-AI fresh quote -> Bybit LIVE order -> verified SL/TP/native trailing -> HOLD/BE/profit-lock/trailing/Smart CUT management -> Telegram -> learning telemetry`

## CONTINUOUS CAPITAL ALLOCATION — CANONICAL

Objective: keep capital reusable so one normal trade cannot monopolize the account.

Rules:
- risk is a ceiling, not a target that must be fully consumed;
- sizing is constrained by both structural SL risk and per-slot capital capacity;
- around $50 equity, base planned risk = $1.50 and base planned reward = $3.00;
- single-trade risk cap = 4% equity;
- total managed open-risk cap = 10% equity;
- max initial-margin budget per new position = 20% equity before fee buffer;
- minimum free-capital reserve target = 30% equity;
- fee/cost buffer = 5% of each slot margin budget;
- portfolio margin target ceiling = 65% equity;
- leverage cap = 5x and may be used for margin efficiency only; leverage must never increase allowed loss;
- max open positions = 3;
- max same-direction positions = 2;
- if capital capacity is the binding constraint, actual risk may be below the planned risk target;
- margin/risk failures are fail-closed.

Bybit UTA account telemetry to expose on Telegram:
- Balance / total wallet balance;
- Equity;
- Available balance;
- Total initial margin / IM rate.

## ENTRY / FREQUENCY PROFILE

- scan every 60s;
- global new-entry spacing = 300s;
- global floor score = 70;
- configured spread ceiling = 9 bps, stricter symbol/profile limit wins;
- configured chase ceiling = 0.60 ATR, stricter symbol/profile limit wins;
- one-shot fresh re-anchor only; no infinite chasing;
- 3 AI review only the final candidate;
- post-AI quote gate is mandatory;
- no daily trade-count target and no daily profit target.

## POSITION MANAGEMENT

Default path:
`HOLD -> BREAKEVEN -> PROFIT_LOCK -> TRAIL -> TP/STOP`

Smart CUT is enabled as an exceptional thesis-invalidation exit. It must require the canonical multi-signal score and confirmation logic, and emergency CUT must require severe confirmed invalidation. CUT orders must remain `reduceOnly`; slow trades, noisy M1, a later scan, or profit giveback alone are never sufficient reasons to CUT.

Manager stays active even when new entries are blocked by spacing, loss-pause, risk or capital gates.

## LOSS CONTROL

- 3 consecutive realized losses trigger a 30-minute new-entry pause;
- position management remains active during the pause;
- daily target is OFF;
- there is no requirement to reach a number of trades or a profit amount each day.

## AI CORE

Production core providers:
- Claude
- Codex
- DeepSeek

Policy: `FINAL_ENTRY_REVIEW_ONLY`. AI cannot bypass deterministic freshness, structure, risk, capital or protection gates.

## CI / DEPLOYMENT

Production deploy workflow: `.github/workflows/deploy-cloudflare-worker.yml`.
`npm run check` locks the source-of-truth, continuous-trading, capital allocator, Smart CUT and hard protection invariants before deploy. A deployment is complete only after `/bybit/health` runtime revision matches the deployment commit.

## PERMANENT INVARIANTS

Never:
- reset `TRADING_STATE`;
- fabricate quote, PnL, provider, execution or protection state;
- bypass fresh quote, structural SL, RR, risk, capital or protection gates to increase trade count;
- increase leverage above 5x to force an entry;
- size up merely to hit a fixed dollar-risk target;
- let one new position consume the old 80% equity margin budget;
- let AI bypass deterministic entry/risk/capital gates;
- commit secrets/API tokens/private keys;
- allow retired Signal V11/legacy execution paths to compete with Bybit Auto production;
- change production behavior without incrementing `BYBIT_AUTO_VERSION`.

## STARTUP / HANDOFF ORDER

1. fresh-read GitHub `main`;
2. read this file;
3. read `CURRENT_HANDOFF.md`;
4. read `WRITE_LOCK.md`;
5. inspect current Bybit AUTO source before any production write;
6. verify `/bybit/health` before claiming LIVE state.
