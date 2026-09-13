# G8 Continuous BrainLoop — Design Specification

Date: 2026-09-13
Branch: `research/cloud-10coin-g8-brainloop-20260913`
Base: `research/cloud-10coin-g7-regime-router-20260913`
Status: Approved design, research-only implementation target

## 1. Purpose

Build a continuously running research loop that searches for stronger crypto trading profiles, promotes only statistically better profiles, records failed experiments, and synchronizes the best verified research evidence into the GitHub Brain so future trading-analysis requests use the strongest currently verified profile.

G8 is not allowed to manufacture an 80% win rate by repeated holdout tuning. The hard target remains an observed backtest target, not a promise of future performance.

## 2. Authority and Safety Boundaries

The current production trading authority remains `BYBIT-BTC-STATEFLOW-2.1`, BTCUSDT Linear Perpetual on Bybit only.

G8 MUST NOT:
- silently replace current production strategy authority;
- place, cancel, amend, or close orders;
- mutate leverage, account state, wallet state, credentials, or live runtime switches;
- auto-promote a financial permission expansion;
- treat a source commit, backtest artifact, or research profile as live market evidence;
- broaden production execution from BTCUSDT to the 10-coin research universe.

G8 MAY:
- continuously run research backtests;
- maintain per-coin research champions;
- expose champion evidence to the Brain as research context;
- provide `NO_TRADE` when evidence is insufficient;
- contribute to live analysis only after the normal Trading authority, freshness, and runtime gates are loaded.

Any future move from research evidence to production execution authority requires a separate explicit migration and production verification.

## 3. Research Universe and Hard Target

Locked research universe:
- BTCUSDT
- ETHUSDT
- BNBUSDT
- XRPUSDT
- SOLUSDT
- TRXUSDT
- DOGEUSDT
- LINKUSDT
- ADAUSDT
- XLMUSDT

Target per coin:
- at least 100 completed OOS evaluation trades;
- observed RR 1:2 win rate at least 80%;
- positive post-cost expectancy;
- stable chronological / CPCV performance;
- no look-ahead;
- no post-outcome selection;
- pessimistic same-bar ambiguity;
- no martingale, grid rescue, add-to-loser, or stop widening.

The target is a certification gate, not a search objective that is allowed to weaken validation integrity.

## 4. Core Architecture

```text
G8 Candidate Factory
    -> bounded mutations / new specialists
    -> Purged Walk-Forward + CPCV
    -> cost stress + stability + falsification
    -> Challenger Evaluation
    -> Promotion Gate
    -> Per-Coin Research Champion Registry
    -> Brain Evidence Snapshot
    -> Trading request resolver loads latest verified snapshot
```

Research and live-decision paths remain separate:

```text
Research Plane
candidate -> backtest -> challenger -> promotion -> champion evidence

Stable Brain / Trading Analysis Plane
request -> trading_router -> current Trading authority -> live data gates
        -> latest verified champion evidence if relevant
        -> qualified analysis / NO_TRADE
```

No in-flight trading request may read a partially written or unverified champion.

## 5. Continuous Loop Semantics

The loop is continuous across bounded workflow runs, not an unbounded process inside one GitHub Actions job.

Each run:
1. loads the previous checkpoint;
2. loads the current per-coin research champions;
3. creates a bounded challenger population;
4. evaluates challengers on research partitions only;
5. promotes only challengers that beat the incumbent under the promotion contract;
6. writes an immutable trial ledger entry for every attempted challenger;
7. publishes an atomic champion snapshot;
8. writes the next checkpoint;
9. exits cleanly.

A scheduled workflow starts the next bounded run. Concurrency MUST serialize G8 loop runs and MUST NOT cancel a valid in-progress run merely because the next schedule tick arrives.

Initial cadence: hourly scheduled trigger plus manual dispatch. If one run is still active, the next run queues rather than overlapping.

## 6. Data Partitions and Anti-Overfit Contract

G8 uses four conceptual evidence tiers:

### 6.1 SEARCH / DEV
Allowed for repeated hypothesis generation and fitting.

### 6.2 PURGED OOF / CPCV
Used for challenger selection. Label horizons are purged; embargo prevents adjacent leakage. Candidate fitness comes from OOF evidence rather than in-sample fit.

### 6.3 FRESH PROMOTION WINDOW
A time-forward window not used to generate the candidate. It may be consumed once for a promotion decision. Once consumed, it is retired into historical evidence and may not remain a pristine promotion window.

### 6.4 SEALED CERTIFICATION WINDOW
Reserved for certification attempts. Repeated adaptive tuning against a revealed certification window is forbidden. A failed certification closes that generation; subsequent research requires a new generation discipline and fresh future evidence before another pristine certification claim.

G8 must record which windows each candidate has seen.

### 6.5 Evidence Epoch and Adaptive Trial Budget

Continuous research on the same finite dataset can overfit even purged OOF/CPCV through repeated adaptive search. Therefore every data cutoff defines an `evidence_epoch`.

Each evidence epoch has a bounded adaptive trial budget per coin and per capability family. The budget is recorded in the checkpoint and trial ledger.

When the promotion evidence budget for an epoch is exhausted:
- the loop MAY continue generating and evaluating exploratory candidates inside SEARCH/DEV;
- exploratory results remain `QUARANTINED`;
- no new Brain champion may be promoted from that exhausted evidence epoch;
- the incumbent verified champion remains active;
- promotion resumes only when a new independent evidence window is created, normally by new chronological market data or a separately approved untouched outer fold.

The scheduler therefore remains continuous, but Brain promotion is evidence-gated rather than iteration-gated.

A candidate cannot reset or evade the budget by changing its random seed, model family, feature subset, or trial ID.

## 7. Candidate Factory

Candidate generation is bounded and typed. A candidate is a composition of independently auditable choices:

- coin;
- regime detector / regime state;
- setup family;
- side;
- causal feature subset;
- optional derivatives feature pack;
- optional order-flow feature pack;
- optional cross-asset context pack;
- model family;
- model hyperparameters within bounded grids;
- probability calibration method;
- abstention / confidence threshold;
- fixed risk geometry;
- maximum holding horizon.

Initial allowed model families:
- logistic baseline;
- Random Forest;
- LightGBM if dependency and reproducibility checks pass;
- XGBoost if dependency and reproducibility checks pass.

Deep sequence models, LOB Transformers, and reinforcement learning remain later-stage quarantined capabilities and do not enter the first G8 implementation.

Candidate mutations MUST be deterministic under a stored seed so a trial can be reproduced exactly.

## 8. Per-Coin Evolution

Each coin has an independent research lineage.

A BTC challenger never replaces a SOL champion. A setup expert is keyed at minimum by:

`coin x regime x setup_family x side`

The registry maintains:
- current research champion;
- optional certified champion;
- previous champions / hall of fame;
- active generation;
- evidence epoch and windows seen;
- adaptive trial budget consumed / remaining;
- trial lineage / parent candidate;
- current best OOF metrics;
- certification status.

A research champion is the best currently verified research profile, but it is not equivalent to a certified 80% profile.

## 9. Fitness and Stability

Candidate ranking is lexicographic, not a single raw win-rate score.

Priority order:
1. validation integrity / no leakage;
2. minimum trade adequacy;
3. worst-fold win rate;
4. Wilson lower confidence bound;
5. OOF RR2 win rate;
6. positive post-cost expectancy;
7. regime / fold stability;
8. drawdown / loss concentration;
9. cost-stress robustness;
10. coverage / completed trades.

A spiky candidate with high mean WR but weak worst-fold behavior loses to a more stable candidate.

## 10. Promotion Contract

A challenger may replace a research champion only when all required gates pass:
- no leakage / causal feature audit passes;
- enough OOF observations for the relevant comparison;
- no material regression in worst-fold stability;
- expectancy remains positive after configured cost stress;
- statistical confidence is not worse in a material way;
- PBO / multiple-testing diagnostics do not materially worsen;
- the challenger improves the lexicographic fitness against the incumbent;
- the challenger record is reproducible from seed + config + source SHA;
- the evidence epoch still has independent promotion budget available.

Promotion is atomic: write a new immutable snapshot, validate it, then move the current pointer.

A challenger that only improves raw WR while degrading robustness is rejected.

## 11. Certification Contract

A `CERTIFIED_CHAMPION` requires:
- at least 100 completed OOS trades;
- RR2 WR >= 0.80;
- positive post-cost expectancy;
- configured validation/holdout stability floors;
- no leakage;
- stable cost-stress result;
- successful sealed certification protocol;
- provenance with source SHA, data range, config hash, trial IDs, evidence epoch, and evidence-window IDs.

Certification does not grant order-execution authority. It grants stronger research evidence status only.

## 12. Trial Ledger and Research Memory

Every candidate attempt is appended to an immutable ledger with at least:
- `trial_id`;
- `generation`;
- `parent_trial_id`;
- `symbol`;
- `seed`;
- `candidate_hash`;
- `source_sha`;
- `evidence_epoch`;
- feature packs;
- model family / parameters;
- geometry;
- data-window IDs;
- OOF trade count;
- OOF RR2 WR;
- worst-fold WR;
- Wilson lower bound;
- expectancy R;
- drawdown metrics;
- cost-stress metrics;
- PBO / DSR when available;
- falsification status;
- promotion decision;
- rejection reasons.

Research memory is evidence memory, not hidden chain-of-thought. It stores outcomes and provenance only.

The Candidate Factory uses the ledger to avoid repeatedly generating materially equivalent failed candidates.

## 13. Falsification and Null Tests

Before a new model family or feature pack can influence promotion, G8 must run bounded falsification checks such as:
- shuffled labels;
- time-shifted feature placebo;
- randomized entry timestamps preserving approximate frequency;
- synthetic no-edge price path where applicable.

If the same workflow can produce apparently strong performance on null data, the capability is quarantined and cannot promote a champion until the defect is resolved.

## 14. Calibration and Abstention

G8 optimizes selective prediction rather than forcing a decision on every candidate setup.

Probability calibration is fit using research OOF evidence only. The trading-analysis resolver may output:
- `QUALIFIED_LONG`;
- `QUALIFIED_SHORT`;
- `NO_TRADE_UNQUALIFIED`;
- `NO_TRADE_REGIME`;
- `NO_TRADE_CONFIDENCE`;
- `NO_TRADE_DISAGREEMENT`;
- `NO_TRADE_COST`;
- `DATA_FAIL`.

A model score is never presented as a literal win probability unless calibration diagnostics support that interpretation.

## 15. Brain Integration

G8 integrates through the existing GitHub Brain authority chain; it does not create a parallel Brain.

New G8 research outputs default to quarantine and have zero routing authority until harmonization and validators pass.

The Brain receives a compact verified champion snapshot containing research evidence, not model internals or hidden reasoning.

For a trading-analysis request, the intended route is:

```text
request
-> task_router
-> DEEP trading profile when required
-> trading_router primary skill / validated capsule
-> current Trading project authority
-> current live-price/runtime evidence
-> G8 champion evidence snapshot if relevant
-> state/structure/flow/derivatives analysis
-> calibration + uncertainty + cost gate
-> qualified result or NO_TRADE
```

Current Trading project authority always outranks G8 research evidence.

For non-BTC coins, G8 may improve research analysis but MUST NOT imply those coins have production execution authority under the current checkpoint.

## 16. Brain Snapshot Contract

The atomic snapshot contains one row per research coin with fields including:
- symbol;
- research champion ID;
- certified champion ID or null;
- generation;
- evidence epoch;
- profile hash;
- source SHA;
- data cutoff;
- OOF metrics;
- certification metrics if any;
- required feature packs;
- supported regimes / setup families / sides;
- confidence / calibration metadata;
- status: `RESEARCH_ONLY`, `CERTIFIED_RESEARCH`, or `QUARANTINED`.

The Stable Brain reads only a validated complete snapshot. Partial workflow artifacts never become Brain evidence.

## 17. Continuous Workflow

Initial workflow topology:

```text
g8-loop-trigger
  -> test-and-validate
  -> load-checkpoint
  -> candidate-matrix (10 coins, bounded parallelism)
  -> per-coin selection
  -> aggregate promotion audit
  -> falsification gate
  -> build champion snapshot
  -> validate snapshot
  -> persist checkpoint + artifacts
```

Schedule: once per hour.

Concurrency:
- one G8 loop generation at a time;
- no `cancel-in-progress` for a valid generation;
- stale/manual supersession requires explicit state handling, not blind cancellation.

A single workflow run has a bounded candidate budget. The next run resumes from checkpoint.

If an evidence epoch is promotion-budget exhausted, the workflow continues exploration but MUST report `promotion_locked_for_epoch=true` and MUST NOT change the verified Brain champion pointer.

## 18. Stop / Continue Rules

The research loop normally continues even after one certified champion is found because stronger challengers may appear.

For an already certified coin:
- incumbent remains locked;
- weaker challengers are rejected;
- a stronger challenger must pass the same promotion/certification gates before replacement.

Global automatic research may be disabled only by an explicit control state or a separately approved cost/governance policy. Reaching 10/10 certified does not silently mutate production execution authority.

## 19. Observability

Each run publishes:
- generation ID;
- evidence epoch;
- adaptive trial budget consumed / remaining;
- `promotion_locked_for_epoch` state;
- start/end source SHA;
- per-coin trial counts;
- incumbent and challenger metrics;
- promotions / rejections;
- null-test results;
- snapshot hash;
- checkpoint hash;
- hard-target progress count;
- workflow health.

No hidden chain-of-thought, credentials, or private provider payloads are stored.

## 20. Failure Behavior

Fail closed when:
- checkpoint is corrupt;
- snapshot validation fails;
- required data is missing or stale for its semantic role;
- candidate provenance is incomplete;
- leakage audit fails;
- null tests reveal spurious edge;
- promotion comparison is incomplete;
- research result conflicts with higher Trading authority;
- a promotion is attempted after the evidence epoch budget is exhausted.

The previous verified champion snapshot remains active if a new generation fails.

## 21. Implementation Boundaries

G8 implementation must be additive to G7 baseline and should reuse existing execution semantics, metrics, candidate routing, causal features, and conservative RR2 simulation.

Expected new responsibilities are separated into focused modules:
- loop state / checkpoint;
- evidence epoch / adaptive trial budget;
- candidate specification and mutation;
- purged/CPCV validation;
- fitness and promotion;
- trial ledger;
- champion registry / snapshot;
- Brain adapter;
- workflow orchestration.

Existing G7 search remains a baseline competitor and rollback reference.

## 22. Testing Strategy

TDD is mandatory.

Required classes of tests:
- deterministic candidate generation under seed;
- no candidate sees future data;
- purge / embargo correctness;
- CPCV partition integrity;
- lexicographic fitness ordering;
- weaker high-WR-but-unstable candidate cannot promote;
- exhausted evidence epoch blocks promotion while allowing exploration;
- a new evidence epoch restores promotion eligibility without resetting historical trial counts;
- atomic champion promotion;
- corrupt snapshot fails closed;
- failed generation preserves prior champion;
- ledger deduplication prevents materially identical retries;
- null/placebo test catches an intentionally leaked feature;
- Brain adapter never overrides higher Trading authority;
- non-certified profile cannot be labeled certified;
- live resolver can abstain;
- full existing regression suite remains green.

## 23. Acceptance Criteria

G8 is technically complete only when:
1. G8 branch tests and full regression pass;
2. an initial loop run processes the full 10-coin universe;
3. trial ledger and per-coin champion registry are produced;
4. a second loop resumes from checkpoint rather than starting from zero;
5. a deliberately weaker challenger is rejected;
6. a synthetic stronger challenger in tests promotes atomically;
7. an exhausted evidence epoch prevents further Brain promotion;
8. Brain snapshot validates and can be loaded by the research adapter;
9. current BTC-only production authority is unchanged;
10. no financial permission is expanded;
11. scheduled bounded loop is active and observable.

Strategy success is a separate condition. It may be called successful against the user hard target only when the actual evidence reports 10/10 coins meeting the hard target. CI success alone is never strategy success.

## 24. Non-Goals for Initial G8

Initial G8 does not:
- guarantee future 80% WR;
- deploy a live multi-coin execution system;
- use reinforcement learning;
- deploy Transformer/LOB deep models;
- auto-purchase external datasets;
- weaken costs, trade-count gates, or evaluation standards to force a pass;
- modify production credentials or live switches.
