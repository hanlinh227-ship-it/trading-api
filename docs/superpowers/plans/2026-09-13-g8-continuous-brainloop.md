# G8 Continuous BrainLoop Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a bounded, continuously recurring G8 research loop that searches for stronger per-coin profiles, promotes only statistically stronger challengers, remembers every trial, and exposes the latest validated research champion to future DEEP trading-analysis requests without changing production execution authority.

**Architecture:** G8 is additive to G7. Research code lives under `research/cloud_10coin_backtest/g8/`; one generation is finite and resumable. A GitHub Actions workflow eventually runs hourly from the repository default branch, while mutable checkpoint/ledger/champion evidence is written to a dedicated `research/g8-brainloop-state` branch so hourly research does not create main-branch commits or trigger production deployment workflows.

**Tech Stack:** Python 3.13, NumPy 2.x, pandas 2.x, scikit-learn 1.6+, pytest 8.x, existing G7 routing/model code, existing conservative execution engine, GitHub Actions.

**Spec:** `docs/superpowers/specs/2026-09-13-g8-continuous-brainloop-design.md`

## Global Constraints

- Production trading authority remains `BYBIT-BTC-STATEFLOW-2.1`, BTCUSDT Linear Perpetual on Bybit only.
- G8 is research-only and MUST NOT place/cancel/amend/close orders or mutate leverage/account/wallet/live runtime switches.
- Locked research universe is BTCUSDT, ETHUSDT, BNBUSDT, XRPUSDT, SOLUSDT, TRXUSDT, DOGEUSDT, LINKUSDT, ADAUSDT, XLMUSDT.
- Certification target per coin remains >=100 completed OOS trades, RR 1:2 WR >=0.80, positive post-cost expectancy, stable validation/CPCV, no leakage, no post-outcome selection.
- Same-bar ambiguity stays pessimistic; martingale, grid rescue, add-to-loser, and stop widening stay forbidden.
- Current Trading project authority always outranks G8 research evidence.
- Repeated adaptive promotion from an exhausted evidence epoch is forbidden.
- One workflow generation is bounded. Continuous research means repeated scheduled generations, never an infinite process inside one runner.
- A scheduled GitHub Actions workflow only becomes hourly-active after the workflow file is present on the default branch. Before that, G8 branch verification uses manual dispatch.
- Mutable G8 state MUST NOT be auto-committed to `main`; main pushes can trigger production Skill Gateway deployment.

---

## File Map

### New research package
- `research/cloud_10coin_backtest/g8/__init__.py`
- `research/cloud_10coin_backtest/g8/state.py`
- `research/cloud_10coin_backtest/g8/candidate.py`
- `research/cloud_10coin_backtest/g8/validation.py`
- `research/cloud_10coin_backtest/g8/fitness.py`
- `research/cloud_10coin_backtest/g8/ledger.py`
- `research/cloud_10coin_backtest/g8/registry.py`
- `research/cloud_10coin_backtest/g8/evaluator.py`
- `research/cloud_10coin_backtest/g8/loop.py`
- `research/cloud_10coin_backtest/run_g8_loop.py`

### Brain evidence
- `AI_SKILL_LIBRARY/v4/tools/validate_g8_champion_snapshot.py`
- Runtime-generated on state branch: `AI_SKILL_LIBRARY/v4/evergreen/candidate_state/g8_trading_champions.json`

### CI
- `.github/workflows/g8-brainloop.yml`

### Tests
- `research/cloud_10coin_backtest/tests/test_g8_state.py`
- `research/cloud_10coin_backtest/tests/test_g8_candidate.py`
- `research/cloud_10coin_backtest/tests/test_g8_validation.py`
- `research/cloud_10coin_backtest/tests/test_g8_fitness.py`
- `research/cloud_10coin_backtest/tests/test_g8_ledger_registry.py`
- `research/cloud_10coin_backtest/tests/test_g8_evaluator.py`
- `research/cloud_10coin_backtest/tests/test_g8_loop.py`
- `AI_SKILL_LIBRARY/tests/test_g8_champion_snapshot.py`

---

### Task 1: Loop State and Evidence Epoch Budget

**Files:**
- Create: `research/cloud_10coin_backtest/g8/__init__.py`
- Create: `research/cloud_10coin_backtest/g8/state.py`
- Test: `research/cloud_10coin_backtest/tests/test_g8_state.py`

**Interfaces:**
- `EvidenceEpoch(epoch_id, data_cutoff, max_adaptive_trials, consumed_trials)`
- `LoopState.new(symbols, source_sha, data_cutoff, max_adaptive_trials)`
- `load_loop_state(path) -> LoopState`
- `save_loop_state(path, state) -> None`
- `can_promote(state, symbol) -> bool`
- `consume_promotion_trial(state, symbol) -> None`

- [ ] **Step 1: Write RED tests**

```python
from pathlib import Path
from g8.state import LoopState, can_promote, consume_promotion_trial, load_loop_state, save_loop_state


def test_loop_state_round_trip(tmp_path: Path):
    state = LoopState.new(
        symbols=["BTCUSDT", "ETHUSDT"],
        source_sha="abc123",
        data_cutoff="2026-08-31",
        max_adaptive_trials=25,
    )
    path = tmp_path / "checkpoint.json"
    save_loop_state(path, state)
    assert load_loop_state(path).to_dict() == state.to_dict()


def test_epoch_budget_blocks_promotion_when_exhausted():
    state = LoopState.new(
        symbols=["BTCUSDT"],
        source_sha="abc123",
        data_cutoff="2026-08-31",
        max_adaptive_trials=1,
    )
    assert can_promote(state, "BTCUSDT") is True
    consume_promotion_trial(state, "BTCUSDT")
    assert can_promote(state, "BTCUSDT") is False
```

- [ ] **Step 2: Run RED**

`cd research/cloud_10coin_backtest && PYTHONPATH=. pytest tests/test_g8_state.py -q`

Expected: `ModuleNotFoundError: g8.state`.

- [ ] **Step 3: Implement minimal dataclasses and atomic JSON persistence**

`save_loop_state()` writes `<name>.tmp`, flushes/fsyncs, then replaces the destination. Persist schema version, generation, exact source SHA, symbols, epoch, and previous snapshot hash.

- [ ] **Step 4: Verify GREEN**

`cd research/cloud_10coin_backtest && PYTHONPATH=. pytest tests/test_g8_state.py tests/test_config.py -q`

- [ ] **Step 5: Commit**

```bash
git add research/cloud_10coin_backtest/g8 research/cloud_10coin_backtest/tests/test_g8_state.py
git commit -m "feat: add G8 loop state and evidence epochs"
```

---

### Task 2: Deterministic Candidate Factory

**Files:**
- Create: `research/cloud_10coin_backtest/g8/candidate.py`
- Test: `research/cloud_10coin_backtest/tests/test_g8_candidate.py`

**Interfaces:**
- `CandidateSpec`
- `CandidateSpec.with_updates(**changes) -> CandidateSpec`
- `candidate_hash(spec) -> str`
- `seed_baseline_candidates(symbol) -> list[CandidateSpec]`
- `mutate_candidate(parent, seed, budget) -> list[CandidateSpec]`

- [ ] **Step 1: Write RED tests**

```python
from g8.candidate import candidate_hash, mutate_candidate, seed_baseline_candidates


def test_same_seed_produces_same_mutation_sequence():
    parent = seed_baseline_candidates("BTCUSDT")[0]
    left = mutate_candidate(parent, seed=77, budget=6)
    right = mutate_candidate(parent, seed=77, budget=6)
    assert [candidate_hash(x) for x in left] == [candidate_hash(x) for x in right]


def test_geometry_change_changes_candidate_hash():
    parent = seed_baseline_candidates("BTCUSDT")[0]
    child = parent.with_updates(risk_atr=1.6)
    assert candidate_hash(parent) != candidate_hash(child)


def test_mutation_budget_is_hard_cap():
    parent = seed_baseline_candidates("SOLUSDT")[0]
    assert len(mutate_candidate(parent, seed=11, budget=3)) <= 3
```

- [ ] **Step 2: Run RED**

`cd research/cloud_10coin_backtest && PYTHONPATH=. pytest tests/test_g8_candidate.py -q`

- [ ] **Step 3: Implement immutable candidate vocabulary**

Use a frozen dataclass with symbol, regime, family, side, feature pack, model family, sorted model params, calibration mode, threshold, risk ATR, hold bars, and parent hash. Initial model families are exactly `logistic` and `random_forest`; no new dependency is introduced in this task. Each mutation changes one typed dimension and identical hashes are removed.

- [ ] **Step 4: Verify GREEN + G7 compatibility**

`cd research/cloud_10coin_backtest && PYTHONPATH=. pytest tests/test_g8_candidate.py tests/test_g7_router.py tests/test_g5_nonlinear.py -q`

- [ ] **Step 5: Commit**

```bash
git add research/cloud_10coin_backtest/g8/candidate.py research/cloud_10coin_backtest/tests/test_g8_candidate.py
git commit -m "feat: add deterministic G8 candidate factory"
```

---

### Task 3: Purged Walk-Forward and CPCV Split Engine

**Files:**
- Create: `research/cloud_10coin_backtest/g8/validation.py`
- Test: `research/cloud_10coin_backtest/tests/test_g8_validation.py`

**Interfaces:**
- `TimeSplit(train_idx, test_idx, blocked_idx)`
- `purged_walk_forward(n, n_splits, purge_bars, embargo_bars) -> list[TimeSplit]`
- `cpcv_splits(n, n_groups, test_groups, purge_bars, embargo_bars) -> list[TimeSplit]`

- [ ] **Step 1: Write RED tests**

```python
from g8.validation import cpcv_splits, purged_walk_forward


def test_purged_walk_forward_removes_label_overlap():
    splits = purged_walk_forward(1000, n_splits=5, purge_bars=144, embargo_bars=12)
    assert len(splits) == 5
    for split in splits:
        assert set(split.train_idx).isdisjoint(split.test_idx)
        assert set(split.train_idx).isdisjoint(split.blocked_idx)


def test_cpcv_is_deterministic_and_embargoed():
    left = cpcv_splits(1200, n_groups=6, test_groups=2, purge_bars=72, embargo_bars=12)
    right = cpcv_splits(1200, n_groups=6, test_groups=2, purge_bars=72, embargo_bars=12)
    assert left == right
    for split in left:
        assert set(split.train_idx).isdisjoint(split.blocked_idx)
```

- [ ] **Step 2: Run RED**

`cd research/cloud_10coin_backtest && PYTHONPATH=. pytest tests/test_g8_validation.py -q`

- [ ] **Step 3: Implement index-only splitting**

Split creation may use only row index, group boundaries, purge horizon, and embargo horizon. It must never inspect label values, future returns, or model outcomes.

- [ ] **Step 4: Verify GREEN + existing stability regression**

`cd research/cloud_10coin_backtest && PYTHONPATH=. pytest tests/test_g8_validation.py tests/test_g3_stability_selection.py -q`

- [ ] **Step 5: Commit**

```bash
git add research/cloud_10coin_backtest/g8/validation.py research/cloud_10coin_backtest/tests/test_g8_validation.py
git commit -m "feat: add G8 purged and CPCV validation"
```

---

### Task 4: Fitness and Promotion Gate

**Files:**
- Create: `research/cloud_10coin_backtest/g8/fitness.py`
- Test: `research/cloud_10coin_backtest/tests/test_g8_fitness.py`

**Interfaces:**
- `TrialMetrics`
- `PromotionDecision(promote, reasons)`
- `fitness_key(metrics) -> tuple`
- `compare_for_promotion(incumbent, challenger, state, symbol) -> PromotionDecision`

- [ ] **Step 1: Write RED tests**

```python
from g8.fitness import TrialMetrics, compare_for_promotion, fitness_key
from g8.state import LoopState


def metrics(wr, worst, expectancy, pbo, trades=220):
    return TrialMetrics(
        trades=trades,
        min_required_trades=100,
        rr2_wr=wr,
        worst_fold_wr=worst,
        wilson_lower=max(0.0, wr - 0.08),
        expectancy_r=expectancy,
        cost_stress_expectancy_r=expectancy - 0.10,
        max_drawdown_r=8.0,
        pbo=pbo,
        leakage_ok=True,
        falsification_ok=True,
        provenance_complete=True,
    )


def test_stability_beats_spiky_high_mean_wr():
    stable = metrics(.76, .72, .95, .20)
    spiky = metrics(.84, .39, 1.02, .35)
    assert fitness_key(stable) > fitness_key(spiky)


def test_exhausted_epoch_blocks_better_challenger():
    state = LoopState.new(["BTCUSDT"], "abc", "2026-08-31", 0)
    decision = compare_for_promotion(None, metrics(.81, .76, 1.20, .10), state, "BTCUSDT")
    assert decision.promote is False
    assert "evidence-budget-exhausted" in decision.reasons


def test_failed_falsification_blocks_promotion():
    state = LoopState.new(["BTCUSDT"], "abc", "2026-08-31", 10)
    challenger = metrics(.83, .79, 1.30, .08)
    challenger = challenger.with_updates(falsification_ok=False)
    assert compare_for_promotion(None, challenger, state, "BTCUSDT").promote is False
```

- [ ] **Step 2: Run RED**

`cd research/cloud_10coin_backtest && PYTHONPATH=. pytest tests/test_g8_fitness.py -q`

- [ ] **Step 3: Implement lexicographic ranking**

Order: validation integrity, trade adequacy, worst-fold WR, Wilson lower bound, OOF RR2 WR, positive cost-stressed expectancy, raw expectancy, lower PBO, lower drawdown, trade coverage. Raw WR alone can never override a material worst-fold regression.

- [ ] **Step 4: Verify GREEN**

`cd research/cloud_10coin_backtest && PYTHONPATH=. pytest tests/test_g8_fitness.py -q`

- [ ] **Step 5: Commit**

```bash
git add research/cloud_10coin_backtest/g8/fitness.py research/cloud_10coin_backtest/tests/test_g8_fitness.py
git commit -m "feat: add G8 promotion fitness gate"
```

---

### Task 5: Trial Ledger and Atomic Champion Registry

**Files:**
- Create: `research/cloud_10coin_backtest/g8/ledger.py`
- Create: `research/cloud_10coin_backtest/g8/registry.py`
- Test: `research/cloud_10coin_backtest/tests/test_g8_ledger_registry.py`

**Interfaces:**
- `TrialRecord`
- `append_trial(path, record) -> None`
- `seen_candidate_hashes(path, symbol) -> set[str]`
- `ChampionRegistry.empty(symbols) -> ChampionRegistry`
- `promote_champion(registry, symbol, record) -> ChampionRegistry`
- `publish_snapshot(path, registry) -> str`

- [ ] **Step 1: Write RED tests**

```python
import json
from g8.ledger import TrialRecord, append_trial, seen_candidate_hashes
from g8.registry import ChampionRegistry, promote_champion, publish_snapshot


def test_ledger_is_append_only(tmp_path):
    path = tmp_path / "trials.jsonl"
    first = TrialRecord.synthetic(symbol="BTCUSDT", candidate_hash="hash-a")
    second = TrialRecord.synthetic(symbol="BTCUSDT", candidate_hash="hash-b")
    append_trial(path, first)
    prefix = path.read_text()
    append_trial(path, second)
    assert path.read_text().startswith(prefix)
    assert seen_candidate_hashes(path, "BTCUSDT") == {"hash-a", "hash-b"}


def test_registry_snapshot_is_valid_complete_json(tmp_path):
    record = TrialRecord.synthetic(symbol="BTCUSDT", candidate_hash="hash-a")
    registry = promote_champion(ChampionRegistry.empty(["BTCUSDT"]), "BTCUSDT", record)
    path = tmp_path / "champions.json"
    digest = publish_snapshot(path, registry)
    payload = json.loads(path.read_text())
    assert len(digest) == 64
    assert payload["symbols"]["BTCUSDT"]["research_champion_id"] == record.trial_id
```

- [ ] **Step 2: Run RED**

`cd research/cloud_10coin_backtest && PYTHONPATH=. pytest tests/test_g8_ledger_registry.py -q`

- [ ] **Step 3: Implement evidence-only memory**

`TrialRecord` stores trial/generation/parent IDs, symbol, deterministic seed, candidate hash, source SHA, data/evidence window IDs, OOF metrics, falsification result, promotion decision, and rejection reasons. It stores no hidden chain-of-thought. Registry publication uses temporary file + flush/fsync + atomic replace.

- [ ] **Step 4: Verify GREEN**

`cd research/cloud_10coin_backtest && PYTHONPATH=. pytest tests/test_g8_ledger_registry.py -q`

- [ ] **Step 5: Commit**

```bash
git add research/cloud_10coin_backtest/g8/ledger.py research/cloud_10coin_backtest/g8/registry.py research/cloud_10coin_backtest/tests/test_g8_ledger_registry.py
git commit -m "feat: add G8 trial ledger and champion registry"
```

---

### Task 6: Candidate Evaluator Using Existing G7 Semantics

**Files:**
- Create: `research/cloud_10coin_backtest/g8/evaluator.py`
- Test: `research/cloud_10coin_backtest/tests/test_g8_evaluator.py`

**Interfaces:**
- `evaluate_candidate(symbol, features, config, candidate, validation_plan) -> TrialMetrics`
- `run_falsification_suite(symbol, features, config, candidate, validation_plan) -> dict[str, float | bool]`

- [ ] **Step 1: Write RED tests with self-contained synthetic features**

```python
import numpy as np
import pandas as pd
from config import DEFAULT_CONFIG
from g8.candidate import seed_baseline_candidates
from g8.evaluator import evaluate_candidate
from g8.validation import purged_walk_forward


def feature_frame(n=900):
    close = 100.0 + np.linspace(0.0, 4.0, n)
    return pd.DataFrame({
        "open": close - 0.05, "high": close + 0.30, "low": close - 0.30, "close": close,
        "atr14": np.ones(n), "body_atr": np.full(n, .5), "close_loc": np.full(n, .75),
        "rel_volume": np.ones(n), "rel_trades": np.ones(n), "taker_buy_ratio": np.full(n, .55),
        "flow_delta": np.full(n, .1), "flow_ema12": np.full(n, .1), "vol_regime": np.ones(n),
        "z_ema20": np.zeros(n), "h1_trend": np.ones(n), "h4_trend": np.ones(n),
        "trend_strength": np.full(n, .7), "prior_high_12": close - .05, "prior_low_12": close - 2.0,
        "prior_high_24": close + 1.0, "prior_low_24": close - 3.0,
        "recent_sweep_low_3": np.zeros(n), "recent_sweep_high_3": np.zeros(n),
        "h1_ma20": close - .2, "h4_ma20": close - .4,
    })


def test_evaluator_returns_only_oof_evidence():
    candidate = seed_baseline_candidates("BTCUSDT")[0]
    plan = purged_walk_forward(900, n_splits=5, purge_bars=144, embargo_bars=12)
    result = evaluate_candidate("BTCUSDT", feature_frame(), DEFAULT_CONFIG, candidate, plan)
    assert result.provenance_complete is True
    assert result.in_sample_score is None


def test_future_rows_do_not_change_earlier_fold_result():
    candidate = seed_baseline_candidates("BTCUSDT")[0]
    left = feature_frame()
    right = left.copy()
    right.loc[800:, "close"] = right.loc[800:, "close"] + 50.0
    plan = purged_walk_forward(900, n_splits=5, purge_bars=144, embargo_bars=12)
    a = evaluate_candidate("BTCUSDT", left, DEFAULT_CONFIG, candidate, plan)
    b = evaluate_candidate("BTCUSDT", right, DEFAULT_CONFIG, candidate, plan)
    assert a.fold_metrics[:3] == b.fold_metrics[:3]
```

- [ ] **Step 2: Run RED**

`cd research/cloud_10coin_backtest && PYTHONPATH=. pytest tests/test_g8_evaluator.py -q`

- [ ] **Step 3: Implement evaluator by composition, not by rewriting execution**

Reuse `optimize.router_g7.build_routed_candidates`, `geometry_key`, `optimize.search_g6.candidate_feature_matrix`, `label_setup_candidates`, existing logistic/RF fitters, `optimize.search._simulate_fast`, `_cost_bps`, and `engine.metrics.summarize_outcomes`. Fit labels/models/calibration only inside training indexes. Score test indexes only after the fold is frozen. Cost stress uses deterministic multipliers of the configured round-trip cost. Falsification includes deterministic label shuffle and causal time-shift placebo.

- [ ] **Step 4: Verify GREEN + execution regressions**

`cd research/cloud_10coin_backtest && PYTHONPATH=. pytest tests/test_g8_evaluator.py tests/test_execution.py tests/test_g7_search.py -q`

- [ ] **Step 5: Commit**

```bash
git add research/cloud_10coin_backtest/g8/evaluator.py research/cloud_10coin_backtest/tests/test_g8_evaluator.py
git commit -m "feat: add G8 purged candidate evaluator"
```

---

### Task 7: Bounded Generation Loop and CLI

**Files:**
- Create: `research/cloud_10coin_backtest/g8/loop.py`
- Create: `research/cloud_10coin_backtest/run_g8_loop.py`
- Test: `research/cloud_10coin_backtest/tests/test_g8_loop.py`

**Interfaces:**
- `run_generation(symbols, start, end, state_dir, results_dir, candidate_budget, source_sha, feature_provider=None) -> GenerationResult`

- [ ] **Step 1: Write RED boundedness/resume tests**

```python
from pathlib import Path
from g8.loop import run_generation


def tiny_provider(symbol, start, end):
    from tests.test_g8_evaluator import feature_frame
    return feature_frame(900), {"audit": {"ok": True}}


def test_generation_honors_candidate_budget(tmp_path: Path):
    result = run_generation(
        symbols=["BTCUSDT"], start="2025-01-01", end="2025-03-01",
        state_dir=tmp_path / "state", results_dir=tmp_path / "results",
        candidate_budget=3, source_sha="abc123", feature_provider=tiny_provider,
    )
    assert result.trials_attempted["BTCUSDT"] <= 3


def test_next_generation_resumes_checkpoint(tmp_path: Path):
    kwargs = dict(
        symbols=["BTCUSDT"], start="2025-01-01", end="2025-03-01",
        state_dir=tmp_path / "state", results_dir=tmp_path / "results",
        candidate_budget=1, source_sha="abc123", feature_provider=tiny_provider,
    )
    first = run_generation(**kwargs)
    second = run_generation(**kwargs)
    assert second.generation == first.generation + 1
    assert second.previous_snapshot_hash == first.snapshot_hash
```

- [ ] **Step 2: Run RED**

`cd research/cloud_10coin_backtest && PYTHONPATH=. pytest tests/test_g8_loop.py -q`

- [ ] **Step 3: Implement one bounded generation**

For each symbol: load incumbent, seed from incumbent or G7 baseline, skip seen hashes, evaluate at most the budget, append every trial, consume valid adaptive-comparison budget, promote only through `compare_for_promotion`, and preserve the previous verified snapshot on failure. A generation summary reports actual improvements and certification count without relabeling research-only champions as certified.

- [ ] **Step 4: Verify CLI on a short real-data smoke**

```bash
cd research/cloud_10coin_backtest
PYTHONPATH=. python run_g8_loop.py \
  --symbols BTCUSDT \
  --start 2025-01-01 \
  --end 2025-02-01 \
  --candidate-budget 1 \
  --state-dir /tmp/g8-state \
  --results-dir /tmp/g8-results \
  --source-sha local-smoke
```

Expected: checkpoint JSON, JSONL ledger, champion registry, generation summary, clean exit.

- [ ] **Step 5: Run full research regression**

`cd research/cloud_10coin_backtest && PYTHONPATH=. pytest tests -q`

- [ ] **Step 6: Commit**

```bash
git add research/cloud_10coin_backtest/g8/loop.py research/cloud_10coin_backtest/run_g8_loop.py research/cloud_10coin_backtest/tests/test_g8_loop.py
git commit -m "feat: add bounded G8 generation loop"
```

---

### Task 8: Brain Research-Evidence Snapshot Validator

**Files:**
- Create: `AI_SKILL_LIBRARY/v4/tools/validate_g8_champion_snapshot.py`
- Create: `AI_SKILL_LIBRARY/tests/test_g8_champion_snapshot.py`
- Modify: `research/cloud_10coin_backtest/g8/registry.py`

**Interfaces:**
- `build_brain_snapshot(registry, source_sha, data_cutoff) -> dict`
- `validate_snapshot(payload) -> list[str]`

- [ ] **Step 1: Write RED authority tests**

```python
from AI_SKILL_LIBRARY.v4.tools.validate_g8_champion_snapshot import validate_snapshot


def valid_snapshot():
    return {
        "schema_version": 1,
        "kind": "g8_trading_research_evidence",
        "research_only": True,
        "authority": {"execution": "none", "production_strategy": "BYBIT-BTC-STATEFLOW-2.1"},
        "source_sha": "abc123",
        "data_cutoff": "2026-08-31",
        "snapshot_hash": "0" * 64,
        "symbols": {
            "BTCUSDT": {
                "status": "RESEARCH_ONLY",
                "research_champion_id": "trial-1",
                "certified_champion_id": None,
                "production_execution_authority": False,
            }
        },
    }


def test_snapshot_cannot_grant_execution_authority():
    payload = valid_snapshot()
    payload["authority"]["execution"] = "orders"
    assert "execution-authority-forbidden" in validate_snapshot(payload)


def test_non_btc_certification_still_has_zero_execution_authority():
    payload = valid_snapshot()
    payload["symbols"] = {
        "SOLUSDT": {
            "status": "CERTIFIED_RESEARCH",
            "research_champion_id": "trial-2",
            "certified_champion_id": "trial-2",
            "production_execution_authority": False,
        }
    }
    assert "production-execution-authority-forbidden" not in validate_snapshot(payload)
```

- [ ] **Step 2: Run RED**

`PYTHONPATH=. pytest AI_SKILL_LIBRARY/tests/test_g8_champion_snapshot.py -q`

- [ ] **Step 3: Implement compact research snapshot + validator**

The generated snapshot contains one row per research symbol with research/certified champion IDs, generation, profile hash, source SHA, data cutoff, OOF metrics, certification metrics, feature packs, supported regimes/families/sides, calibration metadata, and status `RESEARCH_ONLY`, `CERTIFIED_RESEARCH`, or `QUARANTINED`. It never contains credentials, order endpoints, live switches, or execution permission. Snapshot hash is calculated over canonical JSON with `snapshot_hash` temporarily omitted.

- [ ] **Step 4: Verify Brain tests and canonical validator**

```bash
PYTHONPATH=. pytest AI_SKILL_LIBRARY/tests/test_g8_champion_snapshot.py -q
python AI_SKILL_LIBRARY/v4/tools/ci_validate.py --source-sha $(git rev-parse HEAD)
```

- [ ] **Step 5: Commit**

```bash
git add AI_SKILL_LIBRARY/v4/tools/validate_g8_champion_snapshot.py AI_SKILL_LIBRARY/tests/test_g8_champion_snapshot.py research/cloud_10coin_backtest/g8/registry.py
git commit -m "feat: validate G8 Brain research evidence"
```

---

### Task 9: State Branch + GitHub Actions Continuous Loop

**Files:**
- Create: `.github/workflows/g8-brainloop.yml`
- Modify: `research/cloud_10coin_backtest/README.md`
- Modify: `research/cloud_10coin_backtest/tests/test_g8_loop.py`

**State branch:** `research/g8-brainloop-state`

**Interfaces:**
- Workflow manual dispatch works while implementation is on the G8 branch.
- Hourly schedule becomes active only after the validated workflow is merged to the default branch.
- `cancel-in-progress: false`.
- State branch receives only generated research state: checkpoint, trial ledger, champion registry, generation summaries, and `AI_SKILL_LIBRARY/v4/evergreen/candidate_state/g8_trading_champions.json`.

- [ ] **Step 1: Create the state branch once from the validated G8 source commit**

Use GitHub branch creation with name `research/g8-brainloop-state`. The state branch must never be treated as production source authority.

- [ ] **Step 2: Write workflow contract tests before workflow implementation**

Add this test to `tests/test_g8_loop.py`:

```python
from pathlib import Path


def test_g8_workflow_is_research_only_and_non_cancelling():
    root = Path(__file__).resolve().parents[3]
    text = (root / ".github/workflows/g8-brainloop.yml").read_text()
    assert "cron: '17 * * * *'" in text
    assert "cancel-in-progress: false" in text
    assert "run_g8_loop.py" in text
    assert "research/g8-brainloop-state" in text
    forbidden = ["wrangler deploy", "railway up", "BYBIT_AUTO_LIVE", "BYBIT_BTC_LIVE_ACK", "/v5/order/create"]
    assert all(token not in text for token in forbidden)
```

Run:
`cd research/cloud_10coin_backtest && PYTHONPATH=. pytest tests/test_g8_loop.py::test_g8_workflow_is_research_only_and_non_cancelling -q`

Expected: FAIL because workflow file does not exist.

- [ ] **Step 3: Implement workflow**

Required header:

```yaml
name: G8 Continuous BrainLoop
on:
  schedule:
    - cron: '17 * * * *'
  workflow_dispatch:
    inputs:
      candidate_budget:
        description: Bounded challengers per coin
        required: false
        default: '4'
permissions:
  contents: write
concurrency:
  group: g8-brainloop-research
  cancel-in-progress: false
```

Job order:
1. `test`: checkout exact source, install research requirements, run G8 targeted tests, full research regression, G8 Brain snapshot tests, and `ci_validate.py`.
2. `loop`: fetch `research/g8-brainloop-state`, restore `g8_state/` from that branch into the runner workspace, execute exactly one bounded ten-coin generation, build/validate the compact Brain snapshot.
3. `persist-state`: use a separate git worktree checked out to `research/g8-brainloop-state`; copy only `g8_state/`, generation reports, and the validated compact Brain research snapshot; commit with message `chore: persist G8 generation ${GITHUB_RUN_ID}` and push only the state branch.
4. `summary`: emit actual per-coin incumbent metrics, promotion/rejection counts, evidence budget remaining, and certified count.

No workflow job deploys Cloudflare/Railway or mutates production variables.

- [ ] **Step 4: Verify workflow contract and regression**

```bash
cd research/cloud_10coin_backtest
PYTHONPATH=. pytest tests/test_g8_loop.py -q
PYTHONPATH=. pytest tests -q
cd ../..
PYTHONPATH=. pytest AI_SKILL_LIBRARY/tests/test_g8_champion_snapshot.py -q
python AI_SKILL_LIBRARY/v4/tools/ci_validate.py --source-sha $(git rev-parse HEAD)
```

- [ ] **Step 5: Manual-dispatch the workflow from the G8 branch and inspect the first real generation**

Completion evidence requires targeted tests PASS, full research regression PASS, Brain validator PASS, one bounded generation complete, state branch updated, trial ledger present, champion snapshot valid, and no live/deployment action.

- [ ] **Step 6: Commit workflow**

```bash
git add .github/workflows/g8-brainloop.yml research/cloud_10coin_backtest/README.md research/cloud_10coin_backtest/tests/test_g8_loop.py
git commit -m "ci: add G8 continuous BrainLoop workflow"
```

- [ ] **Step 7: Integration gate for true hourly operation**

After branch CI/manual generation is verified, open a reviewed PR to `main`. Hourly cron is not claimed active until the workflow exists on `main` and a scheduled run is observed. Because state persists on `research/g8-brainloop-state`, scheduled generations do not create main commits and do not trigger the Skill Gateway main-push deploy workflow.

---

## Final Verification Checklist

- [ ] `PYTHONPATH=. pytest research/cloud_10coin_backtest/tests -q` passes.
- [ ] `PYTHONPATH=. pytest AI_SKILL_LIBRARY/tests/test_g8_champion_snapshot.py -q` passes.
- [ ] `python AI_SKILL_LIBRARY/v4/tools/ci_validate.py --source-sha <exact-source-sha>` passes with the actual branch SHA substituted at execution time.
- [ ] Candidate generation is deterministic by seed.
- [ ] Purge/embargo/CPCV tests prove train/test isolation.
- [ ] Exhausted evidence epoch blocks adaptive promotion.
- [ ] High raw WR with weak worst-fold stability cannot replace a stable incumbent.
- [ ] Failed falsification blocks promotion.
- [ ] Checkpoint and champion writes are atomic.
- [ ] Every trial is recorded with provenance and rejection reason.
- [ ] First real G8 generation is inspected before saying the loop is operational.
- [ ] State writes go only to `research/g8-brainloop-state`.
- [ ] G8 snapshot has zero execution authority and preserves `BYBIT-BTC-STATEFLOW-2.1` precedence.
- [ ] Hourly operation is claimed only after the workflow is present on `main` and a scheduled run is verified.
- [ ] The 80% target is claimed only for a coin whose certified snapshot proves >=100 OOS trades, RR2 WR >=0.80, positive post-cost expectancy, and required stability gates.
