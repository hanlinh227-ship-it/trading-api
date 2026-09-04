# Bybit Android Monitor V1

Read-only Android client for the production Bybit multi-asset bot.

## Security
- No Bybit API key/secret in the APK.
- No trading endpoints are called by the app.
- First pairing uses a one-time pairing code.
- The returned monitor token is encrypted with Android Keystore (AES-GCM).
- REST and WebSocket use `Authorization: Bearer <monitor-token>`.

## Screens
- Dashboard: Equity, Balance, Available, Unrealized/Realized PnL, Win Rate, Long/Short, WS health, latency, data age.
- Positions: all open positions with Entry, Mark, PnL, ROE, leverage, TP, SL, liquidation price.
- Scanner: Confirmed Tradeable / Watching / No Trade with search.

## Background
Optional foreground realtime monitor posts position/connection notifications. The home-screen widget is refreshed from the foreground stream and by WorkManager.

## Backend
Default endpoint: `https://trading-v77-scanner.hanlinh227.workers.dev`.
Schema: `BYBIT_ANDROID_MONITOR_V1`.
