# V77.18.18 — RELEASE BANNER + ADAPTIVE POSITION REVIEW

Canonical version: V77.18.18
Release name: Adaptive Position Review
Date: 2026-08-18 UTC+7

## Release banner
- `release-notifier.js` stores `v771818:release:last_announced`.
- On the first scheduled tick after a new production version is active, Telegram receives exactly one compact release message with version, release name and key changes.
- `/release` exposes current runtime version/name and last-announced state.
- A version is only persisted as announced after Telegram send succeeds.

## PROP position re-evaluation
- `hyro-position-review.js` evaluates every open position independently every 5 minutes per Hyro account.
- Manual `🧭 Đánh giá` forces an immediate review.
- Each coin reuses its own stable `hyroStrategyProfile` family; review does not apply one generic strategy to all symbols.
- Inputs: current P/L expressed in initial R, holding time, Bybit OI/long-short/orderbook/spread microstructure through the coin strategy family, and current funding.
- Outputs: HOLD / TIGHTEN / CUT.
- HOLD is silent in automatic cron.
- TIGHTEN is an alert only; existing TP1/TP2/BE/trailing manager remains authority for stop management.
- CUT uses reduce-only market execution only when multiple adverse conditions confirm and minimum hold time is met.
- Default automatic CUT is enabled only while that account's AUTO execution is requested and not manually paused. `HYRO_POSITION_REEVAL_AUTO_CUT=false` disables automatic CUT while preserving evaluation.
- Minimum automatic CUT holding time: 8 minutes.
- State prefix: `v771818:hyro:review:`; account B remains isolated by the existing multi-account KV proxy.

## Existing protections retained
Signal/PROP/PERSONAL isolation, `TRADING_STATE`, Signal LIVE ORDERS, Hyro per-symbol entries, funding entry gate, microstructure, dynamic equity sizing, 3-slot portfolio guard, anti-mirror, native SL/TP, TP1/TP2/runner, BE/trailing, Health Guardian and all prior durable state remain unchanged.

## Deployment gate
Do not call V77.18.18 production-active until Cloudflare build is green and newest deployment receives 100% traffic. After activation expect one Telegram release banner on the next cron tick and the new `🧭 Đánh giá` button inside each PROP account.
