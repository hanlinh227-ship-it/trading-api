# CURRENT HANDOFF — TRADING PROJECT

Updated: 2026-08-18 UTC+7

## READ FIRST
1. `V77180_AUTO_READY_CONSOLIDATED.md`
2. `MASTER_TRADING_STATE.md`
3. `ENTRY_EXECUTION_V76.md` and relevant market checkpoints when needed.

## CURRENT CANONICAL
**V77.18.10 source is the latest canonical runtime**. Production entrypoint remains `cloudflare-worker/index.js`.
Cloudflare is deployment only; never maintain a second hand-edited Worker copy.

Latest Hyro commits:
- `3ae1a81e` — separate DEMO vs LIVE Bybit credentials.
- `5acb1303` — hardened Hyro auto-cycle state and explicit fail-closed reasons.
- `de91e842` — environment-aware controls/status.
- `f7f3cfb6` / `b751c943` — zero-equity fail-closed and P/L display protection.
- `7e6c264e` — V77.18.8: Hyro CHALLENGE profile forced to Bybit DEMO execution environment; FUNDED may use configured LIVE/subaccount mode later.
- `87f7e589` — V77.18.9: durable PROP execution notifications for actual submitted orders and actual position closures, with KV dedup/snapshot state.
- `849bfc48` — quick MARKET-only cycle support in `hyro-runtime.js`.
- `4fe83372` — V77.18.10: Telegram `🔎 QUÉT NHANH MARKET` plus automatic Hyro telemetry refresh/reconnect on requests and scheduled cycles.

## NON-NEGOTIABLE RUNTIME SEPARATION
### SIGNAL
- Telegram signal/scanner system only.
- Preserves legacy Signal/LIVE ORDERS behavior.
- Does NOT feed PROP or PERSONAL execution.

### PROP / HYROTRADER
- Independent auto-trading runtime using `hyro-scanner.js` + `hyro-execution.js` + `hyro-runtime.js`.
- Does NOT consume SIGNAL Telegram entries/candidates.
- Regular AUTO remains independent and may use MARKET_PLAN or LIMIT_PLAN.
- Telegram MUST NOT announce scanner candidates during normal AUTO.
- Manual `🔎 QUÉT NHANH MARKET` runs one immediate MARKET-only full cycle. If a MARKET passes all telemetry/risk/RR/execution gates it may submit immediately; otherwise Telegram reports the reason without exposing candidate stream.
- Telegram may notify actual PROP execution events only:
  - actual submitted order: short `PROP - HyroTrader` notice with symbol, BUY/SELL, SL price + estimated USD risk, TP price + estimated USD reward;
  - actual closure confirmed by position disappearance + closed-PnL delta: short `TP DONE` / `SL HIT` style notice with actual P/L delta.

### PERSONAL
- Independent reserved runtime. No routing from SIGNAL or PROP.

## HYRO SUPPORT / PERMISSION STATE
Hyro Support directly confirmed to user by email:
- Existing Hyro-connected API key must not be modified/deleted until reconnect becomes available near expiry.
- A private trading bot must use a separate API key from the key HyroTrader uses.
- Custom bot is permitted during Challenge and Funded stages if it trades only the user's own strategy and complies with rules.
- Copy trading, account mirroring, external signal services, coordinated multi-account trading, HFT and latency arbitrage remain prohibited.

## HYRO ACCOUNT CURRENT STATE
- Active HYRO CHALLENGE.
- One-Step.
- 5K USDT.
- Futures / Bybit.
- Standard / Trailing.
- Challenge uses Bybit Demo Trading account/API.

## CRITICAL ENVIRONMENT RULE — CHALLENGE = BYBIT DEMO
- CHALLENGE uses `HYRO_BYBIT_API_KEY` + `HYRO_BYBIT_API_SECRET`.
- CHALLENGE endpoint is `api-demo.bybit.com`.
- Production LIVE wallet/key is not the Challenge balance.
- V77.18.8+ profile routing forces effective DEMO mode when `phase=CHALLENGE`, even if raw Cloudflare `HYRO_BYBIT_MODE=LIVE` remains set.
- FUNDED/subaccount routing may use `HYRO_BYBIT_LIVE_API_KEY` + `HYRO_BYBIT_LIVE_API_SECRET` later.

## AUTO RECONNECT / REFRESH — V77.18.10
Hyro API does not require a persistent socket session for these REST calls. “Reconnect” means fresh authenticated telemetry probes are run automatically.
- Every Worker scheduled PROP cycle refreshes telemetry before auto scanning.
- Every Worker request schedules a background PROP telemetry refresh.
- After a code deploy/update, the next cron (maximum about one minute) refreshes Challenge telemetry automatically even if user does not press `KẾT NỐI`.
- Any Telegram/API request after deploy also triggers background refresh immediately.
- `KẾT NỐI` is now a status/diagnostic action, not a required activation step.
- Connection panel displays `Auto reconnect: ON (cron + request refresh)`.

## QUICK MARKET SCAN — V77.18.10
Telegram PROP has button `🔎 QUÉT NHANH MARKET`.
When pressed:
1. use effective environment by profile (CHALLENGE => DEMO);
2. refresh account telemetry;
3. enforce equity > 0, manual pause, auto-execution secret, daily target/hard-stop, active-slot and combined-risk gates;
4. run Hyro broad/deep scanner immediately;
5. accept **MARKET_PLAN only** for quick scan; LIMIT plans are ignored in this manual quick cycle;
6. sort eligible MARKET candidates by available scanner score when present;
7. execute the best candidate that also passes execution gate, native SL/TP and idempotency;
8. if none passes, return a short reason such as `NO_MARKET_CANDIDATE`, `CANDIDATES_BLOCKED`, `EXECUTION_REJECTED`, etc.;
9. if submitted, normal durable `PROP - HyroTrader` execution notification is also emitted.

Regular AUTO cron remains unchanged in purpose and can still evaluate both MARKET_PLAN and LIMIT_PLAN.

## HYRO AUTO EXECUTION
Scheduled Worker cron remains every minute (`* * * * *`).
Each regular PROP cycle follows:
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
15. polling snapshots monitor actual closure for TP/SL/P&L notice

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

SL/TP USD on entry is estimated from `|entry-level| * qty` before fees/slippage. Close P/L uses actual account closed-net delta for the confirmed interval.

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
- Source deploys must use the same KV binding and keep vars/secrets.
- Updating code must never clear Signal LIVE ORDERS, PROP execution/idempotency/notification state, or PERSONAL state.
- Quick scan reuses the same execution idempotency/risk gates, so it must not bypass or duplicate an existing order intent.

## REPOSITORY/CLOUDFLARE CONTRACT
- Do not restore legacy `apply-v*.yml` or `scripts/apply_v*.js` chains.
- Deploy only `cloudflare-worker/index.js` as canonical entrypoint.
- Keep same `TRADING_STATE` namespace and `keep_vars`.
- Never recreate/clear state during deploy.

## IMMEDIATE NEXT STEP
Cloudflare must deploy/promote source containing commit `4fe83372` (and runtime commit `849bfc48`) to 100% traffic. After deployment:
1. Challenge remains effective DEMO.
2. Telegram PROP menu shows `🔎 QUÉT NHANH MARKET`.
3. `KẾT NỐI` shows `Auto reconnect: ON (cron + request refresh)`.
4. User can press Quick Scan for an immediate MARKET-only cycle; no need to wait for cron.
5. Regular AUTO continues every minute.
6. Existing Signal/LIVE ORDERS, PROP state/idempotency/notification state and PERSONAL state remain intact through deployment.

## FROZEN/HISTORICAL KNOWLEDGE STILL ACTIVE
- V73 statistical prior remains frozen; do not rebuild/retune from live outcomes.
- V74 market-data integrity/freshness authority remains active where applicable.
- V76 R2 rejected methods remain rejected; do not restore them.
- Existing market-specific Signal knowledge and durable LIVE ORDERS behavior remain active unless explicitly superseded.

## NEW CHAT PROMPT
`Tiếp tục toàn bộ dự án Trading từ GitHub mới nhất. BẮT BUỘC đọc docs/checkpoints/CURRENT_HANDOFF.md trước, sau đó V77180_AUTO_READY_CONSOLIDATED.md và MASTER_TRADING_STATE.md. Canonical hiện là V77.18.10. SIGNAL, PROP/Hyro và PERSONAL hoàn toàn độc lập. Hyro CHALLENGE One-Step 5K Standard/Trailing dùng Bybit Demo Trading với HYRO_BYBIT_API_KEY/SECRET; FUNDED mới dùng LIVE credentials khi phù hợp. PROP AUTO mỗi phút vẫn quét MARKET/LIMIT. Telegram có nút 🔎 QUÉT NHANH MARKET chạy ngay một full MARKET-only cycle và có thể submit nếu toàn bộ gate pass. Hyro telemetry tự refresh/reconnect sau deploy qua cron + request refresh; KẾT NỐI chỉ là status/diagnostic, không phải bước kích hoạt. PROP chỉ notify actual submit và actual close TP/SL/P&L. Bảo toàn toàn bộ KV/LIVE ORDERS/state Signal, PROP và PERSONAL qua mọi deploy; không reset namespace hay quay lại workflow/phương pháp đã loại.`