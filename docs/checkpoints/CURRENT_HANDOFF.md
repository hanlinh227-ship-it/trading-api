# CURRENT HANDOFF — TRADING PROJECT

Updated: 2026-08-18 UTC+7

## READ FIRST
1. `V77180_AUTO_READY_CONSOLIDATED.md`
2. `MASTER_TRADING_STATE.md`
3. `V771813_MICROSTRUCTURE_AUDIT.md`
4. `V771811_PROP_PER_SYMBOL_MANAGEMENT.md`
5. `ENTRY_EXECUTION_V76.md` and relevant market checkpoints when needed.

## CURRENT CANONICAL
**Canonical source is V77.18.13.** Production entrypoint is `cloudflare-worker/index.js`; Signal core remains `engine-v77168.js`; PROP runtime is modular (`hyro-scanner.js`, `hyro-market-context.js`, `hyro-execution.js`, `hyro-runtime.js`, `hyro-position-manager.js`). Cloudflare is deployment only.

Important V77.18.13 commits:
- `8d0e5995` — per-symbol Bybit microstructure module.
- `c2b0bee3` — microstructure integrated into regular/quick Hyro cycles.
- `f2f57917` — removed nominal account-size wizard conflict; dynamic-equity profile UI.
- `3e92e875` — compact PROP Telegram runtime UI/notifications.
- `bc5091c5` — modular canonical CI validator + Wrangler dry-run.
- `add7ed88` — V77.18.13 audit checkpoint.

## NON-NEGOTIABLE SEPARATION / STATE
SIGNAL, PROP/Hyro and PERSONAL remain completely independent.
Never route SIGNAL candidates/orders into PROP. Never route PROP into PERSONAL.
Never reset `TRADING_STATE`, Signal LIVE ORDERS, PROP execution/idempotency/notification/position-manager state, or PERSONAL state.

## HYRO ENVIRONMENT
Current phase: CHALLENGE => force Bybit Demo Trading and `HYRO_BYBIT_API_KEY/SECRET`. FUNDED may later use separate LIVE credentials. Auto telemetry refresh/reconnect remains cron + request based.

## PER-SYMBOL ENTRY — NO GENERIC RESTORE
Every coin keeps a stable method/profile. Explicit major profiles and deterministic symbol-derived profiles remain active. Families include TREND_PULLBACK, BREAKOUT_RETEST, MOMENTUM_BREAKOUT, LIQUIDITY_RECLAIM, RANGE_BREAK, VOL_BREAK, TREND_CONTINUATION.

Do not apply one identical scoring model to every family. Existing EMA/RSI/ATR/swing/funding/TP settings remain family/symbol specific.

## NEW V77.18.13 MICROSTRUCTURE
For the top deep candidates, PROP additionally reads per-symbol Bybit public data:
- 15m Open Interest history;
- 15m Long/Short holder ratio;
- orderbook depth/imbalance;
- bid/ask spread.

Weights depend on strategy family:
- momentum / vol breakout => OI + orderbook heavier;
- liquidity reclaim / range => orderbook + crowding heavier;
- trend pullback / continuation => OI + spread heavier;
- breakout retest => balanced confirmation.

Microstructure is confirmation, not a universal replacement strategy. A can downgrade to B when micro is poor; very weak B becomes C/WATCH; strongly confirmed B may run up to 0.65 A risk. Missing public micro data is neutral rather than an automatic false-negative block, while account/risk/execution telemetry remains fail-closed.

## A/B/C ENTRY POLICY
- A: full-quality MARKET, normal dynamic A risk.
- B: near-market, minimum RR/risk/funding/HTF rules still required. Quick Scan can execute B. Regular AUTO may execute B only when microstructure is strongly confirming.
- C: LIMIT/WATCH; never force MARKET.

Funding block remains authoritative.

## DYNAMIC CAPITAL / SCALE-UP
Current Bybit equity is the live capital authority. Bot automatically scales entry risk, single/combined caps, daily hard stop and applicable exposure caps with equity.
`profile.accountSize` remains only as a legacy reference denominator so old risk ratios survive migration; it is not live capital authority.
The Hyro configuration wizard no longer asks 5K/10K/25K/etc. New configuration is phase -> drawdown -> program. Scale-up is detected automatically from telemetry.

## POSITION MANAGEMENT
Still active:
- TP1 about 40%; TP2 about 35%; runner about 25%;
- SL -> BE after TP1;
- SL -> TP1 + trailing after TP2;
- structural initial SL/native protection;
- state `v771811:hyro:manage:*` survives deploy.

## TELEGRAM
PROP is compact. Actual entry format is provider + symbol/side/tier/micro + SL/TP USD; actual close is concise profit/loss + real P/L. Dashboard, Risk, Connection and Quick Scan are compact.

Signal base/hub UI is compact. Legacy Signal engine notification text is being migrated presentation-only through a one-shot syntax-gated migration; do not change Signal analysis, Books or LIVE ORDER lifecycle logic for UI cleanup.

## REPOSITORY CLEANUP
Removed proven obsolete debug/live-check/verification artifacts from V77.9–V77.10.2. Do not mass-delete old research/checkpoints merely due age; frozen knowledge and durable-order verification files may remain required.

Canonical validator has been corrected for the modular architecture. It validates all Worker JS/MJS syntax, Signal locks in the Signal engine, PROP locks in their modules, frozen V73, `TRADING_STATE`, `keep_vars`, then Wrangler bundle dry-run.

## CLOUDFLARE CONTRACT
- Source of truth: GitHub.
- Same Worker: `trading-v77-scanner`.
- Same KV binding/namespace: `TRADING_STATE`.
- `keep_vars: true`; secrets/vars retained.
- Cron every minute.
- Cloudflare version history is deployment history, not a second source tree; do not delete KV to clean deployment history.

## DEPLOYMENT GATE
Do NOT claim V77.18.13 production-active until validator/Cloudflare build is green and the newest version is at 100% traffic. Then verify Hyro telemetry/equity, Quick Scan, state continuity and no duplicate position-management orders.

## FROZEN RULES
V73 prior, V74 data freshness/authority, V76 rejected-method exclusions and all durable LIVE ORDERS/state rules remain active. Do not restore workflows/methods explicitly removed by canonical checkpoints.

## NEW CHAT PROMPT
`Tiếp tục Trading từ GitHub mới nhất. BẮT BUỘC đọc CURRENT_HANDOFF.md trước, rồi V77180_AUTO_READY_CONSOLIDATED.md, MASTER_TRADING_STATE.md, V771813_MICROSTRUCTURE_AUDIT.md và V771811_PROP_PER_SYMBOL_MANAGEMENT.md. Canonical source V77.18.13. SIGNAL/PROP/PERSONAL độc lập. PROP mỗi symbol có strategy riêng + funding + family-weighted OI/long-short/orderbook/spread microstructure; A/B/C, dynamic equity sizing, partial TP/BE/trailing. Hyro Challenge dùng Bybit Demo; Funded dùng credentials riêng sau này. Bảo toàn toàn bộ TRADING_STATE/LIVE ORDERS/state qua deploy. Không quay lại generic scanner/workflow đã loại.`
