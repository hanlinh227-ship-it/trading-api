# Multi-Coin A+ Scanner — Design Specification

Date: 2026-09-14
Status: Approved design, implementation pending
Repository: `hanlinh227-ship-it/trading-api`
Branch: `spec/multi-coin-a-plus-scanner`

## 1. Objective

Replace the current BTC-only opportunity-scanning assumption with a market-wide USDT perpetual scanner that can discover and rank A+ setups across liquid crypto markets while preserving strict evidence quality, risk controls, and execution safety.

The system must scan broadly but decide narrowly. It may evaluate many symbols, but it must return only the best qualified candidate, a watchlist state, or no setup at all.

This design does not immediately enable live order placement on additional symbols. Research/scanning authority is expanded first. Live execution authority remains separately gated until venue/account/runtime verification is explicitly implemented and approved.

## 2. Core Principle

Canonical decision flow:

`universe discovery -> liquidity eligibility -> regime/volatility -> market structure -> sweep/reclaim OR break/retest -> executed flow -> near-touch L2/microprice -> OI/funding/crowding -> liquidation context -> cross-venue consistency -> risk/reward -> A+ rank -> top candidate`

No single candle, indicator, funding reading, OI reading, book imbalance, liquidation print, AI opinion, or score may independently authorize a trade.

## 3. Market Universe

Primary scan universe:

- USDT-margined perpetual contracts.
- Venues: Bybit, Binance, OKX.
- Symbols are discovered dynamically from venue market metadata; no BTC-first routing.
- Major assets such as BTC, ETH, SOL, BNB, XRP, DOGE and other sufficiently liquid contracts are peers inside the same universe.

A symbol is eligible only if it passes all mandatory data-quality and liquidity gates.

### 3.1 Mandatory eligibility gates

A candidate must satisfy:

1. Active perpetual contract on at least one target venue.
2. Reliable market data on at least two of the three target venues where cross-venue comparison is structurally possible.
3. Minimum quote freshness within the configured freshness SLA.
4. Spread below the configured maximum for the symbol/liquidity tier.
5. Adequate order-book depth for the intended risk/notional.
6. Adequate recent traded volume.
7. Meaningful derivatives data such as OI/funding where the venue exposes it.
8. No unresolved price divergence, stale feed, malformed symbol mapping, or venue-status conflict.
9. Newly listed or highly illiquid contracts are excluded until they satisfy a minimum stability/history gate.

Thresholds must be configuration-driven rather than hard-coded into strategy logic.

## 4. Venue Roles

The scanner treats Bybit, Binance, and OKX as evidence providers and potential execution venues.

### 4.1 Evidence role

For every candidate, the system should gather as available:

- executable bid/ask
- last/mark/index price
- candles across required timeframes
- order-book depth / near-touch liquidity
- recent executed trades
- open interest
- funding / premium
- long-short or crowding context where available
- liquidation data where available

### 4.2 Execution-venue selection

For a trade-ready candidate, venue ranking must consider:

- fresh executable price
- spread
- depth/slippage estimate
- price deviation from other venues
- market-data health
- instrument availability
- account/runtime capability once live execution is later enabled

The chosen venue must be explicitly shown in the result. The system must never silently assume Bybit or Binance.

## 5. Candidate States

The output vocabulary is deliberately small to avoid ambiguity.

### `A+ LIVE CANDIDATE`

All mandatory structural, microstructure, derivatives-context, cross-venue, freshness, and risk gates pass.

This label means the setup meets the system's highest-quality criteria. It does not imply certainty or guaranteed profit.

### `WATCHLIST`

The candidate has a strong structure but one or more non-fatal confirmations are missing, not yet triggered, or not fresh enough for entry.

The response must state the exact missing trigger(s).

### `NO A+ SETUP`

No symbol in the eligible scan universe passes the A+ gate.

The system must not manufacture a setup merely to satisfy a request for a trade.

## 6. Structure Engine

Market structure remains the primary strategy authority.

Valid setup families include:

- liquidity sweep followed by reclaim
- break and retest with acceptance
- displacement followed by controlled retest
- regime-compatible continuation where invalidation is structurally clear

Every candidate must define:

- direction
- trigger
- entry zone
- structural invalidation
- stop location
- target logic
- expected reward/risk

A setup without a clear structural invalidation cannot be A+.

## 7. Microstructure Confirmation

After structure qualifies, the system checks short-horizon evidence:

- executed taker flow supports the proposed direction
- near-touch L2 liquidity is not materially contradictory
- spread/slippage remain acceptable
- microprice/book pressure does not invalidate the structural thesis

Order-book walls alone cannot authorize or veto a setup unless supported by executed behavior or persistent depth evidence.

## 8. Derivatives Context

The scanner evaluates:

- open-interest direction and rate of change
- funding rate / premium
- top-trader and global crowding where available
- liquidation clusters / liquidation flow where available

These signals are contextual modifiers, not primary triggers.

Examples:

- rising price + rising OI may support continuation, subject to crowding
- rising price + collapsing OI may indicate short covering rather than durable demand
- extreme positive funding / long crowding reduces long quality
- extreme negative funding / short crowding reduces short quality

## 9. Cross-Venue Consistency

A candidate must pass a cross-venue sanity check before A+ classification.

The system must compare:

- executable prices
- mid/mark/index relationships where available
- spread and freshness
- major structural disagreement

If venue divergence exceeds configured tolerance, classify the symbol as `PRICE_DIVERGENCE` and prevent A+ promotion until resolved.

No stale venue may overrule a fresh venue.

## 10. A+ Ranking Model

The ranker is gate-first, score-second.

A symbol that fails a mandatory gate cannot compensate with a high aggregate score.

After mandatory gates pass, ranking considers:

1. structural clarity
2. trigger quality
3. executed-flow alignment
4. L2/microprice alignment
5. OI quality
6. funding/crowding quality
7. liquidation context
8. cross-venue consistency
9. liquidity/spread/slippage
10. reward/risk quality
11. freshness/completeness confidence

The ranker returns a deterministic top candidate with an auditable evidence trace.

If the top candidates are materially tied or evidence is contradictory, the correct result is `WATCHLIST` or `NO A+ SETUP`, not arbitrary selection.

## 11. Output Contract

Default user-facing scan result should be concise and contain:

- state: `A+ LIVE CANDIDATE`, `WATCHLIST`, or `NO A+ SETUP`
- symbol
- direction
- selected venue
- current executable price and quote age
- trigger/entry zone
- stop
- target(s)
- reward/risk
- A+ rationale summary
- invalidation condition
- cross-venue confirmation summary
- data-source timestamps/freshness

When there is no A+ setup, the system may optionally return up to three watchlist symbols, but must not present them as trade-ready.

## 12. Risk Model

Retain the existing equity-based risk tiers unless a later risk-specific spec changes them:

- Normal: 0.75%
- Strong: 1.00%
- A+: 1.25%
- Hard single-entry cap: 1.50%

Additional existing portfolio controls remain conceptually preserved:

- active-risk cap
- margin cap
- reserve target
- drawdown governor
- no martingale
- no add-to-loser
- no grid rescue
- pyramiding only into winners under explicit risk controls

A+ quality changes allowed risk within policy; it never overrides drawdown or margin governors.

## 13. Authority Separation

The architecture must explicitly separate three authorities.

### 13.1 Scan authority

May discover and evaluate all eligible USDT perpetual symbols across Bybit, Binance, and OKX.

### 13.2 Research authority

May produce ranked candidates, evidence traces, watchlists, and hypothetical entry/SL/TP plans.

### 13.3 Execution authority

Controls whether an order can actually be placed on a venue/account/symbol.

Execution authority must require explicit venue-specific capability checks, credentials, runtime revision alignment, safety switches, and account validation.

Expanding scan authority must not implicitly expand live execution authority.

## 14. Migration from BTC-Only StateFlow

The current BTCUSDT Bybit StateFlow remains a proven strategy/evidence component rather than being deleted.

Migration rules:

1. Extract reusable BTC StateFlow logic into symbol-agnostic strategy primitives where valid.
2. Preserve BTC-specific state and KV keys; do not reset existing BTC state during migration.
3. Introduce a universe scanner above strategy evaluation.
4. Introduce symbol adapters for venue normalization.
5. Keep venue-specific data collectors behind normalized interfaces.
6. Replace the global `BTCUSDT Bybit only` scan authority with multi-coin scan authority.
7. Preserve existing BTC live-execution boundary until the multi-venue execution layer receives a separate explicit approval and verification.
8. Legacy retired multi-coin engines must not be resurrected as strategy authority; only reusable, validated components may be adapted.

## 15. Data Contracts

All normalized market evidence must include, where applicable:

- venue
- symbol
- instrument type
- source timestamp
- received timestamp
- quote age
- freshness state
- bid/ask/mid/last/mark/index
- source/provider identity
- source revision/SHA where produced by internal runtime
- authority scope
- execution capability state

Candidate evidence must be reproducible enough to explain why a symbol passed or failed each gate.

## 16. Failure Modes

Mandatory fail-closed conditions include:

- stale critical market data
- contradictory symbol mapping
- unresolved venue price divergence
- insufficient liquidity
- missing mandatory structural data
- ambiguous multiple strategy routes with no deterministic resolution
- account/runtime mismatch for live execution
- unsupported symbol on chosen execution venue
- risk-governor lock

The scanner may continue evaluating other symbols when one symbol fails.

## 17. Performance Model

Scanning must be staged to control latency and provider load.

Recommended pipeline:

1. broad lightweight universe scan
2. liquidity/volume/spread pruning
3. structural pre-screen
4. deep microstructure/derivatives analysis only for finalists
5. cross-venue confirmation
6. A+ ranking

The system should not request expensive deep data for every listed perpetual on every cycle.

## 18. Validation and Testing Requirements

Implementation must include tests for:

- dynamic symbol discovery
- symbol normalization across all three venues
- liquidity filtering
- stale-data rejection
- price-divergence rejection
- structure-family qualification
- ranking determinism
- tied/ambiguous candidate handling
- venue selection
- no-A+ behavior
- preservation of existing BTC state
- enforcement of scan/research/execution authority separation
- risk-governor precedence

A regression test must prove that a non-BTC symbol can become the top A+ research candidate while BTC does not receive preferential treatment.

A separate regression test must prove that this does not automatically grant that symbol live execution permission.

## 19. Rollout Plan

Phase 1 — Multi-coin research scanner

- enable dynamic USDT perpetual universe
- Bybit + Binance + OKX evidence
- research-only A+ ranking
- no expansion of live order authority

Phase 2 — Shadow validation

- run scanner continuously
- record candidate outcomes
- compare venue consistency and signal stability
- validate false-positive / stale-data failure behavior

Phase 3 — Controlled execution design

- separate explicit spec and approval
- venue/account safety contracts
- symbol-specific order constraints
- deployment/runtime verification

No phase may silently advance to the next.

## 20. Canonical Naming

Proposed system authority name:

`MULTI-COIN-USDT-PERP-A-PLUS-SCANNER-1.0`

The name identifies scanning/research authority and must not be interpreted as universal live-execution authority.

## 21. Success Criteria

The design is successfully implemented when:

1. A scan request searches the eligible USDT perpetual universe rather than defaulting to BTC.
2. BTC has no built-in ranking advantage.
3. Bybit, Binance, and OKX contribute normalized evidence where available.
4. The system can legitimately select ETH, SOL, BNB, XRP, DOGE, or another eligible symbol as the top candidate.
5. It returns `NO A+ SETUP` when none pass.
6. Every A+ result has fresh executable pricing, structural invalidation, risk/reward, and cross-venue evidence.
7. Research authority and execution authority cannot be confused in code or user-facing output.
8. Existing BTC state and safety controls remain intact during migration.

## 22. Non-Goals

This spec does not:

- guarantee profitable trades
- force at least one trade per scan
- restore retired legacy multi-coin strategy engines as authority
- authorize withdrawals/transfers
- enable live execution across all venues without a later approved execution spec
- use AI consensus as a substitute for market evidence

## 23. Decision Summary

Approved direction: Option A.

The system scans broadly across liquid USDT perpetuals on Bybit, Binance, and OKX; validates candidates through state-first structural and microstructure evidence; ranks only qualified setups; chooses the best venue explicitly; and returns one A+ candidate, a watchlist state, or no setup. Scan/research expansion is decoupled from live execution expansion to preserve safety and prevent authority confusion.
