# CANONICAL SIMULATOR REVALIDATION IN PROGRESS

Audit discovered local study-001 used newer upstream source under the same 1.32.4 version label. Its PASS is research only. Clean-wheel source hash 9741c047... is now enforced; fixed candidate is being evaluated on fresh seeds in reports/pinned-study-002. Do not submit until this section is replaced by final canonical results.

# Kaggriculture V3 — final research handoff

- Repository: hanlinh227-ship-it/trading-api
- Branch: codex/kaggriculture-v3-meta-orchestrator
- PR: #216 — https://github.com/hanlinh227-ship-it/trading-api/pull/216
- PR title: [KAGGLE-V3] Meta Orchestrator and Robust Search System
- Base branch: main, 1346b69e57b6951b11ee77d1e6bb301a6c4d4369
- Source snapshot commit used by benchmark: b60a93d00765757880d8d928afdb2978374e6ea3
- Latest evidence commit SHA: resolve PR head; final evidence commit is being published.
- Kaggle submission performed: **NO**
- Promotion: **PASS — local engineering gate**, V1 live baseline unchanged.
- Kaggle raw-exec compatibility: **PASS**, official source-string loader **PASS**.
- Candidate SHA256: c1a7d713e347453829b6055781bafb0c49cd56b3792bcb356682ca56246f17df

## Files and architecture

Created reward-hunter/kaggriculture-v3/: incumbent.py, features.py, policy.py,
opponents.py, benchmark.py, search.py, promotion.py, package_submission.py,
raw_exec_test.py, generated main.py, champion.json, tests/test_system.py,
README.md, WRITE_LOCK.md, .gitignore, and reports/ including all study JSON.
Created .github/workflows/reward-kaggriculture-v3.yml.
Updated this handoff and CHECKPOINTS/KAGGRICULTURE_REWARD_SOLVER_CURRENT.md.
No V1/V2, production trading source, secret, or existing workflow changed.

V3 preserves a frozen quick-submit V1 fallback, builds pure own/public state features,
classifies strategic regime and opponent behavior, allocates workers using distance
and legal crop maturity, reserves targets/seeds, adapts market selling, and returns
terminal inventory to the shed for liquidation. The best ablation disables extra
harvest waiting. Eight related local opponent families and both seats are evaluated.
No competitor code, external data, replay collection, livestock acquisition or
fertilizer expansion is enabled. See README for verified official game mechanics.

## Exact tests and outcomes

Working directory: repository root. Python 3.12, official kaggle-environments 1.32.4.

1. `python -m compileall -q reward-hunter/kaggriculture-v3` — PASS.
2. `python -m unittest discover -s reward-hunter/kaggriculture-v3/tests -v` — 12/12 PASS.
   Includes maturity legality, terminal drop/sell, atomic seeds, no state leakage,
   parameter bounds, deterministic packaging, failure denominator, duplicate/missing
   evidence, shortened horizon, code identity, seed leakage, tail loss and no-op gates.
3. `python reward-hunter/kaggriculture-v3/benchmark.py --seeds 101 --families starter,incumbent --steps 120 --workers 2 --output reward-hunter/kaggriculture-v3/reports/smoke.json`
   — 4/4 valid. Smoke never grants promotion.
4. `python reward-hunter/kaggriculture-v3/benchmark.py --seeds 101,103 --workers 4 --output reward-hunter/kaggriculture-v3/reports/baseline-v3.json`
   — 32/32 valid, 20 wins; default candidate failed direct incumbent matches.
5. `python reward-hunter/kaggriculture-v3/search.py --candidates 8 --workers 4 --output reward-hunter/kaggriculture-v3/reports/study-001`
   — completed A–F and packaged/source comparison: 412 full simulator episodes,
   frozen best candidate, no E/F-driven retuning; promotion PASS.
6. `python reward-hunter/kaggriculture-v3/raw_exec_test.py` — PASS for delivered best main.py.
   Absent __file__, denied runtime file reads, stdlib-only AST, official last-callable loader.
7. Packaged main.py vs source on seed 997, both seats: exact margins/statuses/action
   counts/terminal inventory agreement, 2/2 wins, mean margin +5393.0.
8. Audited promotion replay over the six committed stage reports + runtime result — PASS.
9. Pattern scan of 1,239 tracked/source files — zero credential/private-key pattern
   findings. No secret values queried or printed. Pattern scan is not a proof against
   every possible credential format. Report: reports/secret-scan.json.
10. Clean minimal dependency venv: 12/12 tests PASS. Exact official wheel installed
    with --no-deps + jsonschema 4.25.1 / requests 2.32.5; unrelated optional game
    imports may log missing numpy, which does not affect Kaggriculture.

## Benchmark evidence

| Block | V3 wins/games | V3 mean margin | V3 worst | V1 wins/games | V1 mean margin |
|---|---:|---:|---:|---:|---:|
| D direct V1 duel | 8/8 | +5299.25 | +3917 | — | — |
| E holdout | 64/64 | +14804.1875 | +2744 | 52/64 | +8717.34375 |
| F final | 64/64 | +15210.328125 | +1229 | 49/64 | +8667.25 |

E/F V3 has zero invalid games and zero measured unit no-ops. Every family won 8/8
in each block. Full per-family and seat metrics: reports/RESULTS.md and study JSON.
V1 mean final cash: E 25053.59375 / F 24559.296875.
V3 mean final cash: E 30890.390625 / F 29968.671875.
V1 unit no-op rate: E .383875 / F .378541; V3 zero. Movement/idle remain proxies,
not illegal actions; rejected/partial market orders are not counted as unit no-ops.

Train seeds 101,103; D 211,223,227,229; E 7001,7003,7007,7013;
F 9001,9007,9011,9013. Each E/F block has four independent seeds, not eight.
Default V3's poor initial result is preserved, not hidden.

## Reproducibility and workflow

Raw JSON source_commit originally identifies checkout base because V3 files were
uncommitted during execution. reports/provenance-resolution.json verifies every
recorded source-file SHA256 against implementation commit b60a93d00765757880d8d928afdb2978374e6ea3.
No outcome was rewritten. Later audit edits affect runner metadata/seed selection/
kind validation, not the evaluated decision policy. Best main.py hash is above.

Workflow: Kaggriculture V3 - validation and research.
First CI run: 34451717476, validation SUCCESS, dispatch research SKIPPED.
Artifact: kaggriculture-v3-ci-34451717476 (ID to be recorded after final CI).
Final evidence revision CI: pending next push; must verify before submission review.
Local full-study artifacts are committed under reports/study-001, not external run IDs.

Dispatch supports configurable candidates and uses its GitHub run ID as a fresh
prospective study seed. CLI --study-seed 1919 reproduces study-001; it is NOT unseen
validation for future changes. Other study seeds deterministically select disjoint
blocks. Never choose a seed after viewing results or repeatedly tune on final seeds.
Only promotion PASS writes champion.json; branch auto-commit is scoped to V3 and
non-forced. No submit input/job/command or Kaggle token use exists.

## Failures, limitations and next action

Resolved during development: raw loader test initially referenced nonexistent
Environment.builtin_agents; corrected to the official build_agent contract and rerun.
Direct git push lacked authentication; authenticated GitHub connector published the
branch/PR successfully. Original default V3 failed V1, corrected by controlled ablation.
No unresolved local test failure. Full CI at final code revision still needs confirmation.

Most important remaining limitation: opponent suite consists of related heuristics and
only four independent seeds per holdout block; local dominance is not leaderboard
proof. No claim of top rank or statistical significance. New official observations,
simulator changes or incumbent revision require fresh validation before use.

Canonical Kaggle submission 56139689: last accessible log run 34450005641 at 07:27 UTC
reported COMPLETE / publicScore 600.0. Extra 56139862 was PENDING then, with no later
accessible confirmation. This is stale status, not a fresh rating check. No new status
workflow or Kaggle submission was invoked in this task. Rules page returned no readable
body, so optional public replay collection remains OFF.

Recommended next action: inspect final CI and exact candidate hash, independently
review promotion evidence and current competition rules/live baseline. Only then may
another authorized session decide if/when to submit. Do not merge this PR automatically.

## NEXT CHAT COMMAND

User will return to ChatGPT and type:

check PR kaggle

The next AI should:
1. Search open PRs in hanlinh227-ship-it/trading-api for a title beginning with [KAGGLE-V3].
2. Fetch that PR.
3. Read CHECKPOINTS/KAGGRICULTURE_V3_CODEX_HANDOFF.md from the PR head branch.
4. Inspect current GitHub Actions runs.
5. Compare V3 evidence against incumbent V1 and current Kaggle live baseline.
6. Fix any remaining CI/runtime issue before considering submission.
7. Never expose KAGGLE_API_TOKEN.
8. Do not submit a candidate that has not cleared the promotion/raw-exec gates.
