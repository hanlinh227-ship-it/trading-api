# CURRENT HANDOFF — TRADING PROJECT

Updated: 2026-08-18 UTC+7

## READ FIRST
1. `V77180_AUTO_READY_CONSOLIDATED.md`
2. `MASTER_TRADING_STATE.md`
3. `ENTRY_EXECUTION_V76.md` and relevant market checkpoints when needed.

## CURRENT CANONICAL
**V77.18.6 source is the latest canonical runtime**. Production entrypoint remains `cloudflare-worker/index.js`.
Cloudflare is deployment only; never maintain a second hand-edited Worker copy.

Latest Hyro commits:
- `3ae1a81e` — separate DEMO vs LIVE Bybit credentials.
- `5acb1303` — hardened Hyro auto-cycle state, explicit reasons, stale-error recovery, fail-closed cycle errors.
- `de91e842` — V77.18.6 Telegram LIVE display: hide DEMO controls in LIVE, block DEMO callbacks in LIVE, clearer runtime/telemetry status.

## NON-NEGOTIABLE RUNTIME SEPARATION
### SIGNAL
- Telegram signal/scanner system only.
- Preserves legacy Signal/LIVE ORDERS behavior.
- Does NOT feed PROP or PERSONAL execution.

### PROP / HYROTRADER
- Independent auto-trading runtime using `hyro-scanner.js` + `hyro-execution.js` + `hyro-runtime.js`.
- Does NOT consume SIGNAL Telegram entries/candidates.
- Telegram PROP is ACCOUNT MONITORING/CONTROL only.
- Telegram MUST NOT push/announce/mirror Hyro auto-entry candidates/orders.
- Auto entries remain silent; only actual account positions/PnL/runtime status may be viewed.

### PERSONAL
- Independent reserved runtime. No routing from SIGNAL or PROP.

## HYRO SUPPORT / PERMISSION STATE
Hyro Support confirmed:
- Existing Hyro-connected API key must not be modified/deleted until reconnect becomes available near expiry.
- A private trading bot must use a **separate API key** from the key HyroTrader uses.
- Custom bot is permitted during Challenge and Funded stages if it trades only the user's own strategy and complies with rules.
- Copy trading, account mirroring, external signal services, coordinated multi-account trading, HFT and latency arbitrage remain prohibited.

## HYRO ACCOUNT CURRENT STATE
- Active HYRO CHALLENGE.
- One-Step.
- 5K USDT.
- Futures / Bybit.
- Standard / Trailing.
- Hyro dashboard reference balance shown: $5,000.

## BYBIT / CLOUDFLARE CREDENTIAL ROUTING
DEMO credentials:
- `HYRO_BYBIT_API_KEY`
- `HYRO_BYBIT_API_SECRET`
- endpoint: `api-demo.bybit.com`

LIVE credentials:
- `HYRO_BYBIT_LIVE_API_KEY`
- `HYRO_BYBIT_LIVE_API_SECRET`
- endpoint: `api.bybit.com`

Mode selector:
- `HYRO_BYBIT_MODE=DEMO|LIVE`

Auto selector:
- `HYRO_AUTO_EXECUTION=true|false`

Current user-side Cloudflare configuration shown:
- `HYRO_BYBIT_MODE=LIVE`
- `HYRO_AUTO_EXECUTION=true`
- LIVE bot credentials added separately from DEMO credentials.

Latest Telegram LIVE connection evidence shown by user:
- Mode: LIVE
- Credentials: OK
- Fresh telemetry: CONNECTED
- Auto execution secret: ON
- Manual pause: OFF
- wallet: PASS
- positions: PASS
- orders: PASS
- closedPnl: PASS

Earlier `10003 API key is invalid` was resolved by creating/using production LIVE API credentials rather than Demo credentials.

## DEMO EXECUTION EVIDENCE
Controlled DEMO tests already passed before LIVE switch:
- real Bybit DEMO pending order create
- order verification
- native SL/TP verification
- cancel verification
- full-cycle DEMO market fill/position/close support added

V77.18.6 hides DEMO test buttons in LIVE and rejects DEMO test callbacks while LIVE.

## HYRO AUTO EXECUTION
Scheduled Worker cron remains every minute (`* * * * *`).
Each PROP cycle is independent from SIGNAL and follows:
1. profile exists
2. fresh telemetry connected
3. not manually paused
4. `HYRO_AUTO_EXECUTION=true`
5. daily target not reached
6. daily hard stop not reached
7. max active slots / duplicate symbol / combined risk gates pass
8. independent Hyro dynamic scanner finds MARKET_PLAN or LIMIT_PLAN
9. planned RR >= 1.5 and structural SL/TP/risk sizing pass
10. Bybit native order is submitted with native SL/TP
11. idempotency state prevents duplicate intent

V77.18.6 runtime reasons are explicit, including:
- `WAITING_FIRST_CYCLE`
- `NO_ELIGIBLE_CANDIDATE`
- `CANDIDATES_BLOCKED`
- `EXECUTION_REJECTED`
- `ORDER_SUBMITTED`
- `MANUAL_PAUSED`
- `AUTO_EXECUTION_DISABLED`
- `DAILY_PROFIT_TARGET_REACHED`
- `DAILY_HARD_STOP`
- `MAX_ACTIVE_SLOTS_REACHED`
- `CYCLE_ERROR`

A stale previous `TELEMETRY_ERROR` must not be presented as the current connection state when fresh telemetry is already PASS.

## HYRO RISK/POLICY
- Daily strategy objective fixed at +5% of configured account size.
- Risk firewall always overrides profit objective.
- Internal daily hard stop remains below 3% account size.
- Native structural SL required; never widen stop.
- TP follows structure/liquidity; planned RR >= 1.5.
- Maximum 2 active Hyro symbols across filled positions + pending orders.
- No duplicate active symbol.
- Manual PAUSE blocks new Hyro entries and cancels pending orders, but monitoring/existing-position protection continues.
- Daily +5% or daily hard stop blocks new entries and cancels remaining pending orders.

## STATE CONTINUITY — NEVER DELETE/RESET
- KV binding remains `TRADING_STATE`; preserve existing namespace ID.
- Existing Signal/LIVE ORDERS keys remain untouched.
- Hyro profile: `v7717:hyro:profile`
- Hyro wizard draft: `v77171:hyro:draft`
- Hyro manual control: `v77173:hyro:control`
- Hyro runtime/execution/day/idempotency keys: `v7718:hyro:*`
- Migrations must remain non-destructive.

## REPOSITORY/CLOUDFLARE CONTRACT
- Do not restore legacy `apply-v*.yml` or `scripts/apply_v*.js` chains.
- Deploy only `cloudflare-worker/index.js` as canonical entrypoint.
- Keep same `TRADING_STATE` namespace and `keep_vars`.
- Never recreate/clear state during deploy.

## IMMEDIATE NEXT STEP
Cloudflare must deploy/promote the latest source containing commit `de91e842` to 100% traffic. After that:
1. Telegram `KẾT NỐI` should show LIVE + 4 telemetry PASS and no DEMO test buttons.
2. Wait for the next minute cron; `Auto engine` should refresh from any stale state into an explicit current-cycle state.
3. If scanner finds a qualified setup and all gates pass, PROP may submit a real LIVE order silently with native SL/TP.
4. Do not manually create a LIVE test order merely to prove execution.

## FROZEN/HISTORICAL KNOWLEDGE STILL ACTIVE
- V73 statistical prior remains frozen; do not rebuild/retune from live outcomes.
- V74 market-data integrity/freshness authority remains active where applicable.
- V76 R2 rejected methods remain rejected; do not restore them.
- Existing market-specific Signal knowledge and durable LIVE ORDERS behavior remain active unless explicitly superseded.

## NEW CHAT PROMPT
`Tiếp tục toàn bộ dự án Trading từ GitHub mới nhất. BẮT BUỘC đọc docs/checkpoints/CURRENT_HANDOFF.md trước, sau đó V77180_AUTO_READY_CONSOLIDATED.md và MASTER_TRADING_STATE.md. Canonical source hiện là V77.18.6. SIGNAL, PROP/Hyro và PERSONAL hoàn toàn độc lập. Hyro Challenge One-Step 5K Bybit Standard/Trailing đã chuyển LIVE bằng bộ HYRO_BYBIT_LIVE_API_KEY/SECRET riêng; Telegram đã từng xác nhận Mode LIVE, Credentials OK, Fresh telemetry CONNECTED và wallet/positions/orders/closedPnl đều PASS. HYRO_AUTO_EXECUTION=true. DEMO controls phải ẩn/blocked khi LIVE. Runtime cron mỗi phút phải fail-closed và chỉ auto order từ Hyro scanner độc lập khi toàn bộ telemetry/risk/RR/native SL-TP/idempotency gates pass. Bảo toàn toàn bộ KV/LIVE ORDERS/state và không quay lại workflow/phương pháp đã loại.`
