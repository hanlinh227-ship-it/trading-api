# CURRENT HANDOFF — TRADING PROJECT

Updated: 2026-08-18 UTC+7

## READ FIRST
1. `V77180_AUTO_READY_CONSOLIDATED.md`
2. `MASTER_TRADING_STATE.md`
3. `V771818_RELEASE_POSITION_REVIEW.md`
4. `V771817_AUTONOMOUS_HEALTH_GUARDIAN.md`
5. `V771816_BALANCED_ENTRY_ALL_MARKETS.md`
6. `V771815_DUAL_HYRO_ACCOUNTS.md`
7. `V771814_PROP_PORTFOLIO_GUARD.md`
8. `V771813_MICROSTRUCTURE_AUDIT.md`
9. `V771811_PROP_PER_SYMBOL_MANAGEMENT.md`
10. `ENTRY_EXECUTION_V76.md` and relevant market checkpoints.

## CURRENT CANONICAL
**Canonical source is V77.18.18 — Adaptive Position Review.** Production entrypoint is `cloudflare-worker/index.js`. Signal core remains `engine-v77168.js` / V77.16.9. PROP remains dual-account modular. Health Guardian remains active.

Important V77.18.18 commits:
- `a77d790f` — periodic PROP HOLD/TIGHTEN/CUT evaluator.
- `5e113cdf` — automatic Telegram release banner.
- `f1726c98` — release/review wired into runtime and PROP UI.
- `a9dd7406` — position review uses each symbol's strategy family.
- `867cd497` — V77.18.18 checkpoint.

## RELEASE VERSION ANNOUNCEMENT
On the first scheduled tick after a new runtime version becomes production-active, Telegram sends one compact message containing:
- version number;
- release name;
- key changes.
State: `v771818:release:last_announced`. `/release` exposes version/name/announcement state. Do not persist announcement if Telegram send fails.

## PROP POSITION REVIEW
Every open PROP position is re-evaluated independently every 5 minutes per account. Manual button: `🧭 Đánh giá`.

Inputs include initial-R P/L, holding time, current funding and Bybit microstructure (OI, long/short, orderbook, spread) interpreted through that symbol's own stable `hyroStrategyProfile.family`.

Actions:
- `HOLD`: keep position; automatic cron stays silent.
- `TIGHTEN`: warning only; existing TP1/TP2/BE/trailing manager remains stop authority.
- `CUT`: reduce-only market close only under strong multi-factor deterioration and after minimum 8 minutes held.

Automatic CUT is allowed only when the account's AUTO execution is requested and not manually paused. Set `HYRO_POSITION_REEVAL_AUTO_CUT=false` to keep review active but disable automatic CUT.

State prefix: `v771818:hyro:review:`. TK2 remains isolated by the existing multi-account KV proxy.

## NON-NEGOTIABLE STATE / SEPARATION
SIGNAL, PROP and PERSONAL remain independent. Never reset `TRADING_STATE`, Signal LIVE ORDERS (`v775:books`), PROP execution/idempotency/notification/position-manager/portfolio/multi-account/review state, or PERSONAL state.

## SIGNAL BALANCED ENTRY
Signal V77.16.9 remains unchanged: Crypto every 5m, Forex hourly, Metals hourly, Futures every 15m. Non-crypto remains MARKET/LIMIT PLAN only until real broker execution authority exists. Hard freshness/news/structural/execution-authority gates remain active.

## PROP CORE
Each coin keeps its own stable strategy/profile. A tier quality unchanged; practical B tier remains lower risk. Funding, BTC filter where configured, microstructure, dynamic equity risk, 3-slot diversified portfolio guard, 6h anti-mirror across TK1/TK2, telemetry, native SL/TP and TP1/TP2/runner management remain mandatory.

## AUTONOMOUS HEALTH GUARDIAN
`system-health.js` continues lightweight audit each cron tick and full probe at most once per 5 minutes. It is read-mostly and must never place/cancel trades or change AUTO/strategy.

## CLOUDFLARE CONTRACT
- Source of truth: GitHub.
- Worker: `trading-v77-scanner`.
- KV binding: `TRADING_STATE` with existing namespace.
- `keep_vars: true`.
- Cron every minute; modules decide internal cadence.

## DEPLOYMENT GATE
Do NOT claim V77.18.18 production-active until Cloudflare build is green and newest version is at 100% traffic. After deploy verify: Telegram release banner appears once, `/release` reports V77.18.18 / Adaptive Position Review, `🧭 Đánh giá` exists for TK1/TK2, review state persists, and all prior Signal/PROP state remains continuous.

## NEW CHAT PROMPT
`Tiếp tục Trading từ GitHub mới nhất. Đọc CURRENT_HANDOFF.md trước. Canonical V77.18.18 Adaptive Position Review. SIGNAL/PROP/PERSONAL độc lập. Telegram tự báo version + release name một lần khi bản mới thực sự chạy. PROP TK1/TK2 tự đánh giá vị thế mỗi 5 phút theo từng coin riêng: HOLD/TIGHTEN/CUT; CUT chỉ reduce-only khi nhiều tín hiệu xấu xác nhận, tối thiểu giữ 8 phút và AUTO đang được phép. Giữ nguyên Health Guardian, balanced Signal autoscan, per-symbol strategy, funding, microstructure, dynamic equity, TP1/TP2/runner, portfolio guard, anti-mirror và toàn bộ TRADING_STATE/LIVE ORDERS.`
