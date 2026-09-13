# Cloud 10-Coin Backtest Engine Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build and deploy an isolated Railway Python batch job that backtests ten Binance USD-M perpetual markets with coin-specific profiles, at least 100 completed trades per coin, RR 1:2 as the hard outcome target, and strict validation/holdout controls.

**Architecture:** A standalone Python package under `research/cloud_10coin_backtest` downloads and audits public Binance USD-M data, derives causal state/flow/structure features, simulates conservative fills/outcomes, searches bounded strategy families per coin, freezes profiles before holdout, and emits reproducible artifacts. Railway runs the package as a separate one-off service with no public domain, no credentials, no shared volumes, and no linkage to live-order infrastructure.

**Tech Stack:** Python 3.12+, standard library plus `numpy`, `pandas`, `requests`, `pytest`; Binance public USD-M REST; Railway Railpack.

**Spec:** `docs/superpowers/specs/2026-09-13-cloud-10coin-backtest-design.md`

## Global Constraints

- Universe is exactly BTCUSDT, ETHUSDT, BNBUSDT, XRPUSDT, SOLUSDT, TRXUSDT, DOGEUSDT, LINKUSDT, ADAUSDT, XLMUSDT.
- Each coin owns an independent profile; no universal parameter set is required.
- A coin cannot PASS with fewer than 100 completed trades.
- Primary PASS target is observed WR >= 80% at RR 1:2 under a locked profile; RR 1:1 is diagnostic only.
- Validation and final holdout are chronological and may not influence parameter selection after freeze.
- Signal features must be causal; no future bars, incomplete HTF candles, or post-outcome trade selection.
- Ambiguous same-bar ordering is conservative: fill+stop ambiguity and TP+SL ambiguity resolve against the strategy unless 1m verification resolves order.
- No martingale, grid rescue, adding to losers, or post-hoc stop widening.
- Final reports include fees, slippage, funding/carry assumptions, expectancy, drawdown, Wilson interval, monthly stability, coverage, and false-positive rejection history.
- Binance access is public read-only market data only; no account/order/private endpoints or secrets.
- `crypto-research-gateway-prod` must not be modified, restarted, or redeployed.
- Research output never self-promotes into BTCUSDT Bybit production authority.

---

### Task 1: Package Skeleton, Configuration, and Deterministic Contracts

**Files:**
- Create: `research/cloud_10coin_backtest/__init__.py`
- Create: `research/cloud_10coin_backtest/config.py`
- Create: `research/cloud_10coin_backtest/requirements.txt`
- Create: `research/cloud_10coin_backtest/README.md`
- Create: `research/cloud_10coin_backtest/tests/test_config.py`

**Interfaces:**
- Produces: `BacktestConfig`, `CostModel`, `SYMBOLS`, `DEFAULT_CONFIG`.
- `BacktestConfig` includes `start`, `end`, `development_fraction`, `validation_fraction`, `rr_primary`, `rr_secondary`, `min_completed_trades`, `target_wr`, `fee_bps_per_side`, `slippage_bps_per_side`, `max_hold_bars_5m`, `cache_dir`, `results_dir`.

- [ ] **Step 1: Write failing config tests**

```python
from research.cloud_10coin_backtest.config import DEFAULT_CONFIG, SYMBOLS


def test_universe_is_exactly_ten_symbols():
    assert SYMBOLS == (
        "BTCUSDT", "ETHUSDT", "BNBUSDT", "XRPUSDT", "SOLUSDT",
        "TRXUSDT", "DOGEUSDT", "LINKUSDT", "ADAUSDT", "XLMUSDT",
    )


def test_hard_gates_are_locked():
    assert DEFAULT_CONFIG.rr_primary == 2.0
    assert DEFAULT_CONFIG.rr_secondary == 1.0
    assert DEFAULT_CONFIG.min_completed_trades == 100
    assert DEFAULT_CONFIG.target_wr == 0.80
```

- [ ] **Step 2: Run test and confirm RED**

Run: `pytest research/cloud_10coin_backtest/tests/test_config.py -q`
Expected: import/file failure.

- [ ] **Step 3: Implement immutable configuration dataclasses**

```python
from dataclasses import dataclass
from pathlib import Path

SYMBOLS = (
    "BTCUSDT", "ETHUSDT", "BNBUSDT", "XRPUSDT", "SOLUSDT",
    "TRXUSDT", "DOGEUSDT", "LINKUSDT", "ADAUSDT", "XLMUSDT",
)

@dataclass(frozen=True)
class CostModel:
    fee_bps_per_side: float = 5.0
    slippage_bps_per_side: float = 1.0

@dataclass(frozen=True)
class BacktestConfig:
    start: str = "2024-01-01"
    end: str | None = None
    development_fraction: float = 0.60
    validation_fraction: float = 0.20
    rr_primary: float = 2.0
    rr_secondary: float = 1.0
    min_completed_trades: int = 100
    target_wr: float = 0.80
    max_hold_bars_5m: int = 288
    cache_dir: Path = Path(".cache/cloud_10coin_backtest")
    results_dir: Path = Path("results")
    costs: CostModel = CostModel()

DEFAULT_CONFIG = BacktestConfig()
```

- [ ] **Step 4: Run tests and confirm GREEN**

Run: `pytest research/cloud_10coin_backtest/tests/test_config.py -q`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add research/cloud_10coin_backtest
git commit -m "feat: scaffold cloud 10-coin backtest package"
```

### Task 2: Binance USD-M Public Data Loader and Cache Audit

**Files:**
- Create: `research/cloud_10coin_backtest/data/__init__.py`
- Create: `research/cloud_10coin_backtest/data/binance_usdm.py`
- Create: `research/cloud_10coin_backtest/data/audit.py`
- Create: `research/cloud_10coin_backtest/data/cache.py`
- Create: `research/cloud_10coin_backtest/tests/test_data_audit.py`
- Create: `research/cloud_10coin_backtest/tests/test_binance_parser.py`

**Interfaces:**
- `parse_kline(row: list) -> dict`
- `fetch_klines(symbol: str, interval: str, start_ms: int, end_ms: int) -> pandas.DataFrame`
- `audit_bars(df, interval_ms: int) -> DataAudit`
- `load_or_fetch_month(...) -> pandas.DataFrame`

- [ ] **Step 1: Write RED tests for futures kline parsing and gap detection**

```python
def test_parse_kline_exposes_taker_flow():
    row = [1000, "10", "12", "9", "11", "20", 1299, "210", 15, "13", "140", "0"]
    out = parse_kline(row)
    assert out["open_time"] == 1000
    assert out["trade_count"] == 15
    assert out["taker_buy_base"] == 13.0
    assert out["taker_buy_quote"] == 140.0


def test_audit_rejects_duplicate_or_missing_5m_timestamp():
    df = sample_frame([0, 300_000, 900_000])
    audit = audit_bars(df, interval_ms=300_000)
    assert audit.gaps == 1
    assert audit.ok is False
```

- [ ] **Step 2: Run RED tests**

Run: `pytest research/cloud_10coin_backtest/tests/test_binance_parser.py research/cloud_10coin_backtest/tests/test_data_audit.py -q`
Expected: FAIL.

- [ ] **Step 3: Implement loader with public endpoint only**

Use only `https://fapi.binance.com/fapi/v1/klines` with `symbol`, `interval`, `startTime`, `endTime`, `limit=1500`; paginate by last open time + interval. Parse columns 0..10 and discard the unused field 11. Reject responses that are not lists.

- [ ] **Step 4: Implement immutable monthly cache manifest**

Manifest fields: `venue`, `instrument`, `symbol`, `interval`, `month`, `rows`, `first_ts`, `last_ts`, `gaps`, `duplicates`, `sha256`. A cache file is reused only if manifest metadata and checksum match.

- [ ] **Step 5: Run tests GREEN**

Run: `pytest research/cloud_10coin_backtest/tests/test_binance_parser.py research/cloud_10coin_backtest/tests/test_data_audit.py -q`
Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add research/cloud_10coin_backtest/data research/cloud_10coin_backtest/tests
git commit -m "feat: add audited Binance USD-M data loader"
```

### Task 3: Causal Feature Engine

**Files:**
- Create: `research/cloud_10coin_backtest/features/__init__.py`
- Create: `research/cloud_10coin_backtest/features/state.py`
- Create: `research/cloud_10coin_backtest/features/structure.py`
- Create: `research/cloud_10coin_backtest/features/flow.py`
- Create: `research/cloud_10coin_backtest/features/volatility.py`
- Create: `research/cloud_10coin_backtest/tests/test_no_lookahead.py`

**Interfaces:**
- `build_features(df5: DataFrame) -> DataFrame`
- Output columns include ATR, rolling MA state, closed-HTF trend labels, prior rolling highs/lows, displacement/body/close-location, relative volume, trade-intensity, taker-buy ratio, volatility regime, and compression ratio.

- [ ] **Step 1: Write RED no-lookahead tests**

```python
def test_future_price_change_does_not_change_past_features():
    a = build_features(sample_bars())
    changed = sample_bars().copy()
    changed.loc[changed.index[-1], "close"] *= 10
    b = build_features(changed)
    pd.testing.assert_series_equal(a.iloc[:-1]["atr"], b.iloc[:-1]["atr"])


def test_htf_state_uses_only_closed_hour():
    features = build_features(sample_5m_crossing_hour())
    assert features.loc["10:55", "h1_close"] == features.loc["10:00", "closed_hour_close"]
```

- [ ] **Step 2: Run RED**

Run: `pytest research/cloud_10coin_backtest/tests/test_no_lookahead.py -q`
Expected: FAIL.

- [ ] **Step 3: Implement features with explicit `.shift(1)` for prior extrema and closed HTF joins**

Resample 5m to 1h/4h with right-closed boundaries, then shift HTF state one completed bar before forward-joining to 5m rows. Compute taker ratio as `taker_buy_base / volume` only when volume > 0.

- [ ] **Step 4: Run GREEN**

Run: `pytest research/cloud_10coin_backtest/tests/test_no_lookahead.py -q`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add research/cloud_10coin_backtest/features research/cloud_10coin_backtest/tests/test_no_lookahead.py
git commit -m "feat: add causal state and flow features"
```

### Task 4: Conservative Execution and Outcome Engine

**Files:**
- Create: `research/cloud_10coin_backtest/engine/__init__.py`
- Create: `research/cloud_10coin_backtest/engine/execution.py`
- Create: `research/cloud_10coin_backtest/engine/outcomes.py`
- Create: `research/cloud_10coin_backtest/tests/test_same_bar_conservative.py`
- Create: `research/cloud_10coin_backtest/tests/test_execution.py`

**Interfaces:**
- `OrderCandidate(signal_index, side, entry, stop, max_fill_bars, max_hold_bars)`
- `simulate_trade(candidate, bars, rr=(1.0, 2.0), costs=...) -> TradeResult | None`
- `TradeResult` records timestamps, gross/net R, RR1 hit, RR2 hit, exit reason, ambiguity flags.

- [ ] **Step 1: Write RED ambiguity and causality tests**

```python
def test_order_cannot_fill_on_signal_bar():
    result = simulate_trade(candidate_at_bar_0(), bars_that_touch_entry_only_on_bar_0())
    assert result is None


def test_same_bar_tp_and_sl_is_stop_first():
    result = simulate_trade(candidate(), bars_with_tp_and_sl_same_bar())
    assert result.exit_reason == "STOP_AMBIGUOUS"
    assert result.rr2_hit is False
```

- [ ] **Step 2: Run RED**

Run: `pytest research/cloud_10coin_backtest/tests/test_execution.py research/cloud_10coin_backtest/tests/test_same_bar_conservative.py -q`
Expected: FAIL.

- [ ] **Step 3: Implement deterministic first-touch simulator**

The simulator searches only bars after `signal_index`; fill must trade through limit; stop is fixed before outcome scan; costs reduce realized R; ambiguous ordering loses conservatively.

- [ ] **Step 4: Run GREEN**

Run: `pytest research/cloud_10coin_backtest/tests/test_execution.py research/cloud_10coin_backtest/tests/test_same_bar_conservative.py -q`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add research/cloud_10coin_backtest/engine research/cloud_10coin_backtest/tests
git commit -m "feat: add conservative execution simulator"
```

### Task 5: Chronological Splits, Metrics, and Profile Freeze

**Files:**
- Create: `research/cloud_10coin_backtest/engine/splits.py`
- Create: `research/cloud_10coin_backtest/engine/metrics.py`
- Create: `research/cloud_10coin_backtest/optimize/__init__.py`
- Create: `research/cloud_10coin_backtest/optimize/selection.py`
- Create: `research/cloud_10coin_backtest/tests/test_splits.py`
- Create: `research/cloud_10coin_backtest/tests/test_metrics.py`
- Create: `research/cloud_10coin_backtest/tests/test_profile_freeze.py`

**Interfaces:**
- `chronological_splits(index, dev=0.60, val=0.20) -> SplitRanges`
- `summarize_trades(trades) -> Metrics`
- `wilson_interval(wins: int, n: int, z: float = 1.96) -> tuple[float, float]`
- `LockedProfile` serialized with `profile_hash`; holdout evaluator accepts only a frozen profile object.

- [ ] **Step 1: Write RED split/metric/freeze tests**

```python
def test_splits_do_not_overlap():
    s = chronological_splits(range(100), 0.6, 0.2)
    assert set(s.development).isdisjoint(s.validation)
    assert set(s.validation).isdisjoint(s.holdout)


def test_profile_hash_changes_if_parameter_changes():
    a = lock_profile({"family": "trend_ote", "r": 0.85})
    b = lock_profile({"family": "trend_ote", "r": 0.90})
    assert a.profile_hash != b.profile_hash
```

- [ ] **Step 2: Run RED**

Run: `pytest research/cloud_10coin_backtest/tests/test_splits.py research/cloud_10coin_backtest/tests/test_metrics.py research/cloud_10coin_backtest/tests/test_profile_freeze.py -q`
Expected: FAIL.

- [ ] **Step 3: Implement metrics and immutable profile freeze**

Metrics must include completed trades, wins/losses at 1R/2R, WR, net expectancy R, max drawdown R, max losing streak, Wilson interval, monthly counts and monthly WR.

- [ ] **Step 4: Run GREEN and commit**

Run: `pytest research/cloud_10coin_backtest/tests/test_splits.py research/cloud_10coin_backtest/tests/test_metrics.py research/cloud_10coin_backtest/tests/test_profile_freeze.py -q`
Expected: PASS.

```bash
git add research/cloud_10coin_backtest
git commit -m "feat: add splits metrics and profile freeze"
```

### Task 6: Strategy Families with Bounded Parameter Grids

**Files:**
- Create: `research/cloud_10coin_backtest/strategies/__init__.py`
- Create: `research/cloud_10coin_backtest/strategies/trend_ote.py`
- Create: `research/cloud_10coin_backtest/strategies/sweep_mss.py`
- Create: `research/cloud_10coin_backtest/strategies/break_retest.py`
- Create: `research/cloud_10coin_backtest/strategies/compression.py`
- Create: `research/cloud_10coin_backtest/strategies/mean_reversion.py`
- Create: `research/cloud_10coin_backtest/tests/test_strategy_causality.py`

**Interfaces:**
- Every module exports `family_name`, `parameter_grid()`, `generate_candidates(features, params)`.
- Candidate generation may use only current/prior feature columns and must never inspect future outcome columns.

- [ ] **Step 1: Write RED family-interface and causality tests**

```python
@pytest.mark.parametrize("module", STRATEGY_MODULES)
def test_family_contract(module):
    assert callable(module.parameter_grid)
    assert callable(module.generate_candidates)
    assert 1 <= len(module.parameter_grid()) <= 256
```

- [ ] **Step 2: Run RED**

Run: `pytest research/cloud_10coin_backtest/tests/test_strategy_causality.py -q`
Expected: FAIL.

- [ ] **Step 3: Implement bounded families**

Use compact discrete grids: retracement depths, ATR-normalized displacement/risk, relative volume/taker-ratio thresholds, max-fill latency, side restrictions, and regime filters. No dates or specific trade IDs are valid parameters.

- [ ] **Step 4: Run GREEN and commit**

Run: `pytest research/cloud_10coin_backtest/tests/test_strategy_causality.py -q`
Expected: PASS.

```bash
git add research/cloud_10coin_backtest/strategies research/cloud_10coin_backtest/tests/test_strategy_causality.py
git commit -m "feat: add bounded strategy families"
```

### Task 7: Search, Validation, Holdout, and Bottleneck Diagnosis

**Files:**
- Create: `research/cloud_10coin_backtest/optimize/search.py`
- Create: `research/cloud_10coin_backtest/optimize/robustness.py`
- Create: `research/cloud_10coin_backtest/tests/test_search_gates.py`

**Interfaces:**
- `search_coin(symbol, features, config) -> CoinResearchResult`
- Development ranks candidates; validation narrows candidates; final chosen profile is frozen before holdout.
- `diagnose_bottleneck(result) -> list[str]` returns one or more of state-selection, direction, entry-geometry, stop-geometry, execution-latency, volatility-regime, executed-flow, derivatives-context, insufficient-frequency.

- [ ] **Step 1: Write RED search-gate tests**

```python
def test_candidate_with_99_trades_cannot_pass():
    result = fake_result(n=99, rr2_wr=1.0)
    assert passes_hard_gate(result) is False


def test_candidate_with_100_trades_and_79pct_cannot_pass():
    result = fake_result(n=100, rr2_wr=0.79)
    assert passes_hard_gate(result) is False
```

- [ ] **Step 2: Run RED**

Run: `pytest research/cloud_10coin_backtest/tests/test_search_gates.py -q`
Expected: FAIL.

- [ ] **Step 3: Implement bounded search and profile freeze**

Search development only. Promote a capped top-K based on RR2 WR, Wilson lower bound, expectancy, drawdown, parameter-neighborhood stability, and trade breadth. Validation is read-only scoring. Freeze exactly one selected profile before holdout.

- [ ] **Step 4: Implement historical extension rule**

If locked profile has WR >= 0.80 but n < 100, extend earlier history without changing parameters. If n >= 100 but WR < 0.80, return FAIL and bottleneck diagnosis; do not optimize on the holdout.

- [ ] **Step 5: Run GREEN and commit**

Run: `pytest research/cloud_10coin_backtest/tests/test_search_gates.py -q`
Expected: PASS.

```bash
git add research/cloud_10coin_backtest/optimize research/cloud_10coin_backtest/tests/test_search_gates.py
git commit -m "feat: add anti-overfit search and hard gates"
```

### Task 8: Ten-Coin Runner and Reproducible Result Artifacts

**Files:**
- Create: `research/cloud_10coin_backtest/run.py`
- Create: `research/cloud_10coin_backtest/reporting.py`
- Create: `research/cloud_10coin_backtest/results/.gitkeep`
- Create: `research/cloud_10coin_backtest/tests/test_run_manifest.py`

**Interfaces:**
- `python -m research.cloud_10coin_backtest.run --start 2024-01-01 --end YYYY-MM-DD`
- Outputs: `run_manifest.json`, `data_audit.json`, `profiles.json`, `coin_summary.csv`, `trades/<symbol>.csv`, `report.md`.

- [ ] **Step 1: Write RED manifest test**

```python
def test_manifest_records_source_and_research_gates(tmp_path):
    manifest = build_manifest(tmp_path, source_sha="abc123")
    assert manifest["venue"] == "Binance"
    assert manifest["instrument"] == "USD-M perpetual"
    assert manifest["target_rr"] == 2.0
    assert manifest["min_completed_trades"] == 100
    assert manifest["target_wr"] == 0.80
```

- [ ] **Step 2: Run RED**

Run: `pytest research/cloud_10coin_backtest/tests/test_run_manifest.py -q`
Expected: FAIL.

- [ ] **Step 3: Implement orchestrator**

For each symbol: load/audit -> feature build -> search/freeze -> validation/holdout -> report. Persist rejected material false positives with rejection reason.

- [ ] **Step 4: Run smoke test on a short date range**

Run: `python -m research.cloud_10coin_backtest.run --symbols BTCUSDT,SOLUSDT --start 2026-08-01 --end 2026-08-07 --smoke`
Expected: exits 0, writes all manifest/report files, labels research target as NOT_EVALUATED when sample <100.

- [ ] **Step 5: Run unit suite and commit**

Run: `pytest research/cloud_10coin_backtest/tests -q`
Expected: PASS.

```bash
git add research/cloud_10coin_backtest
git commit -m "feat: add reproducible 10-coin research runner"
```

### Task 9: Railway Isolation Configuration and Deployment

**Files:**
- Create: `research/cloud_10coin_backtest/railway.toml`
- Modify: `research/cloud_10coin_backtest/README.md`

**Interfaces:**
- Railway service: `crypto-backtest-job` in project `github-brain-zero-local-runtime`.
- Root directory: `/research/cloud_10coin_backtest`.
- Start command: `python run.py` or package-equivalent verified in Railpack.
- No domain, no variables containing credentials, restart policy NEVER.

- [ ] **Step 1: Add Railpack/Railway batch configuration**

`railway.toml` must specify the one-off start command and no HTTP healthcheck requirement.

- [ ] **Step 2: Create isolated Railway service from the approved branch**

Use repo `hanlinh227-ship-it/trading-api`, branch `research/cloud-10coin-80wr-100trades-20260913`, service name `crypto-backtest-job`, root directory `/research/cloud_10coin_backtest`.

- [ ] **Step 3: Configure restart policy NEVER and verify isolation**

Verify no domain, no shared volume, and no secret variables. Record service ID and environment ID in the run report.

- [ ] **Step 4: Deploy and inspect build/runtime logs**

Expected: dependency install succeeds, smoke/full job starts, public Binance requests succeed, no private endpoint calls appear.

- [ ] **Step 5: Verify production gateway unchanged**

Compare `crypto-research-gateway-prod` deployment ID/source SHA before and after the backtest deployment; they must match.

### Task 10: Full Historical Research Run and Final Verification

**Files:**
- Runtime generated only under `research/cloud_10coin_backtest/results/` and Railway logs; do not commit large datasets/trade CSVs.

**Interfaces:**
- Full run covers all ten symbols and starts at 2024-01-01, extending earlier for frozen high-WR profiles that need additional trade count.

- [ ] **Step 1: Execute full ten-coin run**

Run the isolated Railway service with all ten symbols and the latest fully closed date.

- [ ] **Step 2: Verify per-coin gates**

For each symbol check `completed_trades >= 100`, `rr2_wr >= 0.80`, post-cost expectancy > 0, validation/holdout status, and profile hash freeze evidence.

- [ ] **Step 3: Re-run unit suite and deterministic smoke from exact deployed source SHA**

Expected: all package tests pass and smoke artifacts match schema.

- [ ] **Step 4: Run repository validators applicable to the research change**

Run the current Brain validation entrypoint from repository authority and record results. No production deployment is performed by this task.

- [ ] **Step 5: Produce final report without fabricating target attainment**

If all ten pass, report 10/10 with exact counts and WR. If any fail, report the actual PASS count, best locked profile per failed coin, exact bottleneck, and the next evidence layer required; never replace failure with selected 100 historical winners.

- [ ] **Step 6: Commit only source/test/docs changes**

```bash
git status --short
git add research/cloud_10coin_backtest docs/superpowers/plans/2026-09-13-cloud-10coin-backtest-implementation.md
git commit -m "research: implement isolated cloud 10-coin backtest engine"
```
