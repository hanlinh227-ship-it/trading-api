# G7 Regime Router — Design Specification

## Goal
Build a research-only ten-coin G7 backtest/analysis pipeline that improves win-rate stability by routing each causal market event through a regime classifier, a family/side-specific setup model, one locked geometry, and an explicit abstention gate. The hard research target remains >=100 completed evaluation trades per coin, observed RR 1:2 win rate >=80%, positive post-cost expectancy, and stable chronological validation/holdout. G7 must never claim that future win rate is guaranteed or that a live signal is "always >80%".

## Authority and isolation
- Canonical production trading authority remains `docs/checkpoints/CURRENT_HANDOFF.md`: BTCUSDT Bybit only.
- G7 is research-only and must not change live order/execution authority, runtime switches, credentials, production service behavior, or the live-price gateway.
- G7 may create research outputs and a qualification contract for future coin analysis, but it has zero routing/trading authority until separately promoted through existing harmonization/eval/security gates.
- No martingale, grid rescue, add-to-loser, stop widening, post-outcome selection, look-ahead, or OOS retuning.

## Problem diagnosed from G6
G6 improved structural candidate framing but its single forest still mixed heterogeneous setup families and market regimes. BTC G6 OOF RR2 WR was about 30.5% and OOS RR2 WR about 31.2%; ETH and ADA showed similar ~31-33% OOS behavior. This indicates insufficient base edge / state separation rather than a threshold-only problem.

## Architecture

`5m causal features`
→ `G7 regime classifier`
→ `family router`
→ `family + side + regime route`
→ `single locked geometry per route`
→ `route-specific walk-forward model`
→ `stability-first threshold selection`
→ `abstain if route not qualified`
→ `sequential conservative execution`
→ `validation`
→ `untouched holdout`
→ `coin qualification contract`

### 1. Regime classifier
Use only information available at or before the signal bar. Initial G7 uses existing historical OHLCV-derived causal fields because reliable multi-year derivatives archives have not yet been verified.

Regimes:
- `TREND_UP`
- `TREND_DOWN`
- `RANGE`
- `COMPRESSION`
- `EXPANSION`
- `SHOCK`

The classifier uses H1/H4 trend alignment, trend strength, volatility regime, body/ATR expansion, relative volume, z-distance and recent impulse. `SHOCK` is fail-closed / no-trade by default.

### 2. Family router
Allowed routes:
- `TREND_UP`: LONG `setup_trend`, LONG `setup_breakout`; optional LONG `setup_compression` only when the signal contains a valid breakout transition.
- `TREND_DOWN`: SHORT equivalents.
- `RANGE`: `setup_sweep` and `setup_exhaustion` both sides.
- `COMPRESSION`: breakout/compression setup only after directional trigger; no blind pre-breakout entry.
- `EXPANSION`: continuation only when H1/H4 direction agrees and the event is not extreme/exhausted; otherwise abstain.
- `SHOCK`: no candidate.

One candidate route key is `(regime, family, side)`.

### 3. Route-specific model
Do not train one model across unrelated setup families. Each eligible `(regime, family, side)` route receives its own bounded Random Forest meta-label model when enough prior-fold labels exist and both outcome classes are present.

Candidate features include existing G6 directional market-state features plus regime identity, family identity, side, risk geometry and hold geometry. No validation or holdout values may enter model fitting, geometry selection or threshold selection.

### 4. Single locked geometry
G6 produces multiple risk/hold variants per event. G7 may label multiple geometries inside DEV for research, but each route must select exactly one `(risk_atr, hold_bars)` from DEV walk-forward evidence before validation/holdout. OOS inference may emit at most one geometry for that route/event.

Geometry grid remains bounded and cost-valid. No micro-stop geometry may bypass the existing G2 cost/risk guard.

### 5. Stability-first threshold selection
Threshold selection prioritizes stable precision instead of breadth:
1. minimum fold RR2 WR,
2. overall Wilson lower confidence bound,
3. positive post-cost expectancy,
4. completed-trade breadth.

A route can be used diagnostically even if it is not target-qualified, but it must carry `qualified=false` and cannot be represented as an >=80% route.

Route target qualification requires all of:
- sufficient OOF sample for the route,
- overall OOF RR2 WR >=80%,
- positive OOF expectancy,
- stability floor across eligible folds,
- no material single-fold collapse.

The coin hard PASS remains determined only after frozen-profile validation + holdout evaluation and existing global hard gates.

### 6. Abstention / coin analysis contract
G7 adds a research-only analysis decision contract:
- `QUALIFIED_SIGNAL`: only when the selected locked coin/profile and route have passed the configured qualification gates and the current event matches that route.
- `NO_TRADE_UNQUALIFIED`: setup exists but its route/profile has not proven the target.
- `NO_TRADE_REGIME`: current regime does not permit the setup.
- `NO_TRADE_CONFIDENCE`: permitted route but model probability is below its frozen threshold.
- `DATA_FAIL`: causal/current data quality is insufficient.

The system must never convert model score into a fabricated "80% probability". An 80% claim is allowed only as an observed historical qualification statement tied to the exact frozen evaluation evidence.

### 7. Walk-forward and anti-overfit contract
- Full coin split remains chronological DEV / validation / holdout.
- DEV uses chronological expanding walk-forward folds.
- For each OOF fold, geometry/model/threshold decisions can use prior folds only.
- Final route specs are refit/frozen using DEV only.
- Validation/holdout remain untouched until route specs are frozen.
- Same-bar stop/target ambiguity remains pessimistic.
- Actual OOS portfolio evaluation uses sequential non-overlap conservative execution, not independent training labels.

### 8. Initial G7 data scope
G7.0 uses the currently auditable Binance USD-M 5m archive and causal derived fields. Funding/OI/premium/liquidation/context are intentionally not fabricated or backfilled from short-history endpoints. A later G7.x extension may add them only after a trustworthy historical source is verified and independently audited.

### 9. Output artifacts
Per coin:
- locked G7 profile hash,
- chosen route geometries,
- per-route OOF stability metrics,
- qualification flags,
- DEV / validation / holdout / evaluation metrics,
- evaluation trades,
- bottlenecks and abstention counts.

Aggregate:
- 10-coin hard-gate table,
- pass count,
- qualification coverage,
- route-level stability diagnostics,
- explicit `all_pass` boolean.

### 10. CI activation
A dedicated G7 workflow runs automatically on pushes to the G7 research branch:
1. G7 unit tests,
2. full regression suite,
3. BTC smoke,
4. ten-coin matrix,
5. aggregate hard gate.

Workflow success means the pipeline executed correctly; it does not mean the trading target passed. Target success requires aggregate `all_pass=true` with all hard metrics satisfied.

## Acceptance criteria
G7 implementation is technically complete when tests and workflow execute end-to-end with causal/frozen contracts intact. Research success is a separate condition and may only be reported when all ten coins independently satisfy the hard target on evaluation data.
