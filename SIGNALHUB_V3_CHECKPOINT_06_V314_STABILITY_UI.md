# SIGNALHUB V3 CHECKPOINT 06 — V3.14 STABILITY/UI

Date: 2026-09-09
Branch: `signalhub-v314-crypto-stability-ui`
Base: `signalhub-v313-crypto-only-quality` (`d9af4382b7fe898bc055090e6fb9bd4e17c08407`)

## Goal
Continue the crypto-only SignalHub Android app without reintroducing Forex signal generation. Preserve hard separation between SCALP and SWING and make Entry/SL/TP/lifecycle easier to read while improving live-connection stability.

## Changes
- Android version 3.14.0 / versionCode 20.
- API requests moved to shared OkHttp connection pooling with bounded retry and explicit call timeouts.
- Foreground monitor cadence reduced from 1s to 3s; expensive scan calls throttled to 30s per style.
- Background monitor no longer performs redundant full crypto ticker polling; the foreground Activity owns live ticker refresh while open.
- Foreground crypto refresh relaxed from 500ms to 1000ms to reduce socket/server pressure without making the UI feel stale.
- Signal UI explicitly labels the selected style as a hard partition and labels the large current-price number as LIVE price.
- Entry, SL, TP1, TP2, TP3 and RR remain visible on signal cards and detail pages.
- No one-time pairing/login gate is added.

## Invariants
- CRYPTO only.
- SCALP and SWING are independent signal books.
- Win rate remains historical only and is calculated from resolved TP/SL trades.
- Do not label setup score as win probability.
- Bybit remains preferred execution-price authority with OKX/Binance fallback as provided by backend signal metadata.

Build verification and APK checksum must come from CI output/release artifact, not be invented here.
