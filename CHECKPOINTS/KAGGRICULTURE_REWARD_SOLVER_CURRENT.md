# KAGGRICULTURE REWARD SOLVER — CURRENT CHECKPOINT

Updated: 2026-09-11 00:29 +07

## Project / integrity
- Repository: `hanlinh227-ship-it/trading-api`.
- Competition: Kaggle Kaggriculture.
- Promotion/runtime evidence uses `kaggle-environments==1.32.7`.
- `KAGGLE_API_TOKEN` remains only in GitHub Actions secrets; never request, print or commit it.
- No hidden Kaggle state, forced matchmaking, quota bypass, multi-accounting, duplicate/re-roll spam or copied private opponent action tapes.

## Live Kaggle
- Accepted V1 submission: `56139689`, COMPLETE at last confirmed check.
- V5.4 live-shadow submission: `56148022`, last confirmed PENDING; recheck before making a current score/rank claim.
- Old tar submissions `56139515` and `56139862` are ERROR paths and must not be reused.
- Kaggle matchmaking frequency is controlled by Kaggle; local challenger loops cannot force live episodes.

## Historical anchors
- V1 PR #215 merged at `0624e73c079b3097b1b97f69279ea625bd77ec53`.
- V2 Fast lost direct V1 promotion.
- V3 PR #216 and V4 PR #217 remain historical research lanes.
- V5 PR #218 merged at `6435be98d2196f3765f0a07ac6f797d0eec02560`.
- Strong V5.2 current-engine run `34459804967`: Stage C 48/48 wins; direct V1 8/8; holdout 63/64 wins; final 64/64 wins; raw-exec/official-loader/package equivalence PASS. Its promotion was blocked by a legacy baseline benchmark bug plus deliberately strict campaign utilization/inventory gates, not by candidate runtime invalidity.
- V5.3 fixed legacy baseline adaptation, current-engine workflow provenance and continuous public-meta research on main.

## ACTIVE CHALLENGER — V5.7 Adaptive Agro-Economic Learning
- Branch: `research/kaggriculture-v5-4-rank-livestock`.
- PR #219: `[KAGGLE-V5.7] Adaptive Agro-Economic Learning Rank Engine`.
- PR remains OPEN + DRAFT; do not merge until a full canonical V5.7 research cycle is reviewed.
- Dedicated checkpoint: `CHECKPOINTS/KAGGRICULTURE_V5_7_AGRO_ECONOMIC.md`.

### Canonical V5.7 path
- `economic_reasoning.py`: dynamic market/town/scarcity economic model.
- `policy_v57.py`: runtime crop/animal/sale coordinator layered over proven base policy.
- `benchmark_v57.py`: canonical current-engine evaluator with economic telemetry.
- `package_submission_v57.py`: canonical self-contained V5.7 packaging.
- `agro_reasoning.py`: failure-cause attribution + farming recovery hypotheses.
- `search_rank.py`: canonical adaptive research search, now importing V5.7 evaluator/packager.
- `monotonic_rank.py`: accepted-capital high-water guard + taboo/repeated-failure memory.

Temporary `value_overlay.py` / `agent_factory.py` files are transitional and are NOT the canonical V5.7 research path.

### V5.7 learning doctrine
Every local result is converted into both statistical evidence and domain reasoning. Failure labels include execution/no-op/waste, routing, under-utilization, fourth-quadrant overreach, labor/hiring cost, herd/feed stress, herd capital not converted, crop-only income ceiling, idle structures, terminal inventory, capital starvation, expansion cash drag, feed-market dependency, poor price capture, premium supply/price mismatch, failure to compound and catastrophic economics.

Repeated causes produce materially different recovery hypotheses rather than replaying the same losing investment pattern. Candidate ordering is:
`accepted champion -> archived personal champions -> current meta prior -> learned personal patch -> failure-derived recovery hypotheses -> public-top structural priors -> exploratory mutations`.

### Production and price must improve together
The official market is endogenous: selling adds shared inventory and can lower price; town demand / supported market buys remove inventory and can create scarcity. V5.7 therefore models projected town drain and resource-specific glut sensitivity, chooses marginal crop/animal capital by expected realizable value, preserves WHEAT as the herd feed backbone, clips/holds premium sales when dumping would destroy price, sells when scarcity/cash/capacity/endgame conditions justify it, and avoids unjustified late expansion.

### Public top lessons are priors, not imitation
Public high-Elo evidence has repeatedly shown 3-quadrant livestock-heavy structures around 9 cows, 4-5 sheep and roughly 9-10 hands. Public discussions also report strong heuristic/fixed-policy lineages and indicate the fourth quadrant is often an ROI trade-off rather than mandatory. V5.7 includes these only as starting structural hypotheses; our personal failure/success memory is evaluated first and any public prior can be rejected by local evidence.

### Monotonic accepted-capital rule
Exploratory games may lose so the search can learn. A losing challenger can never replace the accepted champion or reach live promotion. Fixed regression seeds `7319,29077`, all local opponent families and both seats compare candidate vs accepted champion. Replacement requires a real positive money gain and no paired regression in money, margin, win rate, worst tail, catastrophic rate, terminal inventory or no-op.

Exact rejected configurations and repeated failed investment patterns are remembered. Regression/stagnation automatically widens/deepens future search up to the existing 8..64 candidate envelope.

## Latest validation / active run
- Canonical V5.7 validation run `34508086126`: SUCCESS.
- Passed compile + all tests, self-contained package + raw-exec, V5.7 economy smoke both seats, and source/package episode equivalence.
- Research in that run was skipped because it was a PR event, as intended.
- First canonical V5.7 push research run: `34508180760`, triggered by commit `46265eea01e691645bc72a2ccf43423c95e2a910`; queued/starting under the non-cancelling single-writer learning group.

## Next action
1. Let only one V5.7 research writer run; do not create redundant full runs.
2. When `34508180760` completes, inspect `AGRO_REASONING`, economy telemetry, direct V1 duel, unseen holdout/final, capital-regression candidate vs accepted champion, promotion reasons and `NEXT_ROUND`.
3. If rejected, keep champion and use the recorded failure causes to generate a materially different next hypothesis; do not lower gates to manufacture progress.
4. If strict + monotonic gates both pass, verify exact candidate hash/package and live Kaggle state before guarded promotion.
5. Keep PR draft until full V5.7 evidence is reviewed.
