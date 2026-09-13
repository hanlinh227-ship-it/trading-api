# Cloud 10-Coin Backtest Engine — Design

Date: 2026-09-13
Status: DESIGN APPROVED IN CHAT; IMPLEMENTATION NOT STARTED
Branch: `research/cloud-10coin-80wr-100trades-20260913`

## 1. Objective

Build an isolated cloud backtest service that can test ten crypto perpetual markets with enough historical depth and execution detail to evaluate a strict research target:

- universe: BTCUSDT, ETHUSDT, BNBUSDT, XRPUSDT, SOLUSDT, TRXUSDT, DOGEUSDT, LINKUSDT, ADAUSDT, XLMUSDT;
- each coin has its own profile and may use different strategy-family weights, side restrictions, thresholds, and execution geometry;
- each coin must produce at least 100 completed trades before it can be considered for PASS;
- target win rate is at least 80% at RR 1:2;
- RR 1:1 is reported as a secondary diagnostic, not a substitute for the RR 1:2 gate;
- results must survive validation/holdout checks and may not rely on selecting winners after outcomes are known.

This is research only. It does not replace the existing BTCUSDT Bybit production authority and must not place, amend, cancel, or close live orders.

## 2. Authority and constraints

The implementation must comply with:

- `AGENTS.md` / GITHUB_BRAIN_V4 routing and authority rules;
- `AI_SKILL_LIBRARY/AI_GLOBAL_CHECKPOINT.md` zero-local cloud runtime contract;
- `AI_SKILL_LIBRARY/skills/trading/quant_backtesting.md` validation rules;
- `docs/checkpoints/CURRENT_HANDOFF.md` and the canonical BTCUSDT Bybit production authority.

Key hard constraints:

1. Cloud-first; no user-local Python/Node installation is required.
2. Backtest infrastructure must be isolated from `crypto-research-gateway-prod`.
3. Binance access is public, read-only market data only.
4. No credentials, account mutation, order placement, leverage mutation, wallet operations, transfer, or withdrawal functionality.
5. Research outputs never self-promote to production trading authority.
6. A historical simulation is evidence only, not a profitability guarantee.

## 3. Deployment architecture

Create a separate Railway service:

- name: `crypto-backtest-job`;
- project: existing `github-brain-zero-local-runtime`;
- source repository: `hanlinh227-ship-it/trading-api`;
- source branch during development: `research/cloud-10coin-80wr-100trades-20260913`;
- root directory: `/research/cloud_10coin_backtest`;
- runtime: Python via Railpack;
- public domain: none;
- outbound network: HTTPS only to approved public Binance endpoints;
- shared volumes/databases with existing gateway services: none;
- restart policy: NEVER for one-off jobs;
- production gateway services must not be edited, restarted, or redeployed as part of this work.

The service is a batch research job, not an always-on API.

## 4. Data layer

### 4.1 Primary market data

Use Binance USD-M perpetual market data for each symbol.

Required 5-minute kline fields:

- open time;
- open/high/low/close;
- base volume;
- quote volume where available;
- trade count;
- taker-buy base volume;
- taker-buy quote volume where available.

The taker-buy fields provide an executed-flow proxy without depending on short-retention ratio endpoints.

### 4.2 Higher-timeframe state

Derive 1h and 4h state causally from 5m bars or download native 1h/4h futures klines when doing so improves efficiency. No higher-timeframe candle may be visible before it has closed.

### 4.3 Derivatives context

Where historical coverage is available without weakening reproducibility, optionally ingest:

- funding history;
- premium/index context;
- open-interest history;
- taker buy/sell metrics;
- crowding/long-short metrics.

Because some Binance derivatives-stat endpoints retain only a limited recent history, these fields must be optional features. The baseline backtest must remain reproducible from long-retention kline data alone. Missing derivatives context must never be silently forward-filled across unavailable periods.

### 4.4 Historical depth

The runner should start with 2024-01-01 through the most recent fully closed day supported by the data source, then expand earlier if a qualifying A+ profile has fewer than 100 trades.

For a coin that achieves >=80% WR with fewer than 100 trades, the preferred action is to extend history while keeping the profile frozen, not relax the rule merely to increase trade count.

### 4.5 Cache

Cache immutable monthly symbol/timeframe files under the job workspace during a run. Cache keys include venue, instrument, symbol, interval, month, and data-source version. A cache integrity manifest records row count, first/last timestamp, expected interval, gaps, duplicates, and checksum.

## 5. Data-quality gates

Each symbol/timeframe must pass before optimization:

- chronological ordering;
- unique timestamps;
- gap audit;
- valid OHLC relationships;
- positive prices;
- nonnegative volumes and trade counts;
- expected timezone UTC;
- fully closed final candle only.

Any material gap is either explicitly excluded from candidate windows or causes the affected window to fail closed. Synthetic candles are not created to hide missing exchange data.

Every final report must state exact source, instrument, date range, bar count, gaps, and coverage.

## 6. Strategy-family architecture

The optimizer may research several causal families, but every final profile is explicit and deterministic.

Candidate families:

1. HTF trend -> displacement -> deep retracement/OTE.
2. Liquidity sweep/reclaim -> MSS -> retracement entry.
3. Breakout -> retest -> continuation.
4. Volatility compression -> displacement breakout -> retest.
5. Exhaustion / mean reversion after statistically large deviation and rejection.
6. Relative-strength / cross-sectional state where all features are computed only from information available at signal time.

Each family exposes only a bounded parameter grid. The optimizer must not create arbitrary per-date/per-trade exceptions.

## 7. Per-coin profile model

No universal strategy is forced across all ten coins.

A profile may contain:

- allowed direction: long, short, or both;
- active family/families;
- HTF state filters;
- structure/liquidity requirements;
- displacement/body/close-location thresholds;
- volume/taker-flow thresholds;
- volatility-regime thresholds;
- retracement depth;
- stop geometry;
- maximum fill latency;
- maximum holding horizon;
- session filter only if it survives stability testing and is not selected from a single favorable month.

Profile complexity is penalized. Simpler profiles are preferred when performance is statistically indistinguishable.

## 8. Execution simulation

Execution rules are causal and conservative:

1. A signal exists only after the signal candle closes.
2. Orders may fill only on subsequent bars.
3. Limit fills require the subsequent bar to trade through the requested price.
4. Stops are placed at the specified structural/volatility invalidation level before outcome evaluation.
5. TP for the primary gate is exactly 2R from the simulated entry.
6. RR 1:1 outcome is recorded separately from the same entry/stop.
7. If fill and stop occur inside the same unresolved bar and ordering cannot be inferred, count the trade pessimistically rather than deleting it.
8. If stop and TP are both touched in the same unresolved bar, count the stop first unless finer-resolution data resolves ordering.
9. No adding to losers, martingale, grid rescue, or post-hoc stop widening.
10. Fees, slippage, and funding/carry assumptions are configured before final interpretation and reported in all final metrics.

Where 1m data is practical for the small set of candidate/final trades, use it as a second-pass execution verifier without changing the already selected signal rule.

## 9. Search objective and anti-overfit rules

The optimizer must not optimize win rate alone.

Primary hard gates:

- completed trades >= 100 per coin;
- RR 1:2 win rate >= 80%;
- no look-ahead/leakage;
- minimum data coverage pass;
- validation/holdout pass.

Secondary ranking metrics:

- Wilson lower confidence bound for win rate;
- expectancy in R after costs;
- max drawdown in R;
- losing-streak distribution;
- monthly stability;
- side/family concentration;
- parameter-neighborhood stability;
- trade-count breadth.

Repeated-test selection bias is controlled by limiting family/parameter grids and keeping at least one untouched holdout segment for each research generation.

If a profile fails a holdout, that holdout result is recorded. It cannot be reused as if it were still untouched after parameters are changed. A new research generation requires a new future/earlier untouched segment.

## 10. Data split

Default chronological split for sufficiently long histories:

- development: first 60%;
- validation: next 20%;
- holdout: final 20%.

Additionally report rolling monthly and quarterly statistics.

A PASS requires all of the following:

1. at least 100 completed trades in the locked-profile evaluation sample;
2. aggregate RR 1:2 WR >=80%;
3. no validation/holdout segment with evidence of catastrophic collapse that is hidden by aggregate results;
4. positive post-cost expectancy;
5. rule was frozen before the final holdout was evaluated.

Observed >=80% is not described as statistically proven true WR >=80% unless the confidence interval supports that statement.

## 11. Optimization workflow

For each coin:

1. Audit data.
2. Generate causal features once.
3. Run bounded family searches on development data.
4. Reject families whose high-trade-count frontier is too far below target.
5. Promote only a small set of candidate A+ profiles to validation.
6. Freeze the selected profile.
7. Evaluate holdout without parameter changes.
8. If WR >=80% but n<100, extend historical range with parameters frozen.
9. If n>=100 but WR<80%, diagnose the bottleneck as one or more of:
   - state selection;
   - direction;
   - entry geometry;
   - stop geometry;
   - execution latency/fill model;
   - volatility regime;
   - executed-flow confirmation;
   - unavailable derivatives context.
10. A failed coin remains FAIL. The engine must not fabricate a PASS.

The global run stops only when all ten coins have PASS or when the configured search space is exhausted and the report clearly states which coins remain below target.

## 12. Outputs

The batch job writes machine-readable and human-readable outputs:

- `results/run_manifest.json`;
- `results/data_audit.json`;
- `results/profiles.json`;
- `results/coin_summary.csv`;
- `results/trades/<symbol>.csv`;
- `results/report.md`.

Per-coin summary includes:

- selected profile and all locked parameters;
- date ranges by split;
- trade counts;
- RR1:1 and RR1:2 wins/losses/WR;
- expectancy after costs;
- max drawdown;
- Wilson interval;
- monthly/quarterly stability;
- data coverage;
- PASS/FAIL reason.

All rejected false-positive profiles of material interest are retained in the report with their validation/holdout failure reason to prevent rediscovery and accidental reuse.

## 13. Code structure

Proposed isolated package:

```text
research/cloud_10coin_backtest/
  README.md
  requirements.txt
  run.py
  config.py
  data/
    binance_usdm.py
    audit.py
    cache.py
  features/
    state.py
    flow.py
    volatility.py
    structure.py
  strategies/
    trend_ote.py
    sweep_mss.py
    break_retest.py
    compression.py
    mean_reversion.py
  engine/
    execution.py
    outcomes.py
    splits.py
    metrics.py
  optimize/
    search.py
    selection.py
    robustness.py
  tests/
    test_no_lookahead.py
    test_same_bar_conservative.py
    test_splits.py
    test_metrics.py
    test_data_audit.py
    test_profile_freeze.py
  results/
    .gitkeep
```

Generated market datasets and large trade outputs are runtime artifacts and must not be committed to Git.

## 14. Testing and verification

Behavior changes follow RED -> GREEN -> regression suite.

Required tests include:

- feature calculations do not access future bars;
- HTF features use only closed HTF candles;
- limit fills occur only after signal close;
- ambiguous same-bar ordering is conservative;
- chronological split boundaries do not leak;
- profile-freeze prevents holdout-aware parameter mutation;
- trade counts and WR calculations are exact;
- Wilson interval implementation is correct;
- data audits detect gaps/duplicates;
- cache manifests reject corrupt/mismatched data;
- no code path imports order/account/private Binance APIs.

Before claiming implementation complete:

1. run package unit tests;
2. run a small deterministic smoke backtest;
3. run repository validators required by the current Brain authority where applicable;
4. deploy only the isolated Railway backtest service;
5. verify that existing gateway production deployment metadata did not change;
6. verify job logs identify exact source branch/SHA and run manifest.

## 15. Railway safety boundaries

The new service must:

- have a distinct service ID;
- have no public domain;
- have no shared volume;
- receive no exchange API secrets;
- have no service binding to order-execution infrastructure;
- never call private Binance endpoints;
- use restart policy NEVER for one-off runs;
- be removable without affecting the two existing research gateway services.

The existing `crypto-research-gateway-prod` must remain untouched throughout this implementation.

## 16. Completion criteria

Engineering completion means the isolated engine is deployed, reproducibly fetches/audits Binance USD-M data, runs the ten-coin research workflow, and emits the required result artifacts.

Research-target completion is stricter and separate:

- 10/10 coins PASS;
- each coin has >=100 completed trades;
- each coin has >=80% observed WR at RR 1:2 under its locked profile;
- validation/holdout gates pass;
- costs are included;
- no false-positive/overfit profile is presented as PASS.

The engineering task may complete even if the market evidence does not satisfy 10/10. In that case the final report must explicitly state the remaining failures and bottlenecks rather than inventing target attainment.
