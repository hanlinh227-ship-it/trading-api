# MULTI-COIN USDT PERPETUAL A+ SCANNER 1.0

Date: 2026-09-14 UTC+7
Authority token: `MULTI-COIN-USDT-PERP-A-PLUS-SCANNER-1.0`
Scope: scan/research only

## Authority
This checkpoint is the canonical Trading scan/research checkpoint. It expands opportunity discovery from BTC-only scanning to dynamically discovered, liquid USDT-margined perpetuals on Bybit, Binance, and OKX.

It does **not** grant live order execution authority. Production execution remains separately governed by `docs/checkpoints/BYBIT_BTC_STATEFLOW_2_1_20260904.md` (`BYBIT-BTC-STATEFLOW-2.1`) until a later execution migration is explicitly approved, deployed, and runtime-verified.

## Universe
- Discover active USDT perpetual contracts dynamically from Bybit, Binance, and OKX.
- BTC receives no ranking bonus, routing preference, or special eligibility exemption.
- A symbol must pass configured freshness, spread, liquidity, history, venue-coverage, and data-quality gates.
- Minimum cross-venue coverage is policy-driven and defaults to two venues where structurally possible.
- Newly listed, stale, malformed, price-divergent, or illiquid symbols fail closed.

## Decision flow
`universe discovery -> liquidity eligibility -> regime/volatility -> market structure -> sweep/reclaim OR break/retest -> executed flow -> near-touch L2/microprice -> OI/funding/crowding -> liquidation context -> cross-venue consistency -> risk/reward -> A+ rank -> top candidate`

No single candle, indicator, funding value, OI change, book imbalance, liquidation print, AI opinion, or aggregate score can independently authorize A+.

## Candidate states
- `A+ LIVE CANDIDATE`: highest-quality research setup after every mandatory gate passes. The label does not guarantee profit and does not grant execution permission.
- `WATCHLIST`: structure is promising but one or more confirmations/triggers are incomplete.
- `NO A+ SETUP`: no eligible symbol passes all A+ gates. Never manufacture a trade.

## Structure families
- liquidity sweep + reclaim
- break + retest with acceptance
- displacement + controlled retest
- regime-compatible continuation with clear invalidation

Every qualifying candidate must include direction, trigger, entry zone, structural invalidation, stop, target logic, reward/risk, evidence freshness, and source provenance.

## Microstructure and derivatives
Executed taker flow, near-touch L2/microprice, OI, funding/premium, crowding and liquidation evidence are confirmation/context layers. They cannot create a setup without valid structure. Resting walls are treated as spoofable unless supported by executed behavior or persistent depth.

## Cross-venue gate
Compare semantically equivalent executable prices and context only after symbol/instrument/quote normalization. Stale venues cannot overrule fresh venues. Unresolved material divergence is `PRICE_DIVERGENCE` and blocks A+.

## Ranking
Ranking is gate-first, score-second. Mandatory-gate failures cannot be offset by a high score. Ties or contradictory finalists resolve to `WATCHLIST` or `NO A+ SETUP`, not arbitrary selection.

## Risk policy
Existing equity risk tiers remain:
- Normal 0.75%
- Strong 1.00%
- A+ 1.25%
- Hard single-entry cap 1.50%

Existing active-risk, margin, reserve and drawdown governors remain controlling. No martingale, no grid rescue, no add-to-loser. A+ quality never overrides risk locks.

## Authority separation
### Scan authority
May discover and evaluate eligible USDT perpetuals across Bybit, Binance and OKX.

### Research authority
May return ranked candidates, watchlists, evidence traces and hypothetical entry/SL/TP plans.

### Execution authority
Not granted by this checkpoint. Live orders remain under `BYBIT-BTC-STATEFLOW-2.1` and its venue/account/runtime gates.

Research evidence must carry `research_only=true` and `production_execution_authority=false` where represented as machine-readable output.

## Preservation rules
- Preserve existing BTC state/KV and Bybit live infrastructure.
- Do not resurrect legacy multi-coin execution, Signal V10/V11, Forex/Meme execution, or AI-council execution authority.
- Provider skills/plugins are evidence sources only.
- G9 research evidence remains research-only and cannot self-promote.

## Rollout
Phase 1: multi-coin research scanner only.
Phase 2: shadow validation/outcome tracking.
Phase 3: separate controlled execution design requiring new explicit approval.

No phase may silently advance to the next.
