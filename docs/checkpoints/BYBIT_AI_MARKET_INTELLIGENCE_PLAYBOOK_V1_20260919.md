# BYBIT AI MARKET INTELLIGENCE PLAYBOOK V1

Updated: 2026-09-19 UTC+7

## Purpose

This playbook defines how all trading AIs analyze BTCUSDT, how evidence is gathered, how stop/target geometry is checked, and how post-trade learning may propose bounded improvements.

It does not create a second trading authority. Production execution authority remains `BYBIT-BTC-STATEFLOW-2.1`.

## 1. Evidence hierarchy

A trade thesis should be assembled in this order:

1. market regime and multi-horizon structure;
2. liquidity event: sweep/reclaim, break/retest, absorption or exhaustion;
3. executed flow persistence, not a single spike;
4. near-touch L2 liquidity + microprice + spread/fragility;
5. derivatives context: OI, funding, premium/basis, long-short crowding;
6. liquidation context;
7. realized volatility and execution cost;
8. stop/target geometry;
9. AI specialist challenge;
10. deterministic risk and execution gates.

No single indicator, OI move, funding reading, order-book wall, liquidation print, candle, model opinion or social/news item can authorize a trade by itself.

## 2. Market data

Canonical Bybit evidence:
- public linear WebSocket orderbook L50;
- public trades;
- all-liquidation stream;
- ticker stream;
- REST open interest;
- REST long/short account ratio;
- ticker funding, mark/index, premium/basis;
- kline-derived 5m/15m/60m structure and realized volatility;
- account fee rate for cost-aware geometry.

Orderbook processing must reset on a fresh snapshot and apply deltas exactly. Displayed liquidity is treated as transient evidence, not guaranteed executable liquidity.

## 3. Structure and regime

The structure agent compares 5m / 15m / 60m:
- recent highs/lows;
- HH/HL or LL/LH progression;
- break and close beyond prior structure;
- sweep beyond prior level followed by reclaim;
- directional efficiency;
- trend/range/squeeze/reversal/high-vol shock.

A counter-trend trade needs materially stronger reversal evidence than a trend-continuation trade.

## 4. Flow and liquidity

Flow is evaluated over 1s/3s/5s/15s/60s.

Preferred:
- 3s/5s/15s persistence;
- price follows aggressor flow;
- microprice and near-touch imbalance are not strongly contradictory;
- spread remains executable;
- liquidation impulse has follow-through.

Rejected or downgraded:
- one-second spike with no 5s/15s persistence;
- book imbalance without executed flow;
- price moving opposite to aggressor flow;
- widening spread / fragile near-touch depth;
- stale or REST-only microstructure for autonomous new risk.

## 5. Derivatives context

OI/funding/crowding is context, not a standalone signal.

Examples:
- price up + OI up can support fresh participation, but crowding/funding may make late entry unattractive;
- price up + OI down can indicate short covering rather than durable new demand;
- extreme funding/premium against the trade reduces risk or vetoes if reward cannot compensate;
- long/short account ratio is treated as crowding evidence only.

## 6. Stop-loss geometry

There is no stop placement that guarantees a position will not be swept.

The engine therefore avoids placing SL exactly on obvious recent swing levels.

For a candidate:
1. identify nearby thesis-invalidation levels from recent structure, sweep level and local range;
2. ignore remote structure that would make a scalp stop unreasonably wide;
3. place the stop beyond the selected invalidation level;
4. add a dynamic noise buffer based on:
   - price-relative minimum;
   - current spread;
   - local 5m range;
   - local 15m range;
5. if structural invalidation is too far for the scalp geometry, reject the setup instead of pulling the stop inside invalidation;
6. use Bybit `MarkPrice` as stop trigger for the current full-position protection path;
7. never widen a live protective stop after it has tightened.

Position size is reduced to fit the wider valid stop. The stop is never tightened merely to preserve desired lot size.

## 7. Take-profit geometry

Base target is regime/tier adaptive R.

For RANGE / REVERSAL / TRANSITION:
- locate nearest opposing structural/liquidity reference;
- front-run it by a spread/noise buffer;
- if this destroys minimum reward/risk after costs, reject the setup rather than projecting TP through the obstacle.

For TREND / BREAKOUT:
- target may remain R-based when opposing liquidity has already been cleared and flow supports continuation.

All targets remain fee/funding/slippage aware.

## 8. AI roles

### structure_regime_agent
Supports only when structure, regime, sweep/break/retest and stop invalidation are coherent.

### flow_liquidity_agent
Supports only when executed-flow persistence, L2, microprice and spread quality are coherent.

### derivatives_risk_agent
Checks OI/funding/premium/crowding/volatility/cost. It may reduce risk only.

### independent_checker
Searches for contradiction, stale evidence, stop inside invalidation, TP through nearby opposing liquidity, cost mismatch or overconfidence.

No majority vote.

## 9. Coin research lane

Broad crypto discovery remains research-only until a separate authority migration.

For any coin considered for future execution, collect:
- instrument status and contract constraints;
- turnover/liquidity/spread/depth;
- listing age and data history;
- funding and OI behavior;
- realized volatility and gap behavior;
- execution/slippage samples;
- market-cap / circulating-supply / token-unlock context when trustworthy external sources are available;
- exchange and project-specific operational risks.

A coin is not promoted because of social popularity or one high-return backtest.

## 10. Self-calibration

Post-trade learning is evidence-driven and candidate-only.

Track:
- net expectancy in R;
- profit factor;
- context-conditioned win/loss distribution;
- MAE/MFE;
- slippage and fees;
- stop swept then thesis recovered;
- TP missed then reversal;
- AI veto precision;
- per-regime and per-setup performance.

Minimum before proposing parameter changes:
- 30 closed trades overall;
- 12 samples for an affected regime;
- rolling windows 30 / 75 / 150.

Permitted candidate changes are bounded:
- entry threshold: +/-10%;
- stop noise buffer: +/-15%;
- target R: +/-10%;
- AI risk-reduction amount: +/-15%.

Learning may never:
- auto-increase the hard risk ceiling;
- auto-enable a new symbol;
- remove native protection;
- self-promote to Live;
- edit Stable authority without the normal promotion process.

Promotion requires Demo evidence, independent checking, no expansion of risk ceilings and a rollback snapshot.

## 11. Outcome standard

The goal is not maximum trade frequency and not maximum win rate.

The objective is:
- coherent evidence;
- valid invalidation;
- executable cost-adjusted reward;
- bounded downside;
- adaptive compounding;
- reduced risk during drawdown;
- reproducible performance across regimes.

No component may describe a trade as guaranteed, unsweepable or certain to be profitable.
