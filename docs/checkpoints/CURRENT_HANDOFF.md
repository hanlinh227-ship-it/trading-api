# CURRENT HANDOFF — TRADING PROJECT

Updated: 2026-08-25 UTC+7

## READ FIRST
1. Fresh-read GitHub `main`.
2. Read `docs/checkpoints/MASTER_TRADING_STATE.md`.
3. Read this file.
4. Read `docs/ai-coengineer/WRITE_LOCK.md`.
5. Inspect current Bybit AUTO source before changing production.

GitHub `main` outranks stale historical checkpoints.

## ACTIVE PRODUCTION AUTHORITY

The production Worker is **Bybit Auto Trade Hub only**.

Canonical source version: `BYBIT-AUTO-1.3.0`.
Execution: Bybit LIVE.
Signal V11 scheduler/execution: disabled.
State: existing `TRADING_STATE` KV preserved.
Daily profit target: OFF.
Trading mode: continuous, controlled by risk/capital/safety gates.
AI core: Claude + Codex + DeepSeek final-entry review only.

## 1.3.0 CAPITAL POLICY

The old model that could allow one position to consume ~80% equity margin is retired.

New sizing order:
`equity -> risk ceiling -> slot margin ceiling -> fee buffer -> leverage for margin efficiency -> final qty -> RR/risk validation`.

Canonical defaults:
- base planned risk near $50 equity: $1.50;
- base planned reward near $50 equity: $3.00;
- max risk per trade: 4% equity;
- max total managed open risk: 10% equity;
- max initial-margin budget per new position: 20% equity before fee buffer;
- minimum reserve target: 30% equity;
- fee/cost buffer: 5% of slot margin budget;
- portfolio margin target ceiling: 65% equity;
- leverage cap: 5x;
- max positions: 3;
- max same direction: 2.

Important: risk is a ceiling, not a compulsory target. If the slot/margin cap is tighter than the risk-derived quantity, the bot accepts the smaller quantity and lower actual dollar risk instead of consuming more capital.

## ENTRY POLICY

- scan every 60s;
- global entry spacing = 300s;
- score floor 70;
- spread ceiling 9 bps unless symbol profile is stricter;
- chase ceiling 0.60 ATR unless symbol profile is stricter;
- bounded one-shot fresh/re-anchor before AI;
- post-AI fresh quote validation remains mandatory;
- no daily target and no fixed daily trade quota.

## POSITION MANAGEMENT

Normal path:
`HOLD -> BREAKEVEN -> PROFIT_LOCK -> TRAIL -> TP/STOP`.

Smart CUT is ON as an exceptional multi-signal thesis-invalidation exit. It must not fire merely because a trade is slow, a later scan changes opinion, M1 is noisy, or unrealized profit gives back. Emergency CUT is reserved for severe confirmed invalidation and must use `reduceOnly`.

## LOSS CONTROL

3 consecutive realized losses -> 30-minute new-entry pause.
Open-position management remains active during the pause.

## TELEGRAM

Dashboard must expose:
- `BYBIT-AUTO-1.3.0 • LIVE` when deployed;
- Balance;
- Equity;
- Available;
- Initial Margin / IM rate;
- continuous trading / daily target OFF;
- capital allocator reserve + slot limits;
- Smart CUT state;
- positions/orders, realized PnL, AI and loss streak.

## DEPLOYMENT CONTRACT

Canonical workflow: `.github/workflows/deploy-cloudflare-worker.yml`.
A production claim is valid only when:
1. current `main` contains intended source;
2. `npm run check` passes;
3. Cloudflare deploy succeeds;
4. `/bybit/health` reports the expected deployment revision;
5. mode/auth/ack/scheduler/ready remain valid.

Do not call source-only changes LIVE.
