# Kaggriculture V3 meta orchestrator

An isolated research lane, **never an automatic Kaggle submission**. V1 and V2 source,
workflows and champions are untouched. Local promotion is not leaderboard evidence.

## Architecture and provenance

- `incumbent.py`: verbatim self-contained V1 policy from quick-submit blob
  `d9203852095c900ea7f447929fc47da6a869f0e7`; branch head `7b1439af`.
  Parameters match the deep V1 champion (11 hands, sell floor .75991).
- `features.py`: stateless own inventory/capacity, public prices, observable opponent
  expansion/labor/crop behavior, remaining turns and eight strategic regimes.
  Opponent cash is not a proxy for hidden wealth. No opponent private fields are read.
- `policy.py`: deterministic task allocation with distinct target reservation and
  per-turn seed accounting; distance-aware priorities; maturity legality; crop mix
  balancing; configurable early harvest; adaptive selling; terminal DROP then SELL.
  The original incumbent is a separately callable fallback and benchmark opponent.
  V3 exceptions are deliberately visible in validation, never silently converted to PASS.
- `opponents.py`: eight local families: starter, frozen incumbent, expansion, cash,
  early sell, hoarder, high labor, grains. These are original parameterized policies,
  not eight independent strong algorithms; results only certify this local suite.
- `benchmark.py`: official simulator, deterministic seed/seat pairs, no-op instrumentation,
  failure-inclusive win denominator, per-family/per-seat/tail reports and source hashes.
- `search.py`: A screening → B multi-seed/seat → C all families → D direct V1 duel →
  E unseen holdout + paired incumbent → F separate final seeds + paired incumbent.
  Structured ablations precede mutations. Selection stops before E/F. Failed gates do
  not trigger retraining on holdout. Full episodes are 720 steps throughout selection.
- `promotion.py`: frozen conservative pass/fail with explicit reasons.
- `package_submission.py`: AST-composed stdlib-only `main.py`, embedded literals.
  Official loader discovers the final callable `agent`. No file, env, pip or network
  dependency at execution. Packaging alone never means approved or submitted.

## Simulator economics verified

Official `kaggle-environments==1.32.4` source was inspected; it matched upstream source
retrieved in this session byte-for-byte. Sources:
https://github.com/Kaggle/kaggle-environments/tree/master/kaggle_environments/envs/kaggriculture

- Workers expire and reset nightly. Daily hire prices grow with Fibonacci sequence.
- Land costs 1000/2000/4000. Seeds are shared and consumed atomically across units.
- Unit invalid/illegal actions silently no-op: terminal DONE alone is insufficient.
- Grain yield may be positive before legal harvest age. V1 can repeatedly request an
  immature harvest; V3 checks first-yield age first.
- Products accumulate in worker inventories; nightly DROP has a 100-unit shed cap,
  and overflow is discarded. DROP near one of four center tiles works before market.
- The 720-step episode ends before the following overnight drop. Terminal cash is
  the reward; carried/shed products have no salvage value. V3 routes terminal loads
  home and sells in the same turn as DROP when possible.
- Market orders execute remotely: unnecessary “market trips” are not added.
- Livestock requires structures, purchase, pickup, placement, wheat feeding and care;
  fertilizer requires logistics and affects watered yields. Neither module is enabled
  without a controlled simulation showing robust net benefit. No such benefit is
  claimed in this iteration; crop logistics is the implemented scope.

## Objective (frozen before study)

For all scheduled games, with invalid games in the win denominator:
`600*(wins+.5*ties)/N + 120*tanh(mean/5000) + 100*tanh(p20/5000)
+ 40*tanh(worst/5000) - 2000*invalid_rate - 150*unit_noop_rate
- 20*(movement+pass)/actions - 150*P(margin < -5000)`.

All families and both seats get equal game counts. Median and per-seat/family metrics
are reported, with explicit coverage and seat gates; family coverage is not inferred
from aggregate money. Movement/pass is an opportunity-cost proxy, not necessarily
an illegal/wasted action. Unit no-ops are actual no-state-change unit operations;
failed/partial market orders are NOT included in this metric. Oversized sells can be
legal partial fills. Missing money never becomes zero. Market impact means quoted
inventory value is a feature proxy, not realizable liquidation value.

## Promotion

Require complete unique seed×family×seat grids at full 720-step horizon, zero invalid
outcomes, matching candidate/source/simulator identities, disjoint holdout/final seeds,
4+ seeds in each final block, positive direct V1 margin with >=62.5% wins, starter
>=87.5%, positive results against 6+ families, >=50% each seat, zero V3 unit no-ops,
mean no worse than paired V1, p20 no worse by >1000 and worst loss no worse by >2000.
Raw exec, official loader and packaged/source episode equivalence must pass.
These are engineering thresholds, not a statistical significance claim. Paired seats
share one seed; count independent seeds when estimating uncertainty.

## Reproduce

Python 3.12; install `kaggle-environments==1.32.4`.

```bash
python -m compileall -q reward-hunter/kaggriculture-v3
python -m unittest discover -s reward-hunter/kaggriculture-v3/tests -v
python reward-hunter/kaggriculture-v3/raw_exec_test.py
python reward-hunter/kaggriculture-v3/benchmark.py --seeds 101,103 --output /tmp/v3-benchmark.json
python reward-hunter/kaggriculture-v3/search.py --candidates 8 --workers 4 --output /tmp/v3-study-new
```

CPU allocation honors affinity and cgroup quota, caps at eight, default four. Each worker
owns its simulator and restored instrumentation. BLAS threads are set to one in CI.
No nested process pools. Output rows are deterministic order regardless of scheduling.
Reports include timing/provenance separately from deterministic game results.

A finished output directory cannot be reused. Committed seeds are now observed: rerunning
study-001 is a reproduction, NOT new unseen evidence. Before a different candidate's
promotion, prospectively register new disjoint E/F seed blocks in `search.py`; do not
optimize/retry against the committed final set. Deeper dispatch runs use the same
published seeds until that change, so they are reproduction/research only.

## CI and limits

Workflow `Kaggriculture V3 - validation and research`: PR compile/tests/raw-exec,
short meta smoke and full-horizon file episode. Dispatch enables full research;
only a passing champion file permits branch commit, only on the V3 branch. Push is
non-forced and fails on concurrent branch movement. Artifacts are retained 30 days.
No Kaggle secret, submit job or submission command exists in V3.

Competition rules page was reachable but returned no readable rule body:
https://www.kaggle.com/competitions/kaggriculture/rules
Thus public replay collection/intelligence is **OFF / not implemented**. No competitor
code, external datasets, hidden tests or platform manipulation is used.
Canonical live baseline remains submission 56139689; latest accessible status log
34450005641 reports COMPLETE / 600.0 at 07:27 UTC. Extra tar submission 56139862 was
PENDING then; no later confirmation was available. Neither status is represented as
fresh live validation. No status workflow or submission was invoked in this session.
