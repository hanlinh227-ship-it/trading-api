# V77.18.19 — SINGLE PROP RECOVERY

Date: 2026-08-18 UTC+7

## Objective
Remove the second Hyro PROP account entirely and restore one canonical Hyro Challenge account without losing existing state or open positions.

## Root causes fixed
1. Multi-account Account A bypassed the canonical `Challenge => DEMO` environment override. This could query the wrong Bybit mode after the dual-account rollout and therefore miss the real Challenge positions/equity.
2. Telemetry used `totalEquity ?? coin.equity`. A numeric zero in `totalEquity` prevented fallback to a positive USDT coin equity/wallet balance. V77.18.19 now chooses the strongest non-negative valid balance source.
3. Health Guardian still treated TK2 as required and generated `TK2 chưa có API key`; all TK2 health logic is removed.

## Canonical PROP architecture
- ONE Hyro account only.
- Existing legacy PROP KV keys remain canonical; no reset/migration of open order or position-manager state.
- Challenge profile always forces Bybit DEMO through `propEnv()`.
- `hyro-multi-account.js` and `hyro-multi-ui.js` are removed from the repository.
- No `HYRO_B_*` variable is read by runtime or Health Guardian.

## Position recognition
Private telemetry probes stay independent:
- `/v5/account/wallet-balance` UNIFIED USDT
- `/v5/position/list` linear USDT
- `/v5/order/realtime` linear USDT
- `/v5/position/closed-pnl`

A wallet aggregate anomaly must not hide valid open positions. Position display/review uses the positions endpoint independently.

## Telegram PROP UI
Single-account menu only:
- Tổng quan / Vị thế
- Risk / Kết nối
- Quét / Đánh giá
- Auto
- DEMO Order/Cycle when applicable
- Cấu hình / Menu

No TK1/TK2 labels and no `2 tài khoản` button.

## Position review retained
V77.18.18 HOLD/TIGHTEN/CUT review remains active every ~5 minutes and on the `Đánh giá` button. Review remains per-symbol strategy aware and auto CUT remains guarded.

## Deployment/state safety
- `TRADING_STATE` unchanged.
- Signal `v775:books` unchanged.
- PROP runtime/execution/idempotency/notification/position-manager/review state unchanged.
- No position is closed or cancelled as part of this migration.
- `keep_vars: true` remains mandatory.

## Production verification after deploy
1. Telegram release banner shows `V77.18.19 — Single PROP Recovery`.
2. PROP menu has only one account.
3. `Kết nối` reports DEMO for Challenge and all private endpoints PASS.
4. `Vị thế` must show any currently open Bybit Challenge position even if wallet aggregate fields are anomalous.
5. Health Guardian must not mention TK2/HYRO_B.
6. `Đánh giá` must evaluate the currently open position as HOLD/TIGHTEN/CUT.
