# G7 Regime Router Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build and activate a research-only G7 regime-routed, route-specific meta-label backtest that can abstain unless an exact frozen route has historically qualified for the >=80% RR1:2 research target.

**Architecture:** Extend G6 rather than replacing the engine. Add a causal regime classifier, route structural candidates by `(regime, family, side)`, select one DEV-only geometry per route, train bounded route-specific Random Forest models with expanding walk-forward OOF predictions, select thresholds by stability-first metrics, freeze all route specs before validation/holdout, and expose a research analysis qualification contract. Keep production BTC-only authority untouched.

**Tech Stack:** Python 3.13, pandas, NumPy, scikit-learn RandomForestClassifier, pytest, GitHub Actions.

**Spec:** `docs/superpowers/specs/2026-09-13-g7-regime-router-design.md`

## Global Constraints
- Research-only; do not modify production trading authority, credentials, runtime switches, or live order execution.
- Hard research target per coin: >=100 completed evaluation trades, observed RR 1:2 WR >=80%, positive post-cost expectancy, stable chronological validation/holdout.
- No future-performance guarantee and no fabricated "80% probability" from model score.
- DEV-only selection; validation/holdout untouched until route specs are frozen.
- Same-bar ambiguity remains pessimistic; actual OOS evaluation remains sequential and non-overlapping.
- No martingale, grid rescue, stop widening, look-ahead, or post-outcome selection.

---

### Task 1: Causal G7 regime classifier

**Files:**
- Create: `research/cloud_10coin_backtest/optimize/regime_g7.py`
- Create: `research/cloud_10coin_backtest/tests/test_g7_regime.py`

**Interfaces:**
- Produces: `classify_regimes(features: pd.DataFrame) -> pd.Series`
- Produces constants: `G7_REGIMES`, including `TREND_UP`, `TREND_DOWN`, `RANGE`, `COMPRESSION`, `EXPANSION`, `SHOCK`.

- [ ] **Step 1: Write failing causal classification tests**

```python
import numpy as np
import pandas as pd
from optimize.regime_g7 import classify_regimes


def _frame(n=80):
    return pd.DataFrame({
        "h1_trend": np.zeros(n),
        "h4_trend": np.zeros(n),
        "trend_strength": np.full(n, 0.2),
        "vol_regime": np.ones(n),
        "body_atr": np.full(n, 0.2),
        "rel_volume": np.ones(n),
        "z_ema20": np.zeros(n),
        "close": np.linspace(100, 101, n),
        "atr14": np.ones(n),
    })


def test_aligned_trend_classifies_trend_up():
    f = _frame()
    f.loc[30, ["h1_trend", "h4_trend", "trend_strength"]] = [1, 1, 1.2]
    assert classify_regimes(f).iloc[30] == "TREND_UP"


def test_shock_overrides_trend():
    f = _frame()
    f.loc[30, ["h1_trend", "h4_trend", "trend_strength", "body_atr", "rel_volume", "vol_regime"]] = [1, 1, 1.5, 3.2, 3.5, 2.2]
    assert classify_regimes(f).iloc[30] == "SHOCK"


def test_future_row_change_does_not_change_prior_regime():
    f = _frame()
    before = classify_regimes(f).iloc[25]
    f.loc[70, ["body_atr", "rel_volume", "vol_regime"]] = [9, 9, 9]
    assert classify_regimes(f).iloc[25] == before
```

- [ ] **Step 2: Run RED**

Run: `cd research/cloud_10coin_backtest && PYTHONPATH=. pytest tests/test_g7_regime.py -q`
Expected: FAIL because `optimize.regime_g7` does not exist.

- [ ] **Step 3: Implement minimal deterministic regime classifier**

Rules, in precedence order:
- `SHOCK`: `body_atr >= 2.5 and rel_volume >= 2.0 and vol_regime >= 1.6`
- `COMPRESSION`: `vol_regime <= 0.75 and body_atr <= 0.55`
- `EXPANSION`: `vol_regime >= 1.35 and body_atr >= 0.75`
- `TREND_UP`: `h1_trend > 0 and h4_trend > 0 and trend_strength >= 0.70`
- `TREND_DOWN`: symmetric
- otherwise `RANGE`

Use only same-row causal feature values and numeric coercion; missing values fall back conservatively to `RANGE` unless the required shock fields are present.

- [ ] **Step 4: Run GREEN + regression**

Run:
`cd research/cloud_10coin_backtest && PYTHONPATH=. pytest tests/test_g7_regime.py -q && PYTHONPATH=. pytest tests -q`
Expected: PASS.

- [ ] **Step 5: Commit**

Commit message: `feat: add causal G7 regime classifier`

---

### Task 2: Regime/family router and one-event candidate contract

**Files:**
- Create: `research/cloud_10coin_backtest/optimize/router_g7.py`
- Create: `research/cloud_10coin_backtest/tests/test_g7_router.py`
- Reuse: `optimize/search_g6.py::build_setup_candidates`

**Interfaces:**
- Consumes: `classify_regimes(features)`
- Produces: `route_key(regime: str, candidate: OrderCandidate) -> tuple[str, str, str] | None`
- Produces: `build_routed_candidates(features, roundtrip_cost_bps) -> dict[tuple[str,str,str], list[OrderCandidate]]`
- Produces: `geometry_key(candidate, features) -> tuple[float, int]`

- [ ] **Step 1: Write failing router tests**

Tests must verify:
- TREND_UP rejects SHORT trend/breakout candidates.
- RANGE admits sweep/exhaustion on both sides.
- SHOCK admits nothing.
- same event may have DEV geometry variants, but route identity excludes geometry.
- changing a future row does not alter an earlier route.

- [ ] **Step 2: Run RED**

Run: `PYTHONPATH=. pytest tests/test_g7_router.py -q`
Expected: import failure.

- [ ] **Step 3: Implement route table**

Allowed mapping:
```python
ALLOWED = {
    "TREND_UP": {("setup_trend", "LONG"), ("setup_breakout", "LONG"), ("setup_compression", "LONG")},
    "TREND_DOWN": {("setup_trend", "SHORT"), ("setup_breakout", "SHORT"), ("setup_compression", "SHORT")},
    "RANGE": {("setup_sweep", "LONG"), ("setup_sweep", "SHORT"), ("setup_exhaustion", "LONG"), ("setup_exhaustion", "SHORT")},
    "COMPRESSION": {("setup_breakout", "LONG"), ("setup_breakout", "SHORT"), ("setup_compression", "LONG"), ("setup_compression", "SHORT")},
    "EXPANSION": {("setup_trend", "LONG"), ("setup_trend", "SHORT"), ("setup_breakout", "LONG"), ("setup_breakout", "SHORT")},
    "SHOCK": set(),
}
```
For `EXPANSION`, additionally require candidate side to agree with H1 and H4 trend at the signal bar; otherwise reject.

- [ ] **Step 4: GREEN + regression**

Run router tests and full tests.

- [ ] **Step 5: Commit**

Commit message: `feat: route G7 setups by market regime`

---

### Task 3: Stability-first route selection and target qualification

**Files:**
- Create: `research/cloud_10coin_backtest/optimize/stability_g7.py`
- Create: `research/cloud_10coin_backtest/tests/test_g7_stability.py`

**Interfaces:**
- Produces: `wilson_lower(wins: int, n: int, z: float = 1.96) -> float`
- Produces: `select_stable_threshold(rows: pd.DataFrame, thresholds, min_trades: int, min_fold_trades: int) -> dict`
- Produces: `route_is_target_qualified(choice: dict, target_wr: float = 0.80) -> bool`

- [ ] **Step 1: RED tests**

Verify:
- a 90/90/35/90% four-fold profile loses to a 74/75/76/75% profile when ranking by minimum-fold stability even if its mean is higher;
- threshold choice returns overall WR, expectancy, minimum fold WR, Wilson lower bound, completed trades and qualified flag;
- `qualified` can only be true when overall WR >=0.80, expectancy >0, minimum-fold floor is met and trade breadth is met.

- [ ] **Step 2: Implement ranking**

Rank candidate thresholds lexicographically by:
`(min_fold_wr, wilson_lower, expectancy_r, completed_trades)`.
Do not optimize directly on validation/holdout.

Initial route qualification floors:
- `completed_trades >= 40` OOF for a route,
- `rr2_wr >= 0.80`,
- `expectancy_r > 0`,
- `min_fold_wr >= 0.65` among folds with at least `min_fold_trades`,
- `wilson_lower >= 0.60`.
These route-level floors do not weaken the final coin hard gate.

- [ ] **Step 3: GREEN + regression**

Run tests and full suite.

- [ ] **Step 4: Commit**

Commit message: `feat: add stability-first G7 threshold gate`

---

### Task 4: Route-specific walk-forward model with locked geometry

**Files:**
- Create: `research/cloud_10coin_backtest/optimize/search_g7.py`
- Create: `research/cloud_10coin_backtest/tests/test_g7_search.py`
- Reuse: `optimize/nonlinear_model.py`, `optimize/search_g6.py`, `optimize/stability.py`, `optimize/search.py`

**Interfaces:**
- Produces: `search_coin_g7(symbol: str, features: pd.DataFrame, config) -> CoinResearchResult`
- Internal route spec fields:
  - `regime`, `family`, `side`
  - `risk_atr`, `hold_bars`
  - `threshold`
  - `model_config`
  - `oof_completed_trades`, `oof_rr2_wr`, `oof_expectancy_r`, `min_fold_wr`, `wilson_lower`, `qualified`
- Locked profile family: `regime_router_g7_forest`

- [ ] **Step 1: RED contract tests**

Tests must verify:
- validation/holdout rows are not accepted by fitting helpers;
- final profile contains one geometry per route;
- OOS selection emits at most one candidate per `(signal_index, route_key)` and then one best candidate per signal across routes;
- unqualified routes are omitted from `QUALIFIED_SIGNAL` eligibility but may be evaluated diagnostically;
- identical seed/data produces identical profile hash.

- [ ] **Step 2: Implement DEV fold datasets**

For each chronological DEV fold:
1. build routed structural candidates;
2. label independently with existing conservative `simulate_trade` semantics;
3. attach route key, geometry key and fold id;
4. build G6 candidate feature vectors only for kept candidates.

- [ ] **Step 3: Implement geometry selection**

For each OOF step and route, choose geometry using prior folds only. Geometry ranking uses stable-threshold metrics from prior-fold candidate labels, not current fold outcomes. Final geometry is selected from all DEV evidence only after OOF model/config selection.

- [ ] **Step 4: Implement route-specific forest**

Bounded model grid:
```python
MODEL_GRID = (
    {"n_estimators": 120, "max_depth": 4, "min_samples_leaf": 18, "max_features": 0.7, "random_state": 71},
    {"n_estimators": 120, "max_depth": 6, "min_samples_leaf": 32, "max_features": 0.7, "random_state": 71},
)
```
Final fit uses at least 240 trees with the chosen depth/leaf settings. Train only when both classes exist and prior-fold route labels >=80; otherwise abstain from model fitting for that route/fold.

- [ ] **Step 5: Implement frozen OOS evaluation**

For validation and holdout:
- rebuild routed candidates causally;
- keep only the route's locked geometry;
- score with route-specific frozen model;
- require `p >= threshold`;
- dedupe same-signal candidates by highest score;
- evaluate using `_simulate_fast` sequential conservative engine.

Calculate DEV, validation, holdout and combined evaluation metrics. Final PASS uses existing `passes_g2_gate` without lowering target/min trades.

- [ ] **Step 6: GREEN + full regression**

Run targeted tests then all tests.

- [ ] **Step 7: Commit**

Commit message: `feat: add G7 route-specific walk-forward search`

---

### Task 5: Research coin-analysis qualification contract

**Files:**
- Create: `research/cloud_10coin_backtest/analysis/g7_decision.py`
- Create: `research/cloud_10coin_backtest/tests/test_g7_decision.py`

**Interfaces:**
- Produces: `classify_signal_decision(profile, route_spec, probability, data_ok=True) -> str`
- Output enum strings: `QUALIFIED_SIGNAL`, `NO_TRADE_UNQUALIFIED`, `NO_TRADE_REGIME`, `NO_TRADE_CONFIDENCE`, `DATA_FAIL`.

- [ ] **Step 1: RED tests**

Verify:
- an unqualified route can never emit `QUALIFIED_SIGNAL` even with probability 0.99;
- a qualified route below frozen threshold returns `NO_TRADE_CONFIDENCE`;
- `DATA_FAIL` overrides everything;
- no function returns a textual future win-rate guarantee.

- [ ] **Step 2: Implement fail-closed decision helper**

This helper is research-only and does not place orders or mutate accounts. It only provides the decision semantics future coin-analysis adapters may consume after promotion.

- [ ] **Step 3: GREEN + regression**

- [ ] **Step 4: Commit**

Commit message: `feat: add G7 research qualification decision contract`

---

### Task 6: Runner and automatic G7 CI activation

**Files:**
- Modify: `research/cloud_10coin_backtest/run.py`
- Create: `.github/workflows/g7-research-ci.yml`
- Create or modify tests for runner generation parsing if an existing runner test file is present.

**Interfaces:**
- `run.py --generation g7`
- Workflow branch: `research/cloud-10coin-g7-regime-router-20260913`

- [ ] **Step 1: RED runner test**

Verify parser accepts `g7` and dispatches `search_coin_g7`.

- [ ] **Step 2: Implement runner integration**

Import `search_coin_g7`; choose it when generation is `g7`; add `g7` to argparse choices.

- [ ] **Step 3: Add automatic workflow**

Jobs:
1. `test`: G7 targeted tests + full regression;
2. `smoke`: BTCUSDT 2025-01-01 through 2026-08-31 using `--generation g7 --smoke`;
3. `backtest`: matrix of locked ten coins, 2024-01-01 through 2026-08-31, max-parallel 5;
4. `aggregate`: read each artifact's `coin_summary.csv`, not the obsolete JSON path, and emit `g7-aggregate.json` with exact metrics and `all_pass`.

Use branch concurrency with `cancel-in-progress: true` for research runs only.

- [ ] **Step 4: GREEN local/unit regression**

Run all tests before push-triggered CI.

- [ ] **Step 5: Commit**

Commit message: `ci: activate automatic G7 research pipeline`

---

### Task 7: Verification and research result gate

**Files:**
- No source change unless verification exposes a bug.
- Inspect GitHub Actions artifacts/logs for the exact G7 source SHA.

- [ ] **Step 1: Verify unit and regression job GREEN**
- [ ] **Step 2: Verify BTC smoke completed and inspect metrics**
- [ ] **Step 3: Verify ten-coin matrix produced all ten artifacts**
- [ ] **Step 4: Verify aggregate reads exact CSV outputs and reports no false `MISSING` rows**
- [ ] **Step 5: Compare G7 against G6 on frequency, RR2 WR, expectancy and stability**
- [ ] **Step 6: Report research success only if all ten coins satisfy hard target; otherwise keep G7 in research and identify the next evidence/data bottleneck**

