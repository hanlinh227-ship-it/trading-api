# Cloud 10-Coin Backtest G2 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add strict causal sweep→MSS→OTE state-machine research and a frozen 1–3-profile per-coin ensemble to improve RR1:2 precision without weakening the >=100-trade, >=80% holdout-aware gate.

**Architecture:** Extend the existing causal 5m feature frame with closed-HTF regime and flow-state fields, add one new strict strategy family with candidate quality/risk floors, then replace single-profile selection with a development-frontier → validation-ensemble → frozen-holdout workflow. Existing execution simulation, costs, data loader, conservative ambiguity handling, and production isolation remain unchanged.

**Tech Stack:** Python 3.13, pandas, numpy, pytest, Railway batch service, Binance USD-M archive data.

**Spec:** `docs/superpowers/specs/2026-09-13-cloud-10coin-backtest-g2-design.md`

## Global Constraints

- Universe remains BTCUSDT, ETHUSDT, BNBUSDT, XRPUSDT, SOLUSDT, TRXUSDT, DOGEUSDT, LINKUSDT, ADAUSDT, XLMUSDT.
- PASS requires >=100 evaluation trades and >=80% RR1:2 WR, positive post-cost expectancy, validation/holdout stability, and a frozen rule before holdout.
- Same-bar ambiguity remains pessimistic; no martingale, grid rescue, look-ahead, or post-outcome trade selection.
- G2 does not change live BTCUSDT Bybit production authority.
- G2 does not add cross-coin SMT; that remains a later generation if required.

---

### Task 1: Causal G2 Feature State

**Files:**
- Modify: `research/cloud_10coin_backtest/features/state.py`
- Test: `research/cloud_10coin_backtest/tests/test_g2_features.py`

**Interfaces:**
- Consumes: `build_features(df5: pd.DataFrame) -> pd.DataFrame`
- Produces additional columns: `h1_trend`, `h4_trend`, `regime`, `flow_ema12`, `flow_divergence`, `swing_high_6`, `swing_low_6`, `prior_swing_high_6`, `prior_swing_low_6`.

- [ ] **Step 1: Write failing tests** proving appending future bars does not change prior G2 features and that prior swing levels exclude the current bar.
- [ ] **Step 2: Run** `PYTHONPATH=. pytest tests/test_g2_features.py -q` and verify RED because columns are missing.
- [ ] **Step 3: Implement minimal features** using only shifted/closed inputs. Use numeric trend states {-1,0,1}; regime values `compression`, `normal`, `expansion`; `flow_ema12` from current/past `flow_delta`; `flow_divergence` as directional disagreement between recent close change and flow EMA.
- [ ] **Step 4: Run focused test and full regression suite**; both must pass.
- [ ] **Step 5: Commit** `feat: add causal G2 regime and flow features`.

### Task 2: Candidate Quality and Risk Floors

**Files:**
- Modify: `research/cloud_10coin_backtest/strategies/common.py`
- Test: `research/cloud_10coin_backtest/tests/test_g2_candidate_quality.py`

**Interfaces:**
- Add `quality_score(features, side, body_atr, flow_strength, trend_strength, rel_volume) -> pd.Series`.
- Extend candidate construction with optional `quality`, `min_risk_atr`, and `max_cost_r`; encode quality on candidate without changing existing G1 callers.

- [ ] **Step 1: Write failing tests** that reject zero/tiny risk, reject excessive round-trip cost/R, and rank a stronger causal signal above a weaker one.
- [ ] **Step 2: Run focused test** and verify RED.
- [ ] **Step 3: Implement backward-compatible candidate metadata/risk-floor behavior**. Existing strategy calls without G2 options must retain prior behavior.
- [ ] **Step 4: Run full suite** and confirm no G1 regression.
- [ ] **Step 5: Commit** `feat: add G2 candidate quality and risk floors`.

### Task 3: Strict Sweep→MSS→OTE State Machine

**Files:**
- Create: `research/cloud_10coin_backtest/strategies/sweep_mss_ote_g2.py`
- Test: `research/cloud_10coin_backtest/tests/test_g2_sweep_mss_ote.py`

**Interfaces:**
- `family_name = "sweep_mss_ote_g2"`
- `parameter_grid() -> Iterable[dict]`
- `generate_candidates(features: pd.DataFrame, params: dict) -> list[OrderCandidate]`

- [ ] **Step 1: Write failing tests** with synthetic bars showing that MSS before sweep is invalid, sweep→MSS in order is valid, weak displacement is rejected, and OTE entry/stop geometry uses MSS impulse and sweep invalidation.
- [ ] **Step 2: Run focused test** and verify module-missing/behavior RED.
- [ ] **Step 3: Implement bounded grid** over side, sweep lookback/window, MSS displacement floor, OTE depth, flow floor, risk floor, stop buffer, fill window, and regime filter. No date/session parameters.
- [ ] **Step 4: Run focused + full suite**.
- [ ] **Step 5: Commit** `feat: add strict sweep MSS OTE G2 family`.

### Task 4: Frozen Ensemble and Conflict Resolution

**Files:**
- Create: `research/cloud_10coin_backtest/optimize/ensemble.py`
- Modify: `research/cloud_10coin_backtest/optimize/selection.py`
- Test: `research/cloud_10coin_backtest/tests/test_g2_ensemble.py`

**Interfaces:**
- `EnsembleMember(family: str, params: dict, profile_hash: str)` frozen dataclass.
- `LockedEnsemble(members: tuple[EnsembleMember, ...], ensemble_hash: str)` frozen dataclass.
- `merge_candidates(candidate_sets) -> list[OrderCandidate]` keeps highest signal-time quality on overlap with deterministic tie-break.
- `lock_ensemble(members) -> LockedEnsemble` hashes immutable member rules.

- [ ] **Step 1: Write failing tests** proving overlap is resolved by pre-outcome quality, ties are deterministic, and frozen ensemble mutation raises/does not change stored parameters.
- [ ] **Step 2: Run focused test** and verify RED.
- [ ] **Step 3: Implement immutable ensemble types and merge behavior**.
- [ ] **Step 4: Run focused + full suite**.
- [ ] **Step 5: Commit** `feat: add frozen per-coin profile ensembles`.

### Task 5: Development Frontier → Validation Ensemble → Holdout Search

**Files:**
- Modify: `research/cloud_10coin_backtest/optimize/search.py`
- Test: `research/cloud_10coin_backtest/tests/test_g2_search_protocol.py`

**Interfaces:**
- Add G2 family to search registry.
- Add `search_coin_g2(symbol, features, config) -> CoinResearchResult`.
- Development selects bounded candidates/frontier only; validation chooses up to 3 members; holdout is evaluated only after ensemble lock.

- [ ] **Step 1: Write failing tests** using deterministic fake family outcomes to prove holdout metrics cannot influence member selection and that an ensemble with <100 trades cannot PASS even at 100% WR.
- [ ] **Step 2: Run focused test** and verify RED.
- [ ] **Step 3: Implement G2 ranking**: RR2 WR + Wilson lower + breadth + expectancy minus complexity/cost penalties. Keep a bounded top set per family, evaluate small combinations on validation, freeze winner, then evaluate holdout.
- [ ] **Step 4: Add stability gate**: validation/holdout segment with >=20 trades must have RR2 WR >=0.60; final evaluation >=100 and >=0.80 with positive expectancy.
- [ ] **Step 5: Run focused + full suite**.
- [ ] **Step 6: Commit** `feat: add leakage-safe G2 ensemble search`.

### Task 6: Runner Generation Mode and Reporting

**Files:**
- Modify: `research/cloud_10coin_backtest/run.py`
- Modify: `research/cloud_10coin_backtest/reporting.py`
- Test: `research/cloud_10coin_backtest/tests/test_g2_runner.py`

**Interfaces:**
- CLI adds `--generation g1|g2`, default `g2` on research branch.
- G2 output records generation, ensemble members/hashes, and bottleneck classification.

- [ ] **Step 1: Write failing tests** for generation parsing and G2 summary metadata.
- [ ] **Step 2: Run focused test** and verify RED.
- [ ] **Step 3: Route G2 to `search_coin_g2` while retaining G1 for reproducibility**.
- [ ] **Step 4: Run full suite**.
- [ ] **Step 5: Commit** `feat: add G2 batch runner and report metadata`.

### Task 7: Railway Verification and Ten-Coin G2 Run

**Files:**
- No production-gateway file changes.
- Runtime artifacts only under `results/` and Railway logs.

**Interfaces:**
- Exact source SHA pinned to `crypto-backtest-job`.

- [ ] **Step 1: Deploy exact G2 SHA** with start command `PYTHONPATH=. pytest tests -q`; require full PASS.
- [ ] **Step 2: Run a short BTCUSDT,SOLUSDT G2 smoke** on archive-backed dates and verify no runtime/data errors.
- [ ] **Step 3: Run all 10 coins for `2024-01-01..2026-08-31`** using G2.
- [ ] **Step 4: Collect `COIN_RESULT` and `FINAL_SUMMARY_JSON`**; report exact trade count, evaluation RR2 WR, validation/holdout WR, expectancy, locked ensemble, and bottleneck for every coin.
- [ ] **Step 5: If a frozen coin is >=80% but <100 trades**, extend its history backward without changing parameters. If a coin has >=100 trades and <80%, keep it FAIL and classify the remaining bottleneck; do not loosen rules post-hoc.
- [ ] **Step 6: Verify production `crypto-research-gateway-prod` deployment/source metadata remained unchanged**.

## Self-review

- Spec coverage: strict state machine, regime/flow, risk floor, ensemble, validation-only selection, frozen holdout, history-extension rule, hard PASS gate, Railway isolation are all mapped to tasks.
- Placeholder scan: none.
- Type consistency: G2 search returns the existing `CoinResearchResult`; new immutable ensemble types are confined to selection/search and serialized by existing result/report paths with G2 metadata additions.
