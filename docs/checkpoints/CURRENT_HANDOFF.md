# CURRENT HANDOFF — TRADING PROJECT

Updated: 2026-08-18 UTC+7

## READ FIRST
1. `V77180_AUTO_READY_CONSOLIDATED.md` — current canonical runtime/auto-trade state.
2. `MASTER_TRADING_STATE.md` — historical/frozen architecture and market-method context.
3. `ENTRY_EXECUTION_V76.md` and relevant market checkpoints when needed.

## CURRENT CANONICAL

**V77.18.2** is the current consolidated runtime. Any older V77.x runtime text in MASTER/checkpoints is historical unless V77.18.2 explicitly preserves it.

Production entrypoint: `cloudflare-worker/index.js`.
Cloudflare is deployment only; do not maintain a second hand-edited Worker copy.

## NON-NEGOTIABLE RUNTIME SEPARATION

### SIGNAL
- Telegram signal/scanner system only.
- Preserves all working Signal/LIVE ORDERS logic from the legacy V77.16.8/V77.17 stack.
- Does NOT feed PROP execution.
- Does NOT feed PERSONAL execution.

### PROP / HYROTRADER
- Independent auto-trading runtime using `hyro-scanner.js` + `hyro-execution.js` + `hyro-runtime.js`.
- Does NOT consume SIGNAL Telegram entries/candidates.
- Telegram PROP is ACCOUNT MONITORING/CONTROL only.
- Telegram may show account config, wallet/equity/available, daily equity P/L, realized profit, realized loss, net realized P/L, floating P/L, peak/DD, open positions, open-risk, pending count, connection/auto/pause state.
- Telegram MUST NOT push, announce, mirror or expose Hyro auto-entry candidates/orders.
- Auto entries remain silent; only actual account positions/PnL may be viewed.

### PERSONAL
- Independent reserved runtime.
- No order/state routing from SIGNAL or PROP.

## HYRO ACCOUNT WIZARD
Stored profile asks:
1. CHALLENGE or FUNDED;
2. account size;
3. Standard/Trailing or Swing/Static;
4. Challenge only: One-Step or Two-Step.

Runtime state persists in KV and survives version upgrades.

## HYRO RISK/POLICY
- Daily strategy objective fixed at +5% of configured account size.
- Risk firewall always overrides profit objective.
- Internal daily hard stop remains below 3% of account size.
- Native structural SL required; never widen stop.
- TP follows structure/liquidity; planned RR >= 1.5.
- Maximum 2 active Hyro symbols across filled positions + pending orders.
- No duplicate active symbol.
- Manual PAUSE blocks new Hyro entries, cancels pending orders, but does not stop Signal scanner or account/position monitoring.
- Reaching daily +5% or daily hard stop blocks new entries and cancels remaining pending orders.
- HYRO_AUTO_EXECUTION defaults OFF; HYRO_BYBIT_MODE defaults DEMO.

## STATE CONTINUITY — NEVER DELETE/RESET
- KV binding remains `TRADING_STATE` and the existing namespace ID must be preserved.
- Existing Signal/LIVE ORDERS keys remain untouched, including legacy books/order archives.
- Hyro profile: `v7717:hyro:profile`
- Hyro wizard draft: `v77171:hyro:draft`
- Hyro manual control: `v77173:hyro:control`
- Hyro runtime/execution/day/idempotency keys: `v7718:hyro:*`
- New versions must read/preserve these states before adding replacements. Migration must be non-destructive.

## REPOSITORY CLEANUP
- Legacy `.github/workflows/apply-v*.yml` auto-promotion workflows are removed from `main`.
- Legacy `scripts/apply_v*.js` migration scripts are removed from `main`.
- Audit/validation/research assets may remain if they cannot rewrite canonical production code.
- Market data, symbol knowledge, checkpoints, Signal engine modules and all KV state are preserved.

## CLOUDFLARE DEPLOYMENT CONTRACT
- Deploy `cloudflare-worker/index.js` as canonical entrypoint.
- Keep the same `TRADING_STATE` KV namespace; never recreate/clear it during deploy.
- Required Hyro secrets when connecting account: `HYRO_BYBIT_API_KEY`, `HYRO_BYBIT_API_SECRET`.
- `HYRO_BYBIT_MODE=DEMO|LIVE`.
- `HYRO_AUTO_EXECUTION=true` is the final execution arming switch and must remain false until account telemetry/API testing passes.

## FROZEN/HISTORICAL KNOWLEDGE STILL ACTIVE
- V73 statistical prior remains frozen; do not rebuild/retune from live outcomes.
- Existing market-specific Signal knowledge, market-data integrity, fresh-price requirements and durable LIVE ORDERS behavior remain active unless explicitly superseded here.
- Do not restore deleted legacy score-only authority or old migration chains.

## NEW CHAT PROMPT
`Continue the Trading project from docs/checkpoints/CURRENT_HANDOFF.md and docs/checkpoints/V77180_AUTO_READY_CONSOLIDATED.md first, then MASTER_TRADING_STATE.md for historical/frozen context. Current canonical is V77.18.2. Preserve every active KV/LIVE ORDER state across versions. SIGNAL, PROP/Hyro and PERSONAL are strictly independent. PROP Telegram is account monitoring/control only and must never publish Hyro auto-entry candidates/orders. Hyro auto-trade uses its own scanner/execution/runtime, fixed +5% daily strategy objective with risk firewall priority, internal daily hard stop below 3%, structural native SL, adaptive structure/liquidity TP, max 2 active symbols, no duplicates, manual pause, DEMO/AUTO OFF by default. Do not restore legacy apply workflows/scripts or maintain a second Cloudflare codebase.`
