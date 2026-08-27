# BYBIT AUTO ON/OFF RUNBOOK — HARD CHECKPOINT

Updated: 2026-08-27 UTC+7
Purpose: future chats must use this checkpoint before changing Bybit Auto execution state.

## SCOPE
This checkpoint is ONLY for the Bybit Auto branch. Forex/MT5 and Meme branches are separate and MUST NOT be enabled/disabled as a side effect.

## CANONICAL RUNTIME
- Production: Unified Trading Hub / Cloudflare Worker.
- Bybit execution authority: BYBIT_AUTO_TRADE_ONLY.
- Current generation at checkpoint creation: BYBIT-AUTO-1.8.3.
- Bybit AI final-entry review: Claude + Codex only. DeepSeek is disabled from active runtime.
- Private transport: VPS_BYBIT_PRIVATE_PROXY.
- Market transport: VPS_BYBIT_MARKET_PROXY.
- Canonical health: `/bybit/health`.
- Entry health: `/bybit/entry-health`.
- Runtime contract: `/runtime/contract`.

## THREE SWITCHES — DO NOT CONFUSE THEM
Bybit LIVE execution requires ALL of these to be true:
1. `BYBIT_AUTO_ENABLED=true` — scheduler is allowed to run Bybit Auto.
2. `BYBIT_AUTO_LIVE=true` — execution mode is LIVE rather than PAPER/non-live.
3. `BYBIT_AUTO_LIVE_ACK=true` — explicit live-trading acknowledgement.

Turning only one or two switches ON is NOT sufficient to declare the bot LIVE-ready.

## TURN BYBIT AUTO ON
Set/deploy ONLY the Bybit branch so that:
- `BYBIT_AUTO_ENABLED=true`
- `BYBIT_AUTO_LIVE=true`
- `BYBIT_AUTO_LIVE_ACK=true`

Do NOT enable Forex as part of this operation. Preserve the independent Forex setting.

After deployment, NEVER report success from config/source alone. Verify production `/bybit/health` and require at minimum:
- `ok=true`
- `authenticated=true`
- `mode="LIVE"`
- `execution.liveAck=true`
- `execution.scheduled=true`
- `execution.ready=true`
- `privateTransport="VPS_BYBIT_PRIVATE_PROXY"`
- `marketTransport="VPS_BYBIT_MARKET_PROXY"`
- account equity/balance can be read from the real account
- runtime revision/version matches the intended deployed source

Then inspect `/bybit/entry-health`. `WAITING_FOR_QUALITY_SETUP` is NOT a connectivity failure; it means runtime is ready but no acceptable setup exists yet. Hard blockers must be resolved before claiming entry-ready.

## TURN BYBIT AUTO OFF — SAFE STOP
Preferred normal stop when the goal is "do not open any new Bybit trades":
- set `BYBIT_AUTO_ENABLED=false`
- set `BYBIT_AUTO_LIVE_ACK=false`

This disables scheduler-driven new entries and removes live acknowledgement. Do not alter Forex/Meme.

If a stronger maintenance lock is desired, also set:
- `BYBIT_AUTO_LIVE=false`

IMPORTANT: before changing code/config around an account that may have an open position, first inspect `/bybit/health` for `positions.openCount` and `openOrdersCount`. Do not assume that disabling the scheduler automatically closes or protects an already-open exchange position. Existing positions/orders require explicit lifecycle handling according to the current engine and must never be silently abandoned.

After OFF deployment, verify production. Do not claim OFF merely because GitHub says the variable changed. Health/status must show scheduler/live acknowledgement disabled as intended.

## EMERGENCY PRINCIPLE
If the user says "tắt bot Bybit", "khóa Bybit", "không trade Bybit nữa", interpret this as stopping NEW Bybit execution while preserving other branches. First inspect current positions/orders when possible. Never cancel/close a real position merely from an ambiguous request; distinguish STOP NEW ENTRIES from CLOSE EXISTING POSITION.

## RE-ENABLE PRINCIPLE
When the user later says "bật lại Bybit" or "nối lại auto Bybit", fresh-read GitHub main and this checkpoint first. Restore the three-switch LIVE contract, deploy, then verify real production health. Do not reuse stale chat assumptions.

## SAFETY / SEPARATION LOCK
- Bybit and Forex are independent branches.
- Changing Bybit ON/OFF must not modify `FOREX_AUTO_LIVE` or MT5 runtime.
- Health requests are read-only and must never submit orders, change leverage, or cancel orders.
- Never expose API secrets/action keys in chat or checkpoint files.
- Never call the bot LIVE-ready unless production evidence confirms it.

## CURRENT KNOWN-GOOD CONNECTION SHAPE
`Cloudflare Worker -> VPS Bybit private/market proxies -> Bybit API/account`

A known-good health response has previously confirmed authenticated LIVE access, scheduler enabled, liveAck enabled, ready=true, real equity readable, zero or known positions/orders, and both VPS transports verified.

## FUTURE CHAT STARTUP RULE
For any future request to enable, disable, reconnect, or diagnose Bybit Auto:
1. Fresh-read GitHub `main`.
2. Read this file: `docs/checkpoints/BYBIT_AUTO_ON_OFF_RUNBOOK_20260827.md`.
3. Read `docs/checkpoints/CURRENT_HANDOFF.md`, but prefer newer source/runtime evidence if it conflicts.
4. Inspect current Bybit source/config/deployment workflow.
5. Inspect production health before and after any state change.
6. Preserve Forex/Meme branch state unless the user explicitly asks to change them.
