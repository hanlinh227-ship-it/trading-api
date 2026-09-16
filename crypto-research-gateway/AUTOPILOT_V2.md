# Hybrid Autopilot V2 — Production Contract

Hybrid Autopilot V2 is a research-only multi-market orchestration layer for Crypto, Forex, Futures, Indices, Metals, and Commodities.

## Request flow

Natural-language requests such as `quét market`, `tìm entry`, `tìm lệnh`, `quét toàn bộ thị trường`, `find best trade`, and `scan markets` are owned by the existing canonical `multi_market_analysis` skill. The global `task_router` remains the sole routing authority; no parallel global router is introduced.

The research gateway exposes `POST /research/autoscan`. It plans the requested market scope, evaluates normalized observations, builds research candidates, applies freshness/conflict/invalidation gates, challenges the thesis, ranks passing opportunities, and returns `TOP_SETUP` or `NO_TRADE` with coverage gaps when evidence is insufficient.

## Safety and authority

- The endpoint is research-only and cannot place orders.
- Non-BTC domains do not receive production execution authority from this capability.
- BTCUSDT/Bybit production execution authority remains governed by the existing Trading project checkpoint and deployment gates.
- External plugins/connectors/providers supply evidence only; their credentials are not inherited by Railway and they never become reasoning, routing, or execution authority.
- Missing, stale, unknown, conflicting, malformed, or semantically incompatible evidence fails closed rather than being fabricated or silently averaged.

## Chart context

TradingView is used only as verified chart context/navigation. A verified external mapping may be preserved. When mapping is unverified, the response returns a symbol-search navigation hint instead of inventing an exchange-qualified TradingView symbol. This is not an official TradingView data/API integration and does not require a paid TradingView account.

## Deployment contract

Production rollout remains zero-local. Cloudflare Skill Gateway and Railway research runtime are separate deployment authorities and both must be verified against the exact canonical `main` SHA before this capability is described as LIVE. Railway verification requires deployment metadata and runtime health to match the exact main source SHA. Cloudflare verification requires the exact-revision health, route matrix, Model Mesh canaries, zero-cost guards, and final exact-SHA gate to pass without rollback.
