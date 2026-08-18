# CURRENT HANDOFF — TRADING PROJECT

Updated: 2026-08-18 UTC+7

## READ FIRST
1. `V77180_AUTO_READY_CONSOLIDATED.md`
2. `MASTER_TRADING_STATE.md`
3. `V771814_PROP_PORTFOLIO_GUARD.md`
4. `V771813_MICROSTRUCTURE_AUDIT.md`
5. `V771811_PROP_PER_SYMBOL_MANAGEMENT.md`
6. `ENTRY_EXECUTION_V76.md` and relevant market checkpoints when needed.

## CURRENT CANONICAL
**Canonical source is V77.18.14.** Production entrypoint is `cloudflare-worker/index.js`; Signal core remains `engine-v77168.js`; PROP runtime is modular (`hyro-scanner.js`, `hyro-market-context.js`, `hyro-portfolio-guard.js`, `hyro-execution.js`, `hyro-runtime.js`, `hyro-position-manager.js`). Cloudflare is deployment only.

Important V77.18.14 commits:
- `b6023570` — Hyro portfolio diversification guard.
- `3abfc4d8` — portfolio-aware candidate selection wired into AUTO/Quick Scan.
- `7484040d` — execution hard cap aligned to guarded 3-slot policy.
- `ed5572bb` — V77.18.14 Telegram/status markers.
- `0c8101ab` — validator locks for V77.18.14.
- `09dbf314` — V77.18.14 portfolio checkpoint.

## NON-NEGOTIABLE SEPARATION / STATE
SIGNAL, PROP/Hyro and PERSONAL remain completely independent.
Never route SIGNAL candidates/orders into PROP. Never route PROP into PERSONAL.
Never reset `TRADING_STATE`, Signal LIVE ORDERS, PROP execution/idempotency/notification/position-manager/portfolio state, or PERSONAL state.

## HYRO ENVIRONMENT
Current phase: CHALLENGE => force Bybit Demo Trading and `HYRO_BYBIT_API_KEY/SECRET`. FUNDED may later use separate LIVE credentials. Auto telemetry refresh/reconnect remains cron + request based.

## PER-SYMBOL ENTRY — NO GENERIC RESTORE
Every coin keeps a stable method/profile. Explicit major profiles and deterministic symbol-derived profiles remain active. Families include TREND_PULLBACK, BREAKOUT_RETEST, MOMENTUM_BREAKOUT, LIQUIDITY_RECLAIM, RANGE_BREAK, VOL_BREAK, TREND_CONTINUATION.
Do not apply one identical scoring model to every family.

## MICROSTRUCTURE
PROP additionally uses per-symbol Bybit Open Interest, Long/Short holder ratio, orderbook imbalance/depth and spread. Weights remain family-specific. Missing public micro data is neutral, while account/risk/execution telemetry remains fail-closed.

## A/B/C ENTRY POLICY
- A: full-quality MARKET, normal dynamic A risk.
- B: near-market; minimum RR/risk/funding/HTF rules remain required. Quick Scan may execute B; regular AUTO may use B only with strong microstructure confirmation.
- C: LIMIT/WATCH; never force MARKET.
Funding block remains authoritative.

## V77.18.14 PORTFOLIO GUARD
- Maximum 3 active symbols total (positions + pending orders).
- Maximum 2 positions/orders in the same direction.
- Maximum 1 same-direction position/order from the same crypto cluster.
- Minimum 3 minutes between new PROP entries.
- Candidate ranking prefers quality first: tier A/B, microstructure, RR, liquidity, then portfolio diversity.
- The third slot is optional and is allowed only when it improves diversification. Never fill slots merely because capacity exists.
- Account scale-up changes risk sizing through live equity; it does NOT increase slot count.

Stable clusters include BTC, ETH beta, L1, DeFi, Meme, Payments, Exchange, AI and RWA. Unknown symbols receive deterministic symbol-specific OTHER clusters.

New durable additive state: `v771814:hyro:portfolio`. Never reset it during deploy.

## DYNAMIC CAPITAL / SCALE-UP
Current Bybit equity is the live capital authority. Bot automatically scales entry risk, single/combined caps, daily hard stop and applicable exposure caps with equity. `profile.accountSize` is legacy reference only.

## POSITION MANAGEMENT
- TP1 about 40%; TP2 about 35%; runner about 25%.
- SL -> BE after TP1.
- SL -> TP1 + trailing after TP2.
- Structural initial SL/native protection remains mandatory.
- state `v771811:hyro:manage:*` survives deploy.

## TELEGRAM
PROP remains compact. Entry notification: provider + symbol/side/tier/micro + SL/TP USD. Close notification: concise profit/loss + real P/L. Portfolio guard may report `PORTFOLIO_GUARD_BLOCKED` / “Chờ phân tán danh mục” when a technically valid setup would over-concentrate exposure.

## CLOUDFLARE CONTRACT
- Source of truth: GitHub.
- Same Worker: `trading-v77-scanner`.
- Same KV binding/namespace: `TRADING_STATE`.
- `keep_vars: true`; secrets/vars retained.
- Cron every minute.
- Cloudflare version history is deployment history, not a second source tree.

## DEPLOYMENT GATE
Do NOT claim V77.18.14 production-active until validator/Cloudflare build is green and newest version is at 100% traffic. Then verify telemetry/equity, Quick Scan, portfolio guard behavior, state continuity and no duplicate position-management orders.

## FROZEN RULES
V73 prior, V74 freshness/data authority, V76 rejected-method exclusions, V77.18.11 per-symbol management, V77.18.13 microstructure and all durable state rules remain active unless explicitly superseded.

## NEW CHAT PROMPT
`Tiếp tục Trading từ GitHub mới nhất. BẮT BUỘC đọc CURRENT_HANDOFF.md trước. Canonical V77.18.14. SIGNAL/PROP/PERSONAL độc lập. PROP mỗi coin có strategy riêng + funding + family-weighted OI/long-short/orderbook/spread; A/B/C; live-equity sizing; TP1/TP2/runner + BE/trailing; portfolio guard tối đa 3 slot, tối đa 2 cùng hướng, không trùng cluster cùng hướng, entry spacing 3 phút. Hyro Challenge dùng Bybit Demo. Bảo toàn toàn bộ TRADING_STATE/LIVE ORDERS/state qua deploy.`
