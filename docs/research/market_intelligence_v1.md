# Market intelligence evidence contract v1 — 2026-10-28

RESEARCH-ONLY. Does not promote a strategy, override project authority, or authorize execution.
Current strategy authority remains docs/checkpoints/CURRENT_HANDOFF.md: BYBIT-TOP100-STATEFLOW-3.0. Forex V76 has 0/28 OOS-promoted entries; V73 frozen no-CUT stays untouched.

## Consumers
- Private linhai-domain-skills v0.9.0: full-market-signal-research
- Hatchable Botkeep E2E Paper v15: lib/market-intelligence.js, scan packet marketContext and candidate.analysis
- Other scanners: use OPTIONAL read-only research annotations, never replace data/decision.json strategy authority.

## Universe
- FX: 28 canonical major pairs, H4/H1/M15/M5, 8-currency strength. Technical breadth computed from signal-engine BUY/SELL is not independent macro evidence.
- XAU/XAG: broker-exact price, real yields, USD, relative metals strength, liquidity and session. Silver proxy is research only.
- Crypto: BTC/ETH regime, measured universe breadth, spot vs perps, OI/funding/basis/liquidation data only when verifiable.
- Macro: published timestamp, vintage, central-bank expectations and major releases; never insert later actuals into earlier market decisions.

## Data contract
See docs/research/market_evidence_contract_v1.json. Each datum must include source/venue/instrument/field/asOfUTC/fetchedAtUTC and publication UTC where available.
Missing data = UNAVAILABLE. Quote from research venue = PROXY for other execution venues. No fabricated macro, order flow or bid/ask.

## Decision sequence
1. Data quality and active research authority gate.
2. Regime TREND_UP, TREND_DOWN, RANGE, TRANSITION, EVENT_SHOCK or UNKNOWN.
3. Cross-market strength, market breadth, macro and event risk; avoid double-counting correlated indicators.
4. H4/H1 context; M15/M5 structure and trigger; liquidity, invalidation, stop and target after cost.
5. Compare evidence for BUY vs SELL; test strongest countercase; veto missing trigger, wrong venue, old quote, event blackout, low RR or unapproved strategy.
6. Rank up to TOP3 distinct exposures, possibly zero; use HOLD where inconclusive.

Initial research score weights (unvalidated): regime/macro 25, relative strength/intermarket 20, multiframe structure 25, liquidity/flows 15, entry/SL/TP/cost 15. Not a win probability.

## Evaluation
Deterministic fixtures for opposite currency legs, breadth coverage, regime mismatch, stale feeds, venue mismatch, missing data and RR; paper smoke tests; separate chronological train/validation/untouched OOS plus regime walk-forward and costs.
Never auto-promote an entry method simply because the proposed score rises.

## Implementation status
Botkeep v15 computes technical FX pair strength from existing signals, qualified 24-hour crypto breadth, and H1/M5 regime heuristic. Real central-bank events, COT, funding, OI and orderbook are not yet fetched into scanner; marked UNVERIFIED in packet. Work activation is separate and not proven. No broker orders.
