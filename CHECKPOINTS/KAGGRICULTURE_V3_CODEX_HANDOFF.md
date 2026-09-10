# Kaggriculture V3 handoff — validation in progress

Repository: hanlinh227-ship-it/trading-api
Branch: codex/kaggriculture-v3-meta-orchestrator
Base: main at 1346b69e57b6951b11ee77d1e6bb301a6c4d4369
PR title: [KAGGLE-V3] Meta Orchestrator and Robust Search System
PR number / URL: pending creation; this file will be updated after creation.
Latest commit SHA: resolve PR head; implementation commit is being created.

Implemented: isolated V3, frozen V1 fallback, state features and strategic regimes,
behavioral opponent classifier, action/market/endgame policy, eight opponent families,
paired benchmark, staged search, promotion checks, stdlib standalone packaging, raw
exec/official-loader gate, 12 unit tests and hosted workflow. See V3 README for economics,
objective normalization, seed blocks and exact reproduction commands.

Verified so far: compile PASS; 12 tests PASS; raw-exec and official loader PASS;
32-game default baseline valid 32/32 but failed V1 duel; structured best candidate
harvest_wait=false won 8/8 V1 direct games with mean +5299.25, worst +3917.
E holdout 64/64 wins, mean +14804.1875 across eight families. Paired V1 and final block
are still running. Promotion: NOT YET DECIDED. No current V3 champion authorized.
CI/run/artifact IDs: pending PR creation.
Kaggle submission performed: NO.
Current live baseline: 56139689 COMPLETE / 600.0 in last accessible 07:27 UTC log,
not a fresh current rating. 56139862 last observed PENDING; unverified afterward.

Known limitation: small independent seed count, related heuristic opponent families;
no statistical significance or leaderboard improvement claim. Public replay ingestion,
livestock/fertilizer acquisition are disabled. Existing Bybit lock and production source
are untouched. Code hashes capture the precommit working-tree source used by local runs.

Next action: finish E/F + package parity, record promotion and all results, push final
reports, inspect CI and replace this interim handoff before completing the session.

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
