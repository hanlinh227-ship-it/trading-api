# Cloud 10-Coin Backtest G2 — Design

Date: 2026-09-13
Status: APPROVED IN CHAT
Branch: `research/cloud-10coin-80wr-100trades-20260913`

## Goal
Raise precision without weakening the research gate. Each coin must still independently satisfy >=100 completed trades and >=80% observed win rate at RR 1:2 after validation/holdout, with positive post-cost expectancy.

## Why G1 is insufficient
G1 has enough data and often enough trades, but its best profiles remain around 45–62% RR2 on evaluation/holdout. The bottleneck is therefore signal-state selection and entry geometry, not data volume. G1 also selects one development-best profile per coin and uses a loose `sweep_mss` proxy rather than a true causal state sequence.

## G2 architecture

### 1. Strict causal state machine
Add a strict `sweep_mss_ote_g2` family. A candidate is valid only when all states occur causally in sequence:

1. closed 1h/4h regime agrees with direction;
2. liquidity sweep occurs against the intended trade direction;
3. within a bounded confirmation window a displacement candle breaks a pre-sweep structure level (MSS);
4. MSS displacement body is at least a configured ATR fraction and closes directionally;
5. taker flow and relative trade/volume intensity confirm or at minimum do not oppose the move;
6. entry is a later OTE/deep retracement of the MSS impulse;
7. stop is beyond sweep invalidation plus a bounded ATR buffer;
8. risk distance must exceed a minimum ATR fraction and a minimum cost-to-risk ratio.

No state can look forward beyond its own candle close.

### 2. Regime features
Extend causal features with:

- closed-H1 and closed-H4 trend direction;
- trend-strength buckets;
- compression/normal/expansion volatility regimes;
- directional taker-flow EMA and flow divergence versus price impulse;
- relative trade-count and volume intensity;
- rolling swing highs/lows needed by the state machine.

All rolling references must use shifted/prior data where the feature represents information that must have existed before the current candle.

### 3. Candidate quality and risk floor
Every generated candidate gets a deterministic quality score composed only of signal-time data. Candidate creation rejects trades where:

- structural risk <= 0;
- risk/ATR is below the configured floor;
- round-trip cost in R exceeds a configured ceiling;
- fill latency exceeds the profile window.

The score is used only for conflict resolution between simultaneously active profiles, not to inspect future outcomes.

### 4. Per-coin ensemble
G2 may lock 1–3 profiles per coin.

Selection protocol:

- development: search bounded family grids and retain a small Pareto/frontier set;
- validation: choose an ensemble of at most 3 profiles using only validation results;
- freeze the ensemble definition and member parameters;
- holdout: evaluate the frozen ensemble exactly once;
- overlapping signals: keep the highest signal-time quality score, then deterministic family/name tie-break; never choose by eventual outcome.

The ensemble is not allowed to create per-date exceptions or dynamically mutate after holdout starts.

### 5. Search objective
Candidate/profile ranking emphasizes:

- RR2 win rate;
- Wilson lower bound;
- completed-trade breadth;
- positive post-cost expectancy;
- monthly/quarterly stability;
- parameter-neighborhood stability.

Penalties apply for excessive parameter complexity, high cost/R, and concentration in one short calendar pocket.

### 6. Historical extension rule
If a frozen profile/ensemble has >=80% RR2 WR but <100 completed trades, keep its rules frozen and extend history backward where Binance USD-M archive data is available. Do not loosen the rule simply to manufacture 100 trades.

### 7. Hard PASS gate
A coin is PASS only when all are true:

- evaluation completed trades >=100;
- evaluation RR2 WR >=0.80;
- post-cost expectancy >0;
- validation and holdout each avoid catastrophic collapse; for segments with >=20 trades, RR2 WR must be >=0.60;
- ensemble/profile was frozen before holdout;
- no leakage/look-ahead;
- conservative same-bar ordering remains active.

Observed 80% does not imply true future WR is 80%.

## G2 files

Modify:
- `research/cloud_10coin_backtest/features/state.py`
- `research/cloud_10coin_backtest/strategies/common.py`
- `research/cloud_10coin_backtest/optimize/search.py`
- `research/cloud_10coin_backtest/optimize/selection.py`
- `research/cloud_10coin_backtest/run.py` only if required for generation metadata/results.

Create:
- `research/cloud_10coin_backtest/strategies/sweep_mss_ote_g2.py`
- `research/cloud_10coin_backtest/optimize/ensemble.py`
- focused G2 tests under `research/cloud_10coin_backtest/tests/`.

## Non-goals

- no live trading;
- no production authority change;
- no martingale/grid rescue;
- no post-outcome trade selection;
- no arbitrary session/date exclusions selected because they won historically;
- no cross-coin SMT in G2; that is reserved for G3 only if G2 exhausts without reaching the target.

## Completion
Engineering G2 completes when all G2 tests plus the existing regression suite pass on Railway and a reproducible ten-coin G2 full run finishes. Research success remains separate: 10/10 coins must satisfy the hard PASS gate; otherwise the report must state remaining bottlenecks without fabricating 80%.