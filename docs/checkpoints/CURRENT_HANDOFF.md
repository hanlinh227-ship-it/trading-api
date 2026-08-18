# CURRENT HANDOFF — TRADING PROJECT

Updated: 2026-08-18 UTC+7

## READ FIRST
1. `V77180_AUTO_READY_CONSOLIDATED.md`
2. `MASTER_TRADING_STATE.md`
3. `ENTRY_EXECUTION_V76.md` and relevant market checkpoints when needed.

## CURRENT CANONICAL
**V77.18.9 source is the latest canonical runtime**. Production entrypoint remains `cloudflare-worker/index.js`.
Cloudflare is deployment only; never maintain a second hand-edited Worker copy.

Latest Hyro commits:
- `3ae1a81e` — separate DEMO vs LIVE Bybit credentials.
- `5acb1303` — hardened Hyro auto-cycle state and explicit fail-closed reasons.
- `de91e842` — environment-aware controls/status.
- `f7f3cfb6` / `b751c943` — zero-equity fail-closed and P/L display protection.
- `7e6c264e` — V77.18.8: Hyro CHALLENGE profile is forced to Bybit DEMO execution environment; FUNDED may use configured LIVE/subaccount mode later.
- `87f7e589` — V77.18.9: durable PROP execution notifications for actual submitted orders and actual position closures, with KV dedup/snapshot state.

## NON-NEGOTIABLE RUNTIME SEPARATION
### SIGNAL
- Telegram signal/scanner system only.
- Preserves legacy Signal/LIVE ORDERS behavior.
- Does NOT feed PROP or PERSONAL execution.

### PROP / HYROTRADER
- Independent auto-trading runtime using `hyro-scanner.js` + `hyro-execution.js` + `hyro-runtime.js`.
- Does NOT consume SIGNAL Telegram entries/candidates.
- Telegram MUST NOT announce scanner candidates.
- NEW user requirement: Telegram MAY notify **actual PROP execution events only**:
  - when an order is really submitted: short `PROP - HyroTrader` notice with symbol, BUY/SELL, SL price + estimated USD risk, TP price + estimated USD reward;
  - when a previously open PROP position closes and closed-PnL count confirms closure: short `TP DONE` / `SL HIT` style notice with actual P/L delta;
  - if multiple PROP positions close inside the same polling interval, send one aggregate close summary rather than invent per-trade P/L allocation.
- Actual account positions/PnL/runtime status remain viewable.

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
Current Hyro Challenge uses the Bybit Demo account/API environment.
Therefore:
- CHALLENGE uses `HYRO_BYBIT_API_KEY` + `HYRO_BYBIT_API_SECRET`.
- CHALLENGE endpoint is `api-demo.bybit.com`.
- Production LIVE wallet/key is not the Challenge balance.
- V77.18.8+ enforces this by profile routing inside `index.js`; CHALLENGE is forced to effective DEMO mode even if raw Cloudflare `HYRO_BYBIT_MODE=LIVE` remains set.
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

Raw selector may remain `HYRO_BYBIT_MODE=DEMO|LIVE`, but effective routing overrides it for profile `phase=CHALLENGE` and forces DEMO.

Auto selector:
- `HYRO_AUTO_EXECUTION=true|false`

## EXECUTION EVIDENCE
Controlled Bybit DEMO tests already passed:
- real pending order create
- order verification
- native SL/TP verification
- cancel verification
- full-cycle DEMO market fill / position visibility / close support

## HYRO AUTO EXECUTION
Scheduled Worker cron remains every minute (`* * * * *`).
Each PROP cycle is independent from SIGNAL and follows:
1. profile exists
2. effective environment selected by profile (CHALLENGE => DEMO)
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
14. after successful submit, Telegram sends one deduplicated execution notice
15. polling snapshots monitor actual position disappearance + closed-PnL count/net change to send one deduplicated close notice

## PROP EXECUTION NOTIFICATION FORMAT
Entry example:
`PROP - HyroTrader`
`🟢 XRPUSDT BUY`
`SL: 0.9387 (~$55.00)`
`TP: 0.9671 (~$110.00)`

Close example:
`PROP - HyroTrader`
`✅ TP DONE XRPUSDT`
`P/L: +$108.42`

or
`PROP - HyroTrader`
`❌ SL HIT XRPUSDT`
`P/L: -$54.73`

The SL/TP USD shown on entry is an estimate from `|entry-level| * qty` before fees/slippage. The close P/L is based on actual account closed-net delta for the confirmed closure interval.

## STATE CONTINUITY — NEVER DELETE/RESET
- KV binding remains `TRADING_STATE`; preserve existing namespace ID.
- Existing Signal/LIVE ORDERS keys remain untouched.
- Existing PERSONAL state remains untouched.
- Hyro profile: `v7717:hyro:profile`
- Hyro wizard draft: `v77171:hyro:draft`
- Hyro manual control: `v77173:hyro:control`
- Hyro runtime/execution/day/idempotency keys: `v7718:hyro:*`
- Notification dedup keys: `v7718:hyro:notify:*`
- Notification position/PnL snapshot: `v7718:hyro:notify:snapshot`
- Deploy/update must be non-destructive; do not recreate/clear `TRADING_STATE`.
- Source deploys must use the same KV binding and keep vars/secrets. Updating code must never clear Signal LIVE ORDERS, PROP execution/idempotency state, or PERSONAL state.

## REPOSITORY/CLOUDFLARE CONTRACT
- Do not restore legacy `apply-v*.yml` or `scripts/apply_v*.js` chains.
- Deploy only `cloudflare-worker/index.js` as canonical entrypoint.
- Keep same `TRADING_STATE` namespace and `keep_vars`.
- Never recreate/clear state during deploy.

## IMMEDIATE NEXT STEP
Cloudflare must deploy/promote source containing commit `87f7e589` to 100% traffic. After deployment:
1. Challenge remains effective DEMO and uses the Challenge Bybit Demo API.
2. No candidate messages are sent from PROP.
3. The next actual PROP order submission sends the compact `PROP - HyroTrader` entry notice.
4. When an actually open PROP position later closes and closed-PnL confirms it, send the compact TP/SL/P&L notice.
5. Existing Signal/LIVE ORDERS, PROP state/idempotency, and PERSONAL state must remain intact through deployment.

## FROZEN/HISTORICAL KNOWLEDGE STILL ACTIVE
- V73 statistical prior remains frozen; do not rebuild/retune from live outcomes.
- V74 market-data integrity/freshness authority remains active where applicable.
- V76 R2 rejected methods remain rejected; do not restore them.
- Existing market-specific Signal knowledge and durable LIVE ORDERS behavior remain active unless explicitly superseded.

## NEW CHAT PROMPT
`Tiếp tục toàn bộ dự án Trading từ GitHub mới nhất. BẮT BUỘC đọc docs/checkpoints/CURRENT_HANDOFF.md trước, sau đó V77180_AUTO_READY_CONSOLIDATED.md và MASTER_TRADING_STATE.md. Canonical hiện là V77.18.9. SIGNAL, PROP/Hyro và PERSONAL hoàn toàn độc lập. Hyro hiện là CHALLENGE One-Step 5K Bybit Standard/Trailing; Challenge phải dùng Bybit Demo Trading với HYRO_BYBIT_API_KEY/SECRET. PROP không phát candidate nhưng từ V77.18.9 được phép gửi thông báo ngắn khi lệnh thật được submit và khi vị thế thật đóng: PROP - HyroTrader + symbol/side/SL/TP USD, sau đó TP DONE hoặc SL HIT + P/L thật. Notification dùng KV dedup/snapshot riêng. Bảo toàn toàn bộ KV/LIVE ORDERS/state Signal, PROP và PERSONAL qua mọi deploy; không reset namespace hay quay lại workflow/phương pháp đã loại.`