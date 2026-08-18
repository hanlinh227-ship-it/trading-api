# CURRENT HANDOFF — TRADING PROJECT

Updated: 2026-08-18 UTC+7

## READ FIRST
1. `V77180_AUTO_READY_CONSOLIDATED.md`
2. `MASTER_TRADING_STATE.md`
3. `ENTRY_EXECUTION_V76.md` and relevant market checkpoints when needed.

## CURRENT CANONICAL
**V77.18.8 source is the latest canonical runtime**. Production entrypoint remains `cloudflare-worker/index.js`.
Cloudflare is deployment only; never maintain a second hand-edited Worker copy.

Latest Hyro commits:
- `3ae1a81e` — separate DEMO vs LIVE Bybit credentials.
- `5acb1303` — hardened Hyro auto-cycle state and explicit fail-closed reasons.
- `de91e842` — V77.18.6 Telegram environment-aware controls/status.
- `f7f3cfb6` / `b751c943` — zero-equity fail-closed and P/L display protection.
- `7e6c264e` — V77.18.8: **Hyro CHALLENGE profile is forced to Bybit DEMO execution environment** regardless of the raw `HYRO_BYBIT_MODE` Cloudflare value; FUNDED may use configured LIVE/subaccount mode later.

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
Hyro Support directly confirmed to user by email:
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

## CRITICAL ENVIRONMENT RULE — CHALLENGE = BYBIT DEMO
HyroTrader's current public platform documentation states the Bybit Challenge is completed using a **Bybit Demo account**. Bybit Demo Trading is an isolated account with its own UID/API key and uses `https://api-demo.bybit.com`.

Therefore:
- CHALLENGE must use `HYRO_BYBIT_API_KEY` + `HYRO_BYBIT_API_SECRET` (Demo Trading key).
- CHALLENGE execution endpoint must be `api-demo.bybit.com`.
- Production LIVE wallet/key is **not** the Challenge balance and may legitimately show $0.
- V77.18.8 enforces this by profile routing inside `index.js`; CHALLENGE is forced to effective DEMO mode even if raw Cloudflare `HYRO_BYBIT_MODE=LIVE` remains set.
- FUNDED/subaccount routing is separate and may use `HYRO_BYBIT_LIVE_API_KEY` + `HYRO_BYBIT_LIVE_API_SECRET` when appropriate.

## BYBIT / CLOUDFLARE CREDENTIAL ROUTING
Challenge / Demo credentials:
- `HYRO_BYBIT_API_KEY`
- `HYRO_BYBIT_API_SECRET`
- endpoint: `api-demo.bybit.com`

Future Live/Funded credentials:
- `HYRO_BYBIT_LIVE_API_KEY`
- `HYRO_BYBIT_LIVE_API_SECRET`
- endpoint: `api.bybit.com`

Raw selector may remain:
- `HYRO_BYBIT_MODE=DEMO|LIVE`

But V77.18.8 effective routing rule overrides it for profile `phase=CHALLENGE` and forces DEMO.

Auto selector:
- `HYRO_AUTO_EXECUTION=true|false`

## EXECUTION EVIDENCE
Controlled Bybit DEMO tests already passed:
- real pending order create
- order verification
- native SL/TP verification
- cancel verification
- full-cycle DEMO market fill / position visibility / close support

These tests occurred in the same Bybit Demo environment used for the Hyro Challenge.

## HYRO AUTO EXECUTION
Scheduled Worker cron remains every minute (`* * * * *`).
Each PROP cycle is independent from SIGNAL and follows:
1. profile exists
2. effective account environment is selected by profile (CHALLENGE => DEMO)
3. fresh telemetry connected
4. account equity > 0
5. not manually paused
6. `HYRO_AUTO_EXECUTION=true`
7. daily target not reached
8. daily hard stop not reached
9. max active slots / duplicate symbol / combined risk gates pass
10. independent Hyro dynamic scanner finds MARKET_PLAN or LIMIT_PLAN
11. planned RR >= 1.5 and structural SL/TP/risk sizing pass
12. Bybit native order is submitted with native SL/TP
13. idempotency state prevents duplicate intent

Current runtime reasons include:
- `NO_ELIGIBLE_CANDIDATE`
- `CANDIDATES_BLOCKED`
- `EXECUTION_REJECTED`
- `ORDER_SUBMITTED`
- `ACCOUNT_EQUITY_ZERO_OR_UNAVAILABLE`
- `MANUAL_PAUSED`
- `AUTO_EXECUTION_DISABLED`
- `DAILY_PROFIT_TARGET_REACHED`
- `DAILY_HARD_STOP`
- `MAX_ACTIVE_SLOTS_REACHED`
- `CYCLE_ERROR`

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
Cloudflare must deploy/promote source containing commit `7e6c264e` to 100% traffic. After deployment:
1. Telegram `KẾT NỐI` for the current CHALLENGE must show effective `Mode: DEMO (forced by Challenge profile)`.
2. Wallet/equity should return to the Bybit Demo Challenge account (previously around $4,994.97 rather than LIVE wallet $0).
3. P/L/Peak/DD must again use the Challenge account, not the production wallet.
4. Wait for next minute cron; AUTO may run only if telemetry/equity/risk gates pass.
5. If a qualified setup exists, PROP may submit an order silently to the Bybit Demo Challenge with native SL/TP.

## FROZEN/HISTORICAL KNOWLEDGE STILL ACTIVE
- V73 statistical prior remains frozen; do not rebuild/retune from live outcomes.
- V74 market-data integrity/freshness authority remains active where applicable.
- V76 R2 rejected methods remain rejected; do not restore them.
- Existing market-specific Signal knowledge and durable LIVE ORDERS behavior remain active unless explicitly superseded.

## NEW CHAT PROMPT
`Tiếp tục toàn bộ dự án Trading từ GitHub mới nhất. BẮT BUỘC đọc docs/checkpoints/CURRENT_HANDOFF.md trước, sau đó V77180_AUTO_READY_CONSOLIDATED.md và MASTER_TRADING_STATE.md. Canonical hiện là V77.18.8. SIGNAL, PROP/Hyro và PERSONAL hoàn toàn độc lập. Hyro hiện là CHALLENGE One-Step 5K Bybit Standard/Trailing; Challenge phải dùng Bybit Demo Trading (`api-demo.bybit.com`) với HYRO_BYBIT_API_KEY/SECRET. V77.18.8 profile-routing bắt buộc CHALLENGE=>DEMO dù raw Cloudflare HYRO_BYBIT_MODE có đang là LIVE; LIVE credentials chỉ dành cho funded/subaccount sau này. HYRO_AUTO_EXECUTION=true nhưng runtime phải fail-closed khi telemetry/equity/risk không hợp lệ. Bảo toàn toàn bộ KV/LIVE ORDERS/state và không quay lại workflow/phương pháp đã loại.`
