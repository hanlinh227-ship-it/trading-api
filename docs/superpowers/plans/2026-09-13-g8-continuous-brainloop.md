# G8 Continuous BrainLoop Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a bounded, hourly, checkpointed G8 research loop that continuously searches for better per-coin trading profiles, promotes only statistically stronger challengers, records every trial, and publishes a validated compact research snapshot that the GitHub Brain can load as subordinate trading evidence.

**Architecture:** G8 is additive to G7. The implementation separates loop state, candidate mutation, purged/CPCV validation, fitness/promotion, ledger/registry, per-coin evaluation, Brain evidence snapshot validation, and GitHub Actions orchestration. Research evidence may improve future trading analysis, but it never replaces `BYBIT-BTC-STATEFLOW-2.1` execution authority and never grants order-execution permissions.

**Tech Stack:** Python 3.13, NumPy 2.x, pandas 2.x, scikit-learn 1.6+, pytest 8.x, existing conservative execution engine, GitHub Actions.

**Spec:** `docs/superpowers/specs/2026-09-13-g8-continuous-brainloop-design.md`

## Global Constraints

- Production trading authority remains `BYBIT-BTC-STATEFLOW-2.1`, BTCUSDT Linear Perpetual on Bybit only.
- G8 is research-only and MUST NOT place/cancel/amend/close orders or mutate leverage/account/wallet/runtime switches.
- Locked research universe remains BTCUSDT, ETHUSDT, BNBUSDT, XRPUSDT, SOLUSDT, TRXUSDT, DOGEUSDT, LINKUSDT, ADAUSDT, XLMUSDT.
- Certification target per coin remains >=100 completed OOS trades, RR 1:2 WR >=0.80, positive post-cost expectancy, stable validation/CPCV, no leakage, no post-outcome selection.
- Same-bar ambiguity remains pessimistic; no martingale, grid rescue, add-to-loser, or stop widening.
- Current Trading authority outranks G8 evidence.
- No repeated adaptive promotion from the same exhausted OOF/evidence epoch.
- A workflow generation is bounded; continuous research is achieved by scheduled checkpointed runs, not an infinite process.

---

## File Map

### New research modules
- `research/cloud_10coin_backtest/g8/__init__.py` — package marker.
- `research/cloud_10coin_backtest/g8/state.py` — loop checkpoint, evidence epoch, trial budget state.
- `research/cloud_10coin_backtest/g8/candidate.py` — immutable candidate spec, hashing, deterministic mutation.
- `research/cloud_10coin_backtest/g8/validation.py` — purged chronological folds and CPCV split generation.
- `research/cloud_10coin_backtest/g8/fitness.py` — fitness tuple, promotion decision, evidence-budget gate.
- `research/cloud_10coin_backtest/g8/ledger.py` — append-only JSONL trial ledger and dedupe lookup.
- `research/cloud_10coin_backtest/g8/registry.py` — per-coin research champion registry and atomic snapshot publishing.
- `research/cloud_10coin_backtest/g8/evaluator.py` — evaluate one candidate using existing feature/execution semantics.
- `research/cloud_10coin_backtest/g8/loop.py` — bounded generation orchestrator.
- `research/cloud_10coin_backtest/run_g8_loop.py` — CLI entrypoint used by GitHub Actions.

### Brain evidence integration
- `AI_SKILL_LIBRARY/v4/evergreen/candidate_state/g8_trading_champions.json` — generated compact research-evidence pointer/snapshot on the G8 branch; zero execution authority.
- `AI_SKILL_LIBRARY/v4/tools/validate_g8_champion_snapshot.py` — schema/authority validator for that snapshot.

### CI
- `.github/workflows/g8-brainloop.yml` — hourly + manual bounded loop.

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

### Task 1: Loop State, Evidence Epoch, and Trial Budget

**Files:**
- Create: `research/cloud_10coin_backtest/g8/__init__.py`
- Create: `research/cloud_10coin_backtest/g8/state.py`
- Test: `research/cloud_10coin_backtest/tests/test_g8_state.py`

**Interfaces:**
- Produces: `LoopState`, `EvidenceEpoch`, `load_loop_state(path)`, `save_loop_state(path, state)`, `can_promote(state, symbol)`, `consume_promotion_trial(state, symbol)`.

- [ ] **Step 1: Write the failing tests**

```python
from pathlib import Path
from g8.state import EvidenceEpoch, LoopState, can_promote, consume_promotion_trial, load_loop_state, save_loop_state


def test_loop_state_round_trip(tmp_path: Path):
    state = LoopState.new(symbols=["BTCUSDT", "ETHUSDT"], source_sha="abc123", max_adaptive_trials=25)
    path = tmp_path / "checkpoint.json"
    save_loop_state(path, state)
    loaded = load_loop_state(path)
    assert loaded.to_dict() == state.to_dict()


def test_evidence_epoch_blocks_promotion_after_budget_exhaustion():
    state = LoopState.new(symbols=["BTCUSDT"], source_sha="abc123", max_adaptive_trials=1)
    assert can_promote(state, "BTCUSDT") is True
    consume_promotion_trial(state, "BTCUSDT")
    assert can_promote(state, "BTCUSDT") is False
```

- [ ] **Step 2: Run tests to verify RED**

Run:
`cd research/cloud_10coin_backtest && PYTHONPATH=. pytest tests/test_g8_state.py -q`

Expected: import failure for `g8.state`.

- [ ] **Step 3: Implement minimal state model**

Use dataclasses with JSON-safe `to_dict()`/`from_dict()`. Required persisted fields:

```python
@dataclass
class EvidenceEpoch:
    epoch_id: str
    data_cutoff: str
    max_adaptive_trials: int
    consumed_trials: dict[str, int]

@dataclass
class LoopState:
    schema_version: int
    generation: int
    source_sha: str
    symbols: list[str]
    epoch: EvidenceEpoch
    last_snapshot_hash: str | None
```

`save_loop_state()` writes to a temporary sibling and then `Path.replace()` to avoid partial checkpoints.

- [ ] **Step 4: Run state tests and regression subset**

Run:
`cd research/cloud_10coin_backtest && PYTHONPATH=. pytest tests/test_g8_state.py tests/test_config.py -q`

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add research/cloud_10coin_backtest/g8 research/cloud_10coin_backtest/tests/test_g8_state.py
git commit -m "feat: add G8 loop state and evidence budget"
```

---

### Task 2: Deterministic Candidate Specification and Mutation

**Files:**
- Create: `research/cloud_10coin_backtest/g8/candidate.py`
- Test: `research/cloud_10coin_backtest/tests/test_g8_candidate.py`

**Interfaces:**
- Produces: `CandidateSpec`, `candidate_hash(spec)`, `seed_baseline_candidates(symbol)`, `mutate_candidate(parent, seed, budget)`.
- Consumes: G7 route/family vocabulary from `optimize/router_g7.py` and model settings compatible with `optimize/nonlinear_model.py`.

- [ ] **Step 1: Write deterministic mutation tests**

```python
from g8.candidate import candidate_hash, mutate_candidate, seed_baseline_candidates


def test_mutation_is_deterministic_for_same_seed():
    parent = seed_baseline_candidates("BTCUSDT")[0]
    a = mutate_candidate(parent, seed=77, budget=6)
    b = mutate_candidate(parent, seed=77, budget=6)
    assert [candidate_hash(x) for x in a] == [candidate_hash(x) for x in b]


def test_candidate_hash_changes_when_geometry_changes():
    parent = seed_baseline_candidates("BTCUSDT")[0]
    child = parent.with_updates(risk_atr=parent.risk_atr + 0.4)
    assert candidate_hash(parent) != candidate_hash(child)
```

- [ ] **Step 2: Verify RED**

Run:
`cd research/cloud_10coin_backtest && PYTHONPATH=. pytest tests/test_g8_candidate.py -q`

- [ ] **Step 3: Implement bounded candidate vocabulary**

`CandidateSpec` fields are explicit and immutable:

```python
@dataclass(frozen=True)
class CandidateSpec:
    symbol: str
    regime: str
    family: str
    side: str
    feature_pack: tuple[str, ...]
    model_family: str
    model_params: tuple[tuple[str, object], ...]
    calibration: str
    threshold: float
    risk_atr: float
    hold_bars: int
    parent_hash: str | None = None
```

Initial model families are only `logistic` and `random_forest`; LightGBM/XGBoost stay disabled until a separate dependency/reproducibility test passes. Mutation may change only one typed dimension per child and must dedupe identical hashes.

- [ ] **Step 4: Run tests**

Run:
`cd research/cloud_10coin_backtest && PYTHONPATH=. pytest tests/test_g8_candidate.py tests/test_g7_router.py tests/test_g5_nonlinear.py -q`

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add research/cloud_10coin_backtest/g8/candidate.py research/cloud_10coin_backtest/tests/test_g8_candidate.py
git commit -m "feat: add deterministic G8 candidate factory"
```

---

### Task 3: Purged Walk-Forward and CPCV Validation

**Files:**
- Create: `research/cloud_10coin_backtest/g8/validation.py`
- Test: `research/cloud_10coin_backtest/tests/test_g8_validation.py`

**Interfaces:**
- Produces: `TimeFold`, `purged_walk_forward(n, n_splits, purge_bars, embargo_bars)`, `cpcv_splits(n, n_groups, test_groups, purge_bars, embargo_bars)`.

- [ ] **Step 1: Write leakage-boundary tests**

```python
from g8.validation import cpcv_splits, purged_walk_forward


def test_purged_walk_forward_has_no_train_test_overlap():
    folds = purged_walk_forward(1000, n_splits=5, purge_bars=144, embargo_bars=12)
    for fold in folds:
        assert set(fold.train_idx).isdisjoint(fold.test_idx)
        assert max(fold.train_idx) < min(fold.test_idx) - 144


def test_cpcv_never_uses_embargo_rows_for_training():
    splits = cpcv_splits(1200, n_groups=6, test_groups=2, purge_bars=72, embargo_bars=12)
    for split in splits:
        blocked = set(split.blocked_idx)
        assert blocked.isdisjoint(split.train_idx)
```

- [ ] **Step 2: Verify RED**

Run:
`cd research/cloud_10coin_backtest && PYTHONPATH=. pytest tests/test_g8_validation.py -q`

- [ ] **Step 3: Implement index-only split generation**

Validation code must know only row indexes and horizons; it must not inspect labels, returns, or outcomes when creating splits. `blocked_idx` includes test rows, purge rows before/after relevant label horizons, and embargo rows.

- [ ] **Step 4: Run validation + existing chronological stability tests**

Run:
`cd research/cloud_10coin_backtest && PYTHONPATH=. pytest tests/test_g8_validation.py tests/test_g3_stability_selection.py -q`

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add research/cloud_10coin_backtest/g8/validation.py research/cloud_10coin_backtest/tests/test_g8_validation.py
git commit -m "feat: add purged walk-forward and CPCV splits"
```

---

### Task 4: Fitness, Promotion, and Evidence-Budget Gate

**Files:**
- Create: `research/cloud_10coin_backtest/g8/fitness.py`
- Test: `research/cloud_10coin_backtest/tests/test_g8_fitness.py`

**Interfaces:**
- Produces: `TrialMetrics`, `fitness_key(metrics)`, `PromotionDecision`, `compare_for_promotion(incumbent, challenger, state, symbol)`.

- [ ] **Step 1: Write ranking and fail-closed tests**

```python
from g8.fitness import TrialMetrics, compare_for_promotion, fitness_key
from g8.state import LoopState


def test_stable_candidate_beats_spiky_high_mean_candidate():
    stable = TrialMetrics(trades=220, rr2_wr=.76, worst_fold_wr=.72, wilson_lower=.69, expectancy_r=.95, max_drawdown_r=7.0, cost_stress_expectancy_r=.72, pbo=.20, leakage_ok=True, falsification_ok=True)
    spiky = TrialMetrics(trades=220, rr2_wr=.84, worst_fold_wr=.39, wilson_lower=.70, expectancy_r=1.02, max_drawdown_r=8.0, cost_stress_expectancy_r=.80, pbo=.35, leakage_ok=True, falsification_ok=True)
    assert fitness_key(stable) > fitness_key(spiky)


def test_exhausted_epoch_blocks_promotion_even_if_challenger_is_better():
    state = LoopState.new(symbols=["BTCUSDT"], source_sha="abc", max_adaptive_trials=0)
    decision = compare_for_promotion(None, TrialMetrics.good_example(), state, "BTCUSDT")
    assert decision.promote is False
    assert "evidence-budget-exhausted" in decision.reasons
```

- [ ] **Step 2: Verify RED**

Run:
`cd research/cloud_10coin_backtest && PYTHONPATH=. pytest tests/test_g8_fitness.py -q`

- [ ] **Step 3: Implement lexicographic fitness and gates**

The tuple ordering must encode the spec priority exactly:

```python
(
    int(metrics.leakage_ok and metrics.falsification_ok),
    int(metrics.trades >= metrics.min_required_trades),
    metrics.worst_fold_wr,
    metrics.wilson_lower,
    metrics.rr2_wr,
    metrics.cost_stress_expectancy_r,
    metrics.expectancy_r,
    -metrics.pbo,
    -metrics.max_drawdown_r,
    metrics.trades,
)
```

`compare_for_promotion()` rejects on exhausted evidence budget, negative post-cost expectancy, material worst-fold regression, failed falsification, or incomplete provenance before comparing fitness.

- [ ] **Step 4: Run tests**

Run:
`cd research/cloud_10coin_backtest && PYTHONPATH=. pytest tests/test_g8_fitness.py -q`

- [ ] **Step 5: Commit**

```bash
git add research/cloud_10coin_backtest/g8/fitness.py research/cloud_10coin_backtest/tests/test_g8_fitness.py
git commit -m "feat: add G8 fitness and promotion contract"
```

---

### Task 5: Append-Only Trial Ledger and Atomic Champion Registry

**Files:**
- Create: `research/cloud_10coin_backtest/g8/ledger.py`
- Create: `research/cloud_10coin_backtest/g8/registry.py`
- Test: `research/cloud_10coin_backtest/tests/test_g8_ledger_registry.py`

**Interfaces:**
- Produces: `TrialRecord`, `append_trial(path, record)`, `seen_candidate_hashes(path, symbol)`, `ChampionRegistry`, `promote_champion(registry, symbol, record)`, `publish_snapshot(path, registry)`.

- [ ] **Step 1: Write append-only and atomicity tests**

```python
import json
from g8.ledger import TrialRecord, append_trial, seen_candidate_hashes
from g8.registry import ChampionRegistry, promote_champion, publish_snapshot


def test_ledger_appends_without_rewriting_existing_trials(tmp_path):
    path = tmp_path / "trials.jsonl"
    append_trial(path, TrialRecord.example("BTCUSDT", "a"))
    first = path.read_text()
    append_trial(path, TrialRecord.example("BTCUSDT", "b"))
    assert path.read_text().startswith(first)
    assert seen_candidate_hashes(path, "BTCUSDT") == {"a", "b"}


def test_snapshot_is_complete_json_after_atomic_publish(tmp_path):
    registry = ChampionRegistry.empty(["BTCUSDT"])
    promote_champion(registry, "BTCUSDT", TrialRecord.example("BTCUSDT", "abc"))
    path = tmp_path / "champions.json"
    publish_snapshot(path, registry)
    payload = json.loads(path.read_text())
    assert payload["symbols"]["BTCUSDT"]["research_champion_id"] is not None
```

- [ ] **Step 2: Verify RED**

Run:
`cd research/cloud_10coin_backtest && PYTHONPATH=. pytest tests/test_g8_ledger_registry.py -q`

- [ ] **Step 3: Implement immutable trial records and atomic registry publishing**

Every `TrialRecord` includes `trial_id`, generation, parent, symbol, seed, candidate hash, source SHA, data/evidence window IDs, metrics, promotion decision, and rejection reasons. `publish_snapshot()` writes temp -> fsync -> replace. Registry keeps research champion, optional certified champion, previous champions, active generation, profile hash, source SHA, and data cutoff.

- [ ] **Step 4: Run tests**

Run:
`cd research/cloud_10coin_backtest && PYTHONPATH=. pytest tests/test_g8_ledger_registry.py -q`

- [ ] **Step 5: Commit**

```bash
git add research/cloud_10coin_backtest/g8/ledger.py research/cloud_10coin_backtest/g8/registry.py research/cloud_10coin_backtest/tests/test_g8_ledger_registry.py
git commit -m "feat: add G8 trial ledger and champion registry"
```

---

### Task 6: Candidate Evaluator Reusing G7 Execution Semantics

**Files:**
- Create: `research/cloud_10coin_backtest/g8/evaluator.py`
- Modify only if required for reusable interfaces: `research/cloud_10coin_backtest/optimize/search_g7.py`
- Test: `research/cloud_10coin_backtest/tests/test_g8_evaluator.py`

**Interfaces:**
- Produces: `evaluate_candidate(symbol, features, config, candidate, validation_plan) -> TrialMetrics` and `run_falsification_suite(...) -> dict`.
- Consumes: `build_routed_candidates`, `geometry_key`, `candidate_feature_matrix`, `label_setup_candidates`, existing nonlinear/logistic fitters, `_simulate_fast`, `_cost_bps`, `summarize_outcomes`.

- [ ] **Step 1: Write evaluator contract tests on synthetic data**

```python
from g8.evaluator import evaluate_candidate


def test_evaluator_returns_oof_only_metrics(flat_features, default_config, baseline_candidate):
    result = evaluate_candidate("BTCUSDT", flat_features, default_config, baseline_candidate)
    assert result.provenance_complete is True
    assert result.in_sample_score is None


def test_same_candidate_cannot_read_rows_beyond_fold_boundary(...):
    # Create two frames identical through cutoff and different afterwards.
    # OOF metrics for folds ending before cutoff must be identical.
    assert left.fold_metrics[:-1] == right.fold_metrics[:-1]
```

- [ ] **Step 2: Verify RED**

Run:
`cd research/cloud_10coin_backtest && PYTHONPATH=. pytest tests/test_g8_evaluator.py -q`

- [ ] **Step 3: Implement candidate-specific route/model/geometry evaluation**

Rules:
- Training labels are created only inside each training fold.
- Test candidates are scored only after the fold model/calibration is frozen.
- Sequential OOS execution uses `_simulate_fast`.
- Cost stress reruns with configured fee/slippage multipliers.
- Falsification includes deterministic shuffled-label and time-shift placebo checks; a capability that scores implausibly strongly on null data is `falsification_ok=False`.
- No certification window is opened here.

- [ ] **Step 4: Run evaluator + execution regression tests**

Run:
`cd research/cloud_10coin_backtest && PYTHONPATH=. pytest tests/test_g8_evaluator.py tests/test_execution.py tests/test_g7_search.py -q`

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add research/cloud_10coin_backtest/g8/evaluator.py research/cloud_10coin_backtest/optimize/search_g7.py research/cloud_10coin_backtest/tests/test_g8_evaluator.py
git commit -m "feat: add G8 purged candidate evaluator"
```

---

### Task 7: Bounded Per-Coin Evolution Loop and CLI

**Files:**
- Create: `research/cloud_10coin_backtest/g8/loop.py`
- Create: `research/cloud_10coin_backtest/run_g8_loop.py`
- Test: `research/cloud_10coin_backtest/tests/test_g8_loop.py`

**Interfaces:**
- Produces: `run_generation(symbols, start, end, state_dir, results_dir, candidate_budget, source_sha) -> GenerationResult`.
- CLI flags: `--symbols`, `--start`, `--end`, `--state-dir`, `--results-dir`, `--candidate-budget`, `--source-sha`.

- [ ] **Step 1: Write boundedness/resume tests**

```python
from g8.loop import run_generation


def test_generation_never_exceeds_candidate_budget(tmp_path, tiny_feature_provider):
    result = run_generation(["BTCUSDT"], "2025-01-01", "2025-03-01", tmp_path / "state", tmp_path / "results", candidate_budget=3, source_sha="abc", feature_provider=tiny_feature_provider)
    assert result.trials_attempted["BTCUSDT"] <= 3


def test_second_generation_resumes_from_checkpoint(tmp_path, tiny_feature_provider):
    first = run_generation(...)
    second = run_generation(...)
    assert second.generation == first.generation + 1
    assert second.previous_snapshot_hash == first.snapshot_hash
```

- [ ] **Step 2: Verify RED**

Run:
`cd research/cloud_10coin_backtest && PYTHONPATH=. pytest tests/test_g8_loop.py -q`

- [ ] **Step 3: Implement generation orchestration**

Per symbol:
1. load incumbent;
2. seed from incumbent or G7 baseline;
3. exclude candidate hashes already recorded;
4. evaluate at most `candidate_budget` challengers;
5. append every trial;
6. consume promotion evidence budget for valid adaptive comparisons;
7. atomically promote winners;
8. never replace prior verified snapshot if generation fails.

Generation output must include progress toward 10/10 target but must not label research-only improvement as certification.

- [ ] **Step 4: Add CLI smoke test**

Run:
`cd research/cloud_10coin_backtest && PYTHONPATH=. python run_g8_loop.py --symbols BTCUSDT --start 2025-01-01 --end 2025-02-01 --candidate-budget 1 --state-dir /tmp/g8-state --results-dir /tmp/g8-results --source-sha local-smoke`

Expected: clean exit, checkpoint JSON, trial ledger, champion snapshot, generation summary.

- [ ] **Step 5: Run full research regression suite**

Run:
`cd research/cloud_10coin_backtest && PYTHONPATH=. pytest tests -q`

Expected: all tests pass.

- [ ] **Step 6: Commit**

```bash
git add research/cloud_10coin_backtest/g8/loop.py research/cloud_10coin_backtest/run_g8_loop.py research/cloud_10coin_backtest/tests/test_g8_loop.py
git commit -m "feat: add bounded G8 continuous research generation"
```

---

### Task 8: Brain Evidence Snapshot Adapter and Validator

**Files:**
- Create: `AI_SKILL_LIBRARY/v4/tools/validate_g8_champion_snapshot.py`
- Create/generated by test fixture: `AI_SKILL_LIBRARY/v4/evergreen/candidate_state/g8_trading_champions.json`
- Create: `AI_SKILL_LIBRARY/tests/test_g8_champion_snapshot.py`
- Modify: `research/cloud_10coin_backtest/g8/registry.py`

**Interfaces:**
- Produces: `build_brain_snapshot(registry, source_sha, data_cutoff) -> dict` and CLI validator exit code 0/1.

- [ ] **Step 1: Write authority-preservation tests**

```python
from AI_SKILL_LIBRARY.v4.tools.validate_g8_champion_snapshot import validate_snapshot


def test_snapshot_has_zero_execution_authority(valid_snapshot):
    errors = validate_snapshot(valid_snapshot)
    assert errors == []
    assert valid_snapshot["authority"]["execution"] == "none"
    assert valid_snapshot["authority"]["production_strategy"] == "BYBIT-BTC-STATEFLOW-2.1"


def test_non_btc_certification_does_not_grant_production_execution(valid_snapshot):
    valid_snapshot["symbols"]["SOLUSDT"]["status"] = "CERTIFIED_RESEARCH"
    assert validate_snapshot(valid_snapshot) == []
    assert valid_snapshot["symbols"]["SOLUSDT"]["production_execution_authority"] is False
```

- [ ] **Step 2: Verify RED**

Run:
`PYTHONPATH=. pytest AI_SKILL_LIBRARY/tests/test_g8_champion_snapshot.py -q`

- [ ] **Step 3: Implement validator and compact snapshot**

Required top-level fields:

```json
{
  "schema_version": 1,
  "kind": "g8_trading_research_evidence",
  "research_only": true,
  "authority": {
    "execution": "none",
    "production_strategy": "BYBIT-BTC-STATEFLOW-2.1"
  },
  "source_sha": "...",
  "data_cutoff": "YYYY-MM-DD",
  "snapshot_hash": "...",
  "symbols": {}
}
```

Each symbol row carries research champion ID, certified champion ID/null, generation, profile hash, OOF metrics, certification metrics/null, feature packs, regimes/families/sides, calibration metadata, and one of `RESEARCH_ONLY`, `CERTIFIED_RESEARCH`, `QUARANTINED`.

Validator rejects execution permission fields, missing provenance, unsupported symbols, invalid status, and snapshot-hash mismatch.

- [ ] **Step 4: Run Brain and research validators**

Run:
`PYTHONPATH=. pytest AI_SKILL_LIBRARY/tests/test_g8_champion_snapshot.py -q`

Run:
`python AI_SKILL_LIBRARY/v4/tools/validate_g8_champion_snapshot.py AI_SKILL_LIBRARY/v4/evergreen/candidate_state/g8_trading_champions.json`

Run:
`python AI_SKILL_LIBRARY/v4/tools/ci_validate.py --source-sha $(git rev-parse HEAD)`

Expected: all pass; no production authority mutation.

- [ ] **Step 5: Commit**

```bash
git add AI_SKILL_LIBRARY/v4/tools/validate_g8_champion_snapshot.py AI_SKILL_LIBRARY/v4/evergreen/candidate_state/g8_trading_champions.json AI_SKILL_LIBRARY/tests/test_g8_champion_snapshot.py research/cloud_10coin_backtest/g8/registry.py
git commit -m "feat: publish validated G8 Brain research evidence"
```

---

### Task 9: Hourly GitHub Actions BrainLoop

**Files:**
- Create: `.github/workflows/g8-brainloop.yml`
- Modify: `research/cloud_10coin_backtest/README.md`

**Interfaces:**
- Schedule: hourly cron.
- Manual dispatch: `candidate_budget` optional bounded integer.
- Concurrency: one branch loop at a time, `cancel-in-progress: false`.

- [ ] **Step 1: Add workflow with test-first job graph**

Workflow topology:

```yaml
name: G8 Continuous BrainLoop
on:
  schedule:
    - cron: '17 * * * *'
  workflow_dispatch:
    inputs:
      candidate_budget:
        description: bounded challengers per coin
        required: false
        default: '4'
concurrency:
  group: g8-brainloop-research
  cancel-in-progress: false
```

Jobs:
1. `test` — install requirements, run `pytest tests/test_g8_*.py -q`, full research regression, G8 Brain snapshot tests.
2. `loop` — restore previous checkpoint/ledger artifact if present, run one bounded generation over 10 coins with max parallelism controlled inside the runner, upload state/results.
3. `validate-snapshot` — run G8 snapshot validator and `ci_validate.py` against current source SHA.
4. `summary` — publish per-coin incumbent metrics, promotions/rejections, epoch budget remaining, and certified count.

The workflow MUST NOT deploy Cloudflare/Railway or touch production environment variables.

- [ ] **Step 2: Add workflow contract test via static assertions**

Add assertions to `research/cloud_10coin_backtest/tests/test_g8_loop.py` that parse `.github/workflows/g8-brainloop.yml` as text and require:
- hourly schedule;
- `cancel-in-progress: false`;
- no `railway`, `wrangler deploy`, `BYBIT_AUTO_LIVE`, or order-execution commands;
- `run_g8_loop.py` invocation;
- snapshot validator invocation.

- [ ] **Step 3: Run full verification locally/in CI**

Run:
`cd research/cloud_10coin_backtest && PYTHONPATH=. pytest tests -q`

Run:
`PYTHONPATH=. pytest AI_SKILL_LIBRARY/tests -q`

Run:
`python AI_SKILL_LIBRARY/v4/tools/ci_validate.py --source-sha $(git rev-parse HEAD)`

Expected: PASS.

- [ ] **Step 4: Commit workflow**

```bash
git add .github/workflows/g8-brainloop.yml research/cloud_10coin_backtest/README.md research/cloud_10coin_backtest/tests/test_g8_loop.py
git commit -m "ci: activate hourly G8 Continuous BrainLoop"
```

- [ ] **Step 5: Verify first GitHub Actions run before claiming activation**

Required evidence:
- targeted G8 tests PASS;
- full research regression PASS;
- Brain validator PASS;
- one bounded generation completes;
- checkpoint artifact exists;
- trial ledger artifact exists;
- champion snapshot validates;
- no deployment/live-runtime job exists;
- summary reports actual champion/certification state, not a fabricated success.

Do not claim the 80% target is achieved unless the generated certified snapshot proves it per coin.

---

## Final Verification Checklist

Before calling G8 BrainLoop implemented:

- [ ] `PYTHONPATH=. pytest research/cloud_10coin_backtest/tests -q` passes.
- [ ] `PYTHONPATH=. pytest AI_SKILL_LIBRARY/tests -q` passes.
- [ ] `python AI_SKILL_LIBRARY/v4/tools/ci_validate.py --source-sha <exact-branch-sha>` passes.
- [ ] G8 candidate generation is deterministic by seed.
- [ ] purge/embargo/CPCV tests prove no fold overlap.
- [ ] evidence-budget exhaustion blocks adaptive promotion.
- [ ] high-WR/unstable challenger loses to stable incumbent.
- [ ] falsification failure blocks promotion.
- [ ] checkpoint and champion snapshot writes are atomic.
- [ ] workflow is bounded and hourly, with `cancel-in-progress: false`.
- [ ] G8 Brain snapshot has zero execution authority and preserves `BYBIT-BTC-STATEFLOW-2.1` production precedence.
- [ ] first real GitHub Actions generation is inspected before reporting activation.
