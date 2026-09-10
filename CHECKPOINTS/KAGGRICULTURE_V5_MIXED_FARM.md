# Kaggriculture V5 Mixed-Farm Economy Checkpoint

Updated: 2026-09-10

## Identity
- Repository: `hanlinh227-ship-it/trading-api`
- Branch: `codex/kaggriculture-v5-mixed-farm-economy`
- Base: `codex/kaggriculture-v4-full-farm-expansion`
- Current engine target: `kaggle-environments==1.32.7`
- Kaggle submission: **NO**

## Why V5 exists
V5 converts the V4 acreage-first research lane into a mixed-farm economy. The goal is not merely to own land: crops, livestock, feed, care, fertilizer, labor, selling and expansion must form one cash-flow engine that can finance all four quadrants and still beat the incumbent on unseen games.

## Public meta research integrated
- Kaggle Staff says current agents should use `kaggle-environments >= 1.32.7`; V5 therefore treats older 1.32.4 V3/V4 studies as historical research, not current promotion evidence.
- A public high-Elo replay study reported a modal older-meta farm around 9 cows + 4 sheep + 1 wheat + 10 hands, normally on three quadrants. This is included only as a search prior; V5 does not assume it is current or optimal.
- Public replay discussions and Staff guidance establish public episode/replay material as fair-use competition research. V5 includes an offline analyzer and never makes replay/network calls from the submitted runtime.
- Public strategies repeatedly emphasize livestock CARE/FEED economics, metered selling, shed-capacity risk and action/movement efficiency. V5 independently implements and re-tests those concepts.

Research notes: `reward-hunter/kaggriculture-v3/meta/PUBLIC_META_RESEARCH.md`
Offline analyzer: `reward-hunter/kaggriculture-v3/meta/replay_intelligence.py`

## V5 runtime architecture
- `features.py`: public market/town demand, scarcity, crop mix, herd state, feed/care/fertilizer obligations, land state, productive utilization and opponent behavior.
- `policy.py`: dynamic marginal crop ROI; working-capital-aware land expansion; bounded cow/sheep/goose pipeline; structure placement; animal pickup/place/feed/care/harvest; fertilizer collection/use; metered selling; feed insurance; terminal liquidation.
- `benchmark_v5.py`: paired seeds/seats, current 1.32.7 provenance, money/margin/tail, action no-ops, full unlock timing, productive utilization, animals and terminal unsold stock.
- `search_v5.py`: crop-only controls plus multiple herd families, public meta prior, stochastic variants and optional fresh replay-derived prior. A fresh public prior can enter only as a candidate; it cannot bypass local promotion gates.
- `promotion_v5.py`: fail closed on current engine, invalid games, no-ops, weak incumbent/meta results, tail regressions, slow/incomplete expansion, under-utilization, terminal inventory or raw-exec mismatch.

## Continuous R&D loop
Workflow `.github/workflows/reward-kaggriculture-v5-meta-intel.yml` is designed to:
1. download the public scheduled Kaggriculture top-replay notebook output,
2. analyze it offline,
3. upload a compact meta report every scan,
4. after merge, run a daily local adaptive search using the fresh replay-derived prior,
5. never auto-submit to Kaggle.

This is continuous external R&D, not hidden cross-match memory inside the Kaggle runtime. The submitted agent remains self-contained and adapts only to legal observations during each match.

## Important V5.0 failure found and fixed
Initial canonical 1.32.7 validation run `34458086918` validated code/runtime but its 360-step economic smoke exposed a serious strategy failure:
- 16/16 valid games
- 0 wins
- mean margin `-2400.625`
- mean money `0.0`
- movement/idle rate `0.9834`
- no unit no-ops
- no full unlock in the 15-day smoke

Root cause: the first V5 design reserved nearly the entire next-land cost while continuing to hire, so after buying the first field it could enter a cash-flow deadlock: insufficient cash for the next land purchase but too much reserved to buy productive seeds. It also attempted to build structures for the entire target herd before the herd/cash-flow pipeline justified them.

V5.1 corrections:
- preserve a true operating-capital floor even when land is late,
- buy a productive seed engine before repeated hires,
- cap hires to economically useful workers and at most three new hires per turn,
- cap new animals to a two-animal purchase pipeline,
- build structures only for active/queued herd plus a small forward pipeline,
- maintain local shed pickup budgets to avoid duplicate pickup no-ops,
- meter crop sales and reserve feed wheat,
- diversify crop ROI instead of degenerating into monoculture,
- keep full-farm expansion as a research requirement but never let acreage alone authorize promotion.

Corrected V5.1 trigger commit: `682bb3df08911fdfa8c0aaaba6dc4b6625f1edc4`.

## Workflows / runs
- V5 canonical research workflow: `.github/workflows/reward-kaggriculture-v5-mixed-farm.yml`
- V5.0 initial run: `34458086918` — validation SUCCESS but economic smoke FAILED strategically; stale research superseded by V5.1.
- V5 public meta workflow: `.github/workflows/reward-kaggriculture-v5-meta-intel.yml`
- Initial public meta run: `34458096559` — started from trigger `ef145df13e61990d4340fefb805463e6a55ef206`.
- Corrected V5.1 run: inspect latest branch workflows; do not infer success before the economic smoke and research jobs finish.

## Submission rule
Do not submit V5 simply because it opens all four quadrants or resembles a top replay. Submit only if the current 1.32.7 unseen holdout/final gates, V1 direct duel, meta-opponent suite, raw-exec, official loader and package/source equivalence all pass.

## NEXT CHAT COMMAND
User can type: `check PR kaggle`

The next AI should:
1. find the open PR beginning `[KAGGLE-V5]`,
2. read this checkpoint from its head branch,
3. inspect the latest V5.1 canonical workflow and public-meta workflow,
4. fix CI/economy failures before considering submission,
5. compare actual 1.32.7 V5 evidence to the live incumbent,
6. never expose `KAGGLE_API_TOKEN`,
7. never auto-submit a candidate that has not passed promotion/raw-exec gates.
