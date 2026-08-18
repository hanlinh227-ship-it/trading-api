# V77.16.7 LIVE ORDER RECONCILIATION CHECKPOINT

Verified production: V77.16.7 — Durable Order Archive Hub.

## Root causes fixed
1. `limitActive` (filled LIMIT positions) existed in KV but group summaries displayed only `marketActive` and `limitPending`, so a filled LIMIT looked like it disappeared after the next scan.
2. Live symbols are intentionally excluded from new-entry deep scans to prevent duplicate entries. With `limitActive` hidden, this protection looked like state loss.
3. Legacy `toPos()` selected TP2 only when `targetRR === 2`; other RR values could make lifecycle monitor TP1 instead. New positions now use TP2 whenever a valid TP2 exists.
4. Older orders had no `discoveredBy` metadata. They are now backfilled as `LEGACY_PRESERVED` without changing ID/entry/SL/TP.
5. Legacy Books normalization previously sliced active/pending arrays to top-3 while reading. V77.16.7 preserves all valid existing orders; max limits apply only to opening new orders.
6. Current live orders are archived into durable order history as `LIVE_STATE_PRESERVED`, and `/order-history` exposes that archive.
7. Crypto lifecycle still checks pending LIMIT fills and TP/SL. Filled LIMIT moves `limitPending -> limitActive`, sends Telegram notification, and remains visible in Crypto/Hub until a legitimate TP/SL lifecycle event removes it.
8. Crypto auto-scan runs from cron every 5 minutes and notifies newly created executable MARKET/LIMIT orders. Manual Hub, market button, symbol button, chat command and auto scan all tag the order source.

## Required UI behavior
- Crypto group summary MUST show: MARKET running, LIMIT filled/running (`limitActive`), MARKET PLAN, LIMIT PLAN, LIMIT pending, pure WATCH.
- Hub MUST show `LIVE POSITIONS` separately from `TOP SETUPS NEW`.
- A live symbol excluded from fresh candidate scanning MUST still appear in LIVE POSITIONS.
- Books/Orders remain durable through Worker deployments and fresh scans.

## Production verification
See `V77167_LIVE_ORDER_CHECK.txt`.
Verified before scan:
- DOTUSDT MARKET, source GROUP_MANUAL.
- POLUSDT LIMIT_ACTIVE, source LEGACY_PRESERVED.

After a fresh Crypto scan: both IDs remained unchanged.
After a full Hub scan: both IDs remained unchanged; Hub added a new VIRTUALUSDT MARKET sourced from API_HUB.
No prior IDs disappeared. Hub returned Books and showed 3 live positions. Every order had a source label. Order-history count increased and contained LIVE_STATE_PRESERVED events. VERDICT=PASS.

## Invariant
Never interpret a symbol missing from fresh scan candidates as a closed/lost order. Fresh scans and durable live-order state are separate layers. An order may leave live state only through a legitimate lifecycle/broker reconciliation event (TP, SL, explicit close/cancel, expiry for pending orders, or future MT5 broker truth).
