# V77.18.17 — AUTONOMOUS HEALTH GUARDIAN

Canonical extension over V77.18.16.

## Purpose
Automate runtime health verification without changing trading logic or resetting state.

## Health module
`cloudflare-worker/system-health.js`

Durable additive keys only:
- `v771817:health:last`
- `v771817:health:alert_state`
- `v771817:health:last_full`

No existing Signal/PROP/PERSONAL state is migrated or reset.

## Automatic checks
- `TRADING_STATE` presence and Signal LIVE ORDERS readability (`v775:books`).
- Latest Signal scan snapshots for crypto/forex/metal/future (`v7712:scan:*`) with market-specific stale thresholds.
- Telegram token/chat configuration and full-audit `getMe` connectivity.
- Twelve Data key presence.
- Massive Futures key presence.
- Hyro TK1/TK2 configured/connected state.
- Bybit telemetry diagnostics/endpoints reported by each Hyro account.
- Equity, positions, orders, AUTO requested/manual pause state.
- Hyro runtime freshness.
- Combined open-risk cap sanity.

## Cadence
Worker scheduled event runs the lightweight health audit every cron tick. Full audit is limited to once per 5 minutes by durable state.

## Alert policy
Telegram notification is state-transition based. Do not spam repeated identical failures.
Notify when the error/warning signature changes and notify once when the system recovers to healthy.

## Runtime endpoints
- `/health` returns last stored health snapshot.
- `/health/run` performs an on-demand full audit without sending a Telegram alert.

## State safety
Health Guardian is read-mostly. It does not place/cancel trades, alter scanner thresholds, toggle AUTO, change profiles, or rewrite LIVE ORDERS. It only writes the new `v771817:health:*` keys.

## Canonical
Production wrapper version: `V77.18.17`.
Signal remains V77.16.9 Balanced Entry. PROP dual-account architecture, anti-mirror, portfolio guard, per-symbol strategies, position management and dynamic equity sizing remain unchanged.

Do not claim production-active until Cloudflare build/deploy for V77.18.17 is green and at 100% traffic.
