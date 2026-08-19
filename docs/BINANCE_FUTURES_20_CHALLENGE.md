# Binance USDⓈ-M Futures — $20 Challenge

Isolated personal-account engine. No Telegram integration. Replaces the abandoned Personal Gold module.

## Defaults
- Starting capital model: 20 USDT
- Universe: BTCUSDT, ETHUSDT, SOLUSDT, XRPUSDT perpetuals
- Scan cadence: 60 seconds using native Binance USDⓈ-M 1m/5m klines and book ticker
- Leverage: 3x isolated, hard config cap 5x
- Risk target: 0.20 USDT/trade, reduced sizing can be configured
- Daily loss stop: 1.00 USDT
- Max one open position, max 24 entries/day, 3-loss pause 30 minutes
- LIVE execution is OFF unless BINANCE20_AUTO_EXECUTE=true

## Required secrets for LIVE
BINANCE_FUTURES_API_KEY
BINANCE_FUTURES_API_SECRET

Optional:
BINANCE_FUTURES_BASE_URL
BINANCE20_LEVERAGE
BINANCE20_RISK_USD
BINANCE20_SYMBOLS

The client reads Binance exchangeInfo filters before sizing and rejects orders below the symbol's quantity/notional constraints. Entry is MARKET with reduce/close protection through STOP_MARKET and TAKE_PROFIT_MARKET using MARK_PRICE triggers.

This is an experimental challenge engine. A 20 USDT futures account can be lost quickly; keep LIVE disabled until paper/test execution and fee/slippage behavior are verified.
