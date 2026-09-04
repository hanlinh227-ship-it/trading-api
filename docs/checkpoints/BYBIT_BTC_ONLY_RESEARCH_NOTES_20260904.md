# BTC-ONLY RESEARCH NOTES — 2026-09-04

External research and Bybit V5 documentation support using live order book + public trade flow as execution/market-microstructure inputs rather than relying on indicator-only entries.

Production interpretation:
- Maintain a local BTCUSDT order book from WebSocket snapshot/delta.
- Use publicTrade.BTCUSDT for aggressor-side trade flow delta.
- Correlate order-book matching-engine timestamps/cross sequence with trade flow where possible.
- Use funding/open interest as contextual derivatives state, not direct direction signals.
- Treat strong trade imbalance/toxic-flow conditions as possible jump/shock risk and reduce/add no new risk unless the setup explicitly handles expansion.

These inputs complement market structure/liquidity/price action. None alone is sufficient entry authority.
