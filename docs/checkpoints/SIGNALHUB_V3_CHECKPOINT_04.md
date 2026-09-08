# SIGNALHUB V3 CHECKPOINT 04

Updated: 2026-09-09 UTC+7
Status: V3 DATA/UX INTEGRATION BUILT — STRATEGY ENGINES STILL REQUIRE VALIDATION

## User contract locked
- One active exposure per symbol at a time.
- Multiple different symbols may be followed/traded concurrently; no fixed per-symbol cooldown.
- Re-entry is allowed as soon as a genuinely new setup is validated; no same-idea/FOMO recycling.
- Scalp and Swing are separate engines, not timeframe-reskinned copies.
- Self-learning must improve selection/entry quality, not manufacture a better win rate by simply suppressing frequency.
- Forex execution truth = Exness MT5.
- Crypto market truth = Bybit official V5 + existing VPS public WebSocket bridge.
- App language is Vietnamese with simple trading terms.
- Bottom navigation = SIGNALS / WATCHLIST / HISTORY / NEWS.

## Implemented in this checkpoint

### SignalHub V3 gateway wrapper
- New `signalhub-worker/gateway-v3.js` wraps the existing SignalHub 2.1 gateway so old routes/history remain available.
- `wrangler.jsonc` now points to `gateway-v3.js`.
- New routes:
  - `GET /v3/status`
  - `POST /v3/mt5/prices`
  - `POST /v3/mt5/heartbeat`
  - `POST /v3/mt5/events`
  - `GET /v3/forex/live`
  - `GET /v3/crypto/tickers`
  - `GET /v3/crypto/universe`
  - `GET /v3/crypto/discovery?style=scalp|swing`
- Real Exness `BROKER_FILL_CONFIRMED` events may patch a matching server signal to OPEN and store broker-confirmed entry/deal metadata.
- No server component is allowed to guess a broker fill merely because a scanner candle touched Entry.

### Forex live bridge integration
- Existing EA v2.01 is compatible with the V3 telemetry routes.
- Exness tick packet supplies Bid/Ask/tick timestamp for resolved symbols.
- V3 live status is explicit: LIVE / DELAYED / STALE / OFFLINE.
- Existing legacy signal engine is preserved for compatibility while new Scalp/Swing research is developed.

### Bybit / Crypto audit and V3 data layer
- Existing repo already has `bybit-live-bridge` with public linear WebSocket order book/trade/liquidation feeds and reconnect handling.
- Existing deep WS bridge intentionally limits simultaneously deep-tracked symbols; V3 broad discovery therefore uses official Bybit REST over the full USDT Linear Perpetual universe and promotes only candidates to deep analysis.
- `/v3/crypto/universe` uses Bybit V5 instruments-info pagination.
- `/v3/crypto/tickers` returns broad Bybit-native price, bid/ask, spread, turnover, OI, funding and 24h change.
- `/v3/crypto/discovery` ranks candidates for deeper Scalp/Swing analysis but is explicitly `DISCOVERY_ONLY_NOT_TRADE_SIGNAL`.
- No unvalidated crypto candidate is presented as BUY/SELL.

### Android V3 UX/UI
- App version bumped to 3.0.0.
- Dark monospace cyber-finance layout.
- Header has EXNESS and BYBIT live-state chips.
- Market selectors: FOREX / CRYPTO.
- Style selectors: SCALP / SWING.
- Bottom tabs: TÍN HIỆU / THEO DÕI / LỊCH SỬ / TIN TỨC.
- Forex Scalp cards: symbol, side/order type, Exness live price, Entry/TP/SL, waiting/fill/open state, R progress rail.
- Tapping Forex card opens detailed view with broker-confirmation state.
- Forex Swing intentionally does not reuse old intraday signals as fake swing signals.
- Crypto screen shows scanned/eligible/deep-analysis counts and Bybit candidate telemetry; candidates are shown as watch/analyse, not fake trade signals.
- Watchlist includes core Forex/metals/oil and major crypto live rows.
- History keeps existing resolved Forex history and does not fabricate Crypto/Swing history.
- News screen is present as context UX and does not invent headlines while no canonical news feed is connected.

### Android notification monitor
- Foreground service now checks signal state + latest Exness broker event about every 5 seconds.
- `BROKER_FILL_CONFIRMED` produces a Vietnamese `ĐÃ KHỚP` notification using the Exness-confirmed price.
- Last broker event fingerprint is stored locally to prevent duplicate alert after service restart.

## Validation completed
- GitHub Actions Android build compiled the V3 Java code successfully before final artifact renaming.
- Isolated SignalHub deployment workflow completed successfully after V3 wrapper activation.
- Legacy SignalHub 2.1 routes remain intentionally compatible so existing EA/history are not destroyed.

## Important unfinished work — do not mislabel as complete
1. Forex Scalp V3 strategy engine: regime-first, anti-FOMO, per-symbol calibration and OOS validation still required before replacing legacy signal generation.
2. Forex Swing V3 strategy engine: separate HTF engine still required.
3. Crypto Scalp actual signal engine: deep candidate analysis + validation still required before BUY/SELL.
4. Crypto Swing/Hold actual signal engine: separate regime/HTF model still required.
5. Canonical macro/news feed is not yet wired into V3 app/decision layer.
6. MT5 bridge auth should be hardened with a Cloudflare secret rather than compatibility header-only mode.
7. EA v2.02 should persist signal/order mappings across MT5 restart and include `DEAL_REASON` for exact TP/SL/manual-close classification.
8. Existing Bybit deep WS bridge is not intended to subscribe orderbook depth for 500+ symbols simultaneously; broad scan + dynamic deep promotion is the canonical architecture.

## Anti-overclaim rule
- Setup score is not win probability.
- No stable win rate is claimed without adequate forward/walk-forward/OOS evidence including cost/slippage.
- Previous V76 Forex research promoted 0/28 symbols; it remains research evidence, not an edge guarantee.

## Next checkpoint target
`SIGNALHUB_V3_CHECKPOINT_05` = final installable Android V3 artifact + verified V3 route smoke test + EA v2.02 state persistence/fill reason, followed by separately versioned Scalp/Swing strategy research.
