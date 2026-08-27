# BYBIT AUTO 1.8.5 — ANTI-SWEEP + TELEGRAM RETRY LOCK

Date: 2026-08-27 (Asia/Bangkok)

## Authority
GitHub `main` source remains authoritative. This checkpoint documents the 1.8.5 reliability change after the 1.8.4 scale-risk baseline.

## Problems addressed
1. A Bybit LIVE market order could fill and the app could notify, while Telegram remained silent when the one-shot Telegram send failed. The previous controller only attempted entry notification on the exact `executed:true` cycle.
2. Initial scalp protection and subsequent BE/lock/trailing could become operationally too sensitive to 1m noise. Native trailing was armed from the initial protection request, so its activation threshold had to be moved much farther away from ordinary noise.

## 1.8.5 protection policy
- Structure-first anti-sweep stop remains authoritative.
- Price-distance risk is widened through ATR/structure/wick geometry; USD risk is NOT increased. Position sizing must reduce quantity when stop distance is wider.
- Minimum initial stop distance by volatility class: LOW 1.70 ATR, MEDIUM 1.85 ATR, HIGH 2.05 ATR.
- Structure buffer: LOW 0.55 ATR, MEDIUM 0.68 ATR, HIGH 0.82 ATR, also bounded by recent wick noise.
- Pathological stop geometry is rejected above 4.0/4.4/4.8 ATR rather than accepted blindly.
- Protection management warm-up: minimum 120 seconds after entry.
- Break-even trigger: approximately 1.30R / 1.35R / 1.45R (LOW/MEDIUM/HIGH).
- Native trailing activation: approximately 1.85R / 1.95R / 2.10R.
- BE / profit lock / trailing require momentum confirmation to remain aligned; no tightening simply because raw R briefly touches the trigger.
- Trailing distance is wider and cannot collapse below 0.45R under normal management.
- Smart CUT remains exceptional and keeps its minimum-age + multi-signal + confirmation logic; reduce-only execution remains mandatory.

## Telegram reliability
- Entry notification dedupe is now an order-id history rather than a single one-shot last-order check.
- If the first Telegram send fails, `lastTelegramNotifyError.willRetry=true` is persisted.
- Future scheduler cycles recover unnotified LIVE `openPlans` and retry the alert until the order id is successfully recorded.
- Successful recovery is marked `Telegram recovered/retried`.

## Version
`BYBIT-AUTO-1.8.5`

## Non-regression
- Do not increase USD loss budget merely to widen a stop.
- Do not remove structural SL/TP, risk preflight, live protection verification, strict AI gate, loss-streak pause, correlation gates, or Smart CUT safeguards.
- Do not revert Telegram entry notifications to one-shot-only behavior.
