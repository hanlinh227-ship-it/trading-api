# CURRENT HANDOFF — TRADING PROJECT

Updated: 2026-08-18 UTC+7

## READ FIRST
1. `V77180_AUTO_READY_CONSOLIDATED.md`
2. `MASTER_TRADING_STATE.md`
3. `V771811_PROP_PER_SYMBOL_MANAGEMENT.md`
4. `ENTRY_EXECUTION_V76.md` and relevant market checkpoints when needed.

## CURRENT CANONICAL
**Hyro strategy/position-management layer is V77.18.11.** Production entrypoint remains `cloudflare-worker/index.js` and Cloudflare remains deployment only. Do not maintain a second hand-edited Worker copy.

Current important commits:
- `7e6c264e` — CHALLENGE profile forced to Bybit DEMO execution environment.
- `87f7e589` — durable actual-entry / actual-close PROP Telegram notifications.
- `849bfc48` + `4fe83372` — Quick MARKET scan and auto telemetry refresh/reconnect.
- `81273246` — per-symbol Hyro strategy registry + funding-aware TP ladder.
- `03d10901` — partial TP / breakeven / trailing position manager.
- `4fe4085b` — position manager wired into regular/quick Hyro cycles.
- `49b8d0a9` — trailing activates from current mark after TP2.
- `e86b0b9a` — V77.18.11 checkpoint.

## NON-NEGOTIABLE RUNTIME SEPARATION
### SIGNAL
- Telegram signal/scanner system only.
- Existing Signal LIVE ORDERS/state remain authoritative.
- SIGNAL never feeds PROP or PERSONAL execution.

### PROP / HYROTRADER
- Independent auto-trading runtime: `hyro-scanner.js` + `hyro-execution.js` + `hyro-runtime.js` + `hyro-position-manager.js`.
- Does not consume SIGNAL candidates/orders.
- Regular AUTO may use MARKET_PLAN or LIMIT_PLAN.
- `🔎 QUÉT NHANH MARKET` runs an immediate MARKET-only full cycle and may submit only if all telemetry/risk/RR/execution gates pass.
- PROP Telegram does not publish scanner candidates during normal AUTO.
- PROP Telegram may notify actual submitted orders and confirmed closures only.

### PERSONAL
- Independent reserved runtime. Never route SIGNAL/PROP state or orders into PERSONAL.

## HYRO ACCOUNT / ENVIRONMENT
Current account:
- CHALLENGE
- One-Step
- 5K USDT
- Futures / Bybit
- Standard / Trailing

Current environment rule:
- CHALLENGE => Bybit Demo Trading (`api-demo.bybit.com`)
- Challenge credentials: `HYRO_BYBIT_API_KEY` + `HYRO_BYBIT_API_SECRET`
- FUNDED/LIVE credentials remain separate: `HYRO_BYBIT_LIVE_API_KEY` + `HYRO_BYBIT_LIVE_API_SECRET`
- Profile routing overrides raw `HYRO_BYBIT_MODE` while phase=CHALLENGE.

## AUTO / CONNECTION
- Worker cron remains every minute.
- Hyro telemetry refreshes automatically on scheduled cycles and requests.
- `KẾT NỐI` is status/diagnostic, not a required activation step.
- `HYRO_AUTO_EXECUTION=true|false` remains the execution selector.
- AUTO remains fail-closed on bad telemetry/equity/risk/account state.

## V77.18.11 — PER-SYMBOL PROP STRATEGIES
Do not restore `GENERIC_DYNAMIC` as the single strategy for all coins.

Each symbol now receives a stable deterministic profile with its own:
- strategy family
- EMA lengths
- RSI thresholds
- allowed EMA/ATR distance
- swing lookback
- SL ATR buffer
- target lookback
- minimum RR
- TP1/TP2/TP3 R multiples
- BTC-context rule
- funding filter

Explicit major profiles exist for BTCUSDT, ETHUSDT, SOLUSDT, XRPUSDT, BNBUSDT, DOGEUSDT, ADAUSDT, AVAXUSDT, LINKUSDT, SUIUSDT, AAVEUSDT and ALGOUSDT.

Other eligible USDT perpetual symbols receive a stable symbol-derived profile and parameters. Mapping must not change randomly between scans/deploys.

Strategy families include:
- TREND_PULLBACK
- BREAKOUT_RETEST
- MOMENTUM_BREAKOUT
- LIQUIDITY_RECLAIM
- RANGE_BREAK
- VOL_BREAK
- TREND_CONTINUATION

## FUNDING-AWARE FILTER
Scanner reads Bybit `fundingRate` and `nextFundingTime`.
Current conservative rule:
- adverse funding within 30 minutes and |rate| >= 0.05% => block entry;
- adverse funding within 60 minutes may reduce effective RR;
- funding never bypasses telemetry/risk firewall.

## TP / SL / POSITION MANAGEMENT
New durable manager: `hyro-position-manager.js`.

For a filled PROP position:
1. initial structural SL is preserved as the risk baseline;
2. TP1 reduce-only Limit targets about 40% of original size;
3. TP2 reduce-only Limit targets about 35%;
4. remaining ~25% is runner toward TP3/final target;
5. when mark reaches TP1, full native SL moves to actual average-entry breakeven;
6. when mark reaches TP2, SL moves to TP1 and trailing stop is armed for runner;
7. trailing activates from current mark, not stale TP2 price;
8. prices/quantities are normalized to Bybit tickSize/qtyStep;
9. native final TP/SL protection from entry remains as fallback protection.

Exact TP R multiples are profile-specific, not one fixed TP for every coin.

## RISK / EXECUTION GATES STILL AUTHORITATIVE
- Fresh telemetry required.
- Equity must be valid and >0.
- Manual pause blocks new entries.
- Daily target / daily hard stop apply.
- Max active symbols, duplicate symbol and combined open-risk gates apply.
- Structural SL required; never widen stop to force a trade.
- Planned RR must pass execution minimum.
- Native Bybit order protections and idempotency remain mandatory.

## TELEGRAM PROP NOTIFICATIONS
Actual entry only, compact format:
`PROP - HyroTrader`
`🟢/🔴 SYMBOL BUY/SELL`
`SL: price (~USD risk)`
`TP: final price (~USD reward)`

Confirmed close:
`TP DONE` or `SL HIT` + actual closed P/L delta.

Scanner candidates remain silent during normal AUTO.

## STATE CONTINUITY — NEVER DELETE / RESET
KV binding remains `TRADING_STATE` with the same namespace ID.

Never clear/recreate on deployment:
- Signal LIVE ORDERS/state
- PERSONAL state
- `v7717:hyro:profile`
- `v77171:hyro:draft`
- `v77173:hyro:control`
- `v7718:hyro:*` runtime/execution/day/idempotency
- `v7718:hyro:notify:*`
- `v7718:hyro:notify:snapshot`
- `v771811:hyro:manage:*` position-management state

All migrations/updates must be additive/non-destructive. Quick scan and regular AUTO reuse the same execution/risk/idempotency state.

## REPOSITORY / CLOUDFLARE CONTRACT
- Do not restore legacy `apply-v*.yml` or `scripts/apply_v*.js` chains.
- Deploy canonical source from repository only.
- Preserve `TRADING_STATE` binding and keep vars/secrets.
- Never reset KV to fix a display/runtime problem.

## DEPLOYMENT / VERIFICATION GATE
Do not claim V77.18.11 active until Cloudflare build containing commit `49b8d0a9` or newer is green and promoted to 100% traffic.

After deployment verify on Challenge DEMO:
1. telemetry CONNECTED and expected Challenge equity;
2. AUTO ON / manual pause OFF as intended;
3. Quick Scan still works;
4. runtime preview contains per-symbol `strategy`, `profile`, TP1/TP2/TP3 and funding context;
5. a controlled filled position receives only one TP1 and one TP2 reduce-only order;
6. no duplicate partial TP orders across cron cycles/deploys;
7. SL can move to breakeven after TP1;
8. SL can move to TP1 + trailing after TP2;
9. existing Signal/PROP/PERSONAL state remains intact.

## FROZEN / HISTORICAL RULES STILL ACTIVE
- V73 statistical prior remains frozen; do not rebuild/retune from live outcomes.
- V74 market-data integrity/freshness authority remains active where applicable.
- V76 R2 rejected methods remain rejected; do not restore them.

## NEW CHAT PROMPT
`Tiếp tục toàn bộ dự án Trading từ GitHub mới nhất. BẮT BUỘC đọc docs/checkpoints/CURRENT_HANDOFF.md trước, sau đó V77180_AUTO_READY_CONSOLIDATED.md, MASTER_TRADING_STATE.md và V771811_PROP_PER_SYMBOL_MANAGEMENT.md. Hyro strategy/position-management layer hiện là V77.18.11. SIGNAL, PROP/Hyro và PERSONAL hoàn toàn độc lập. Hyro CHALLENGE One-Step 5K Standard/Trailing dùng Bybit Demo credentials; FUNDED mới dùng LIVE credentials. PROP mỗi symbol có strategy profile riêng, funding-aware, TP1 40% + TP2 35% + runner 25%, dời SL về BE sau TP1 và lên TP1 + trailing sau TP2. Quét nhanh MARKET và auto reconnect vẫn giữ. Bảo toàn toàn bộ TRADING_STATE/LIVE ORDERS/PROP management/PERSONAL state qua mọi deploy; không quay lại generic scanner hay workflow đã loại.`
