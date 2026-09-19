# BYBIT TOP100 STATEFLOW 3.0 — CANONICAL CHECKPOINT

Updated: 2026-09-19 UTC+7

Authority token: `BYBIT-TOP100-STATEFLOW-3.0`

## Scope
Production execution family: up to 100 high-market-cap crypto assets on Bybit USDT Linear Perpetual, dynamically selected and fail-closed.

## Universe admission
A symbol may receive new risk only when:
- CoinGecko market-cap rank <= 100.
- Market cap >= USD 250M.
- Active Bybit USDT linear perpetual.
- Listing age >= 30 days when launch metadata exists.
- Bybit 24h turnover >= USD 10M.
- Open-interest value >= USD 3M.
- Spread <= 10 bps.
- Anti-sweep liquidity score >= 0.62.
- Fresh microstructure is available.
- Strategy, derivatives, volatility, portfolio-risk, execution-quality and native-protection gates all pass.

The universe may contain fewer than 100 symbols at any moment. Breadth is an opportunity ceiling, not a requirement to force 100 simultaneous markets.

## Anti-sweep policy
No trading system can guarantee a stop will never be swept. The runtime reduces sweep exposure using:
- state-first sweep/reclaim or break/retest confirmation;
- near-touch order-book and microprice evidence;
- structure-based invalidation;
- volatility/liquidity noise buffers;
- wider dynamic-symbol anti-sweep buffer;
- lower default risk and leverage on non-core assets;
- fresh order-book/trade requirements;
- no martingale and no adding to losers.

## Portfolio
Breadth does not expand the global risk budget. Per-position risk, active-risk caps, correlation groups, margin caps, drawdown contraction, and native TP/SL remain authoritative.

## Data and transport
- Market-cap source: CoinGecko public market data, cached 30 minutes.
- Stale market-cap cache: fail closed after 24 hours.
- Bybit market/execution metadata remains exchange authoritative.
- BTC cloud-native WebSocket remains available.
- Non-BTC fresh microstructure may use the private VPC public-WS mirror.
- Private Bybit V5 signing remains in Cloudflare; Demo/LIVE mode separation remains mandatory.

## Activation
1. CI green.
2. Deploy exact main revision.
3. Bybit Demo authenticated and execution.ready.
4. Dynamic top-100 universe non-empty and market-cap evidence fresh or within allowed stale window.
5. Representative non-BTC symbols pass fresh microstructure and strategy checks.
6. Demo canary only.
7. LIVE remains separately gated by existing live acknowledgements.

Forex, meme-specific execution, Signal V10/V11 and AI-council order authority remain retired.
