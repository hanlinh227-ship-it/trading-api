# CURRENT HANDOFF — TRADING PROJECT

Updated: 2026-08-18 UTC+7

## READ FIRST
1. `V77180_AUTO_READY_CONSOLIDATED.md`
2. `MASTER_TRADING_STATE.md`
3. `V771819_SINGLE_PROP_RECOVERY.md`
4. `V771818_RELEASE_POSITION_REVIEW.md`
5. `V771817_AUTONOMOUS_HEALTH_GUARDIAN.md`
6. `V771816_BALANCED_ENTRY_ALL_MARKETS.md`
7. `V771814_PROP_PORTFOLIO_GUARD.md`
8. `V771813_MICROSTRUCTURE_AUDIT.md`
9. `V771811_PROP_PER_SYMBOL_MANAGEMENT.md`
10. `ENTRY_EXECUTION_V76.md` and relevant market checkpoints.

## CURRENT CANONICAL
**Canonical source is V77.18.19 — Single PROP Recovery.** Production entrypoint is `cloudflare-worker/index.js`. Signal core remains `engine-v77168.js` / V77.16.9.

PROP is SINGLE ACCOUNT ONLY. The previous TK2/multi-account runtime and Telegram UI are removed. `hyro-multi-account.js` and `hyro-multi-ui.js` no longer exist in canonical source.

## ROOT-CAUSE FIXES V77.18.19
1. Dual-account Account A bypassed the canonical `Challenge => DEMO` override. Single PROP now always goes through `propEnv()`, so a CHALLENGE profile uses Bybit DEMO regardless of stale environment mode.
2. Bybit telemetry previously used `totalEquity ?? coin.equity`; a valid numeric zero prevented fallback. Equity/wallet/available now choose the strongest non-negative valid source, so zero aggregate fields do not mask a positive USDT balance.
3. Position probing stays independent from wallet parsing. An anomalous wallet aggregate must not make an existing `/v5/position/list` position disappear from Telegram/review.
4. Health Guardian no longer checks TK2 or `HYRO_B_*` and must never alert `TK2 chưa có API key`.

## SINGLE PROP TELEGRAM
Menu:
- Tổng quan / Vị thế
- Risk / Kết nối
- Quét / Đánh giá
- Auto
- DEMO Order/Cycle when applicable
- Cấu hình / Menu

No TK1/TK2 labels and no `2 tài khoản` button.

## RELEASE VERSION ANNOUNCEMENT
Telegram sends one compact release message after a new production runtime starts. `/release` exposes version/name/state. V77.18.19 release name: `Single PROP Recovery`.

## PROP POSITION REVIEW
`🧭 Đánh giá` and automatic review remain active roughly every 5 minutes.
- HOLD: keep.
- TIGHTEN: warn/manage more defensively; existing TP/BE/trailing manager remains stop authority.
- CUT: reduce-only market close only under strong multi-factor deterioration, minimum hold ~8m, and only when AUTO execution is allowed.
- Inputs remain per-symbol strategy family + initial-R P/L + holding time + funding + OI/long-short/orderbook/spread.
- `HYRO_POSITION_REEVAL_AUTO_CUT=false` disables automatic CUT without disabling review.

## STATE SAFETY
Never reset `TRADING_STATE`.
Signal LIVE ORDERS `v775:books` remains unchanged.
PROP legacy execution/runtime/idempotency/notification/position-manager/portfolio/review state remains canonical and unchanged.
No order/position is closed or cancelled merely because of V77.18.19 deployment.
Old TK2-prefixed KV may remain inert historical data; runtime must not read it.

## SIGNAL
Signal V77.16.9 remains unchanged: Crypto auto-scan ~5m, Forex hourly, Metals hourly, Futures ~15m. Non-crypto remains MARKET/LIMIT PLAN until a real broker execution authority exists. Hard freshness/news/structural/execution-authority gates remain active.

## PROP CORE
One Hyro account only. Each coin keeps its own stable strategy/profile. A tier quality unchanged; B tier remains reduced-risk. Funding, microstructure, dynamic equity, 3-slot diversified portfolio guard, native SL/TP and TP1/TP2/runner management remain mandatory.

## HEALTH GUARDIAN
`system-health.js` audits one PROP account only. Lightweight checks each cron tick; full probe at most once per 5 minutes. It is read-mostly and cannot place/cancel trades or change AUTO/strategy.

## CLOUDFLARE CONTRACT
- Source: GitHub.
- Worker: `trading-v77-scanner`.
- KV binding: existing `TRADING_STATE` namespace.
- `keep_vars: true`.
- Cron every minute; modules decide internal cadence.

## DEPLOYMENT GATE
Do NOT claim V77.18.19 production-active until Cloudflare build is green and newest deployment is at 100% traffic.
After deploy verify:
1. release banner reports `V77.18.19 — Single PROP Recovery`;
2. PROP has only one account/menu;
3. Challenge connection reports DEMO and wallet/positions/orders/closedPnL endpoints PASS;
4. an actually open Challenge position appears under `Vị thế`;
5. `Đánh giá` sees that same position;
6. Health Guardian never mentions TK2/HYRO_B;
7. Signal/LIVE ORDER state remains continuous.

## NEW CHAT PROMPT
`Tiếp tục Trading từ GitHub mới nhất. Đọc CURRENT_HANDOFF.md trước. Canonical V77.18.19 Single PROP Recovery. PROP chỉ còn 1 Hyro account; Challenge luôn dùng DEMO qua propEnv; telemetry equity có positive fallback và positions độc lập với wallet. Không khôi phục TK2/multi-account. Giữ release banner, Health Guardian single-account, HOLD/TIGHTEN/CUT 5m, per-symbol strategy, funding/microstructure, dynamic equity, TP1/TP2/runner, portfolio guard và toàn bộ TRADING_STATE/LIVE ORDERS.`
