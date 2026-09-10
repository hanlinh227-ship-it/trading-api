# Kaggriculture Reward Solver

Primary target: Kaggle Kaggriculture 2026.

The repository contains an original, self-contained policy plus automated local evaluation and parameter search. Research and optimization do not require Kaggle credentials because the official `kaggle-environments` package provides the simulator locally.

## Pipeline

1. Validate policy syntax and action contract.
2. Run deterministic seeded matches in both seats against built-in baselines.
3. Run evolutionary/random parameter search on the VPS.
4. Re-evaluate the best candidate over holdout seeds.
5. Write `champion.json` only when the candidate beats the incumbent gate.
6. Package `main.py` + `champion.json` into a Kaggle-ready tarball.
7. Submission is a separate guarded step and is never attempted unless the account has already joined the competition and a Kaggle API token is configured outside the repository.

## Safety / integrity

- Never commit Kaggle API tokens, cookies, credentials, or private competition data.
- Do not clone a competitor submission into the active agent. Public solutions may be studied only within their licenses and competition rules.
- Every candidate is tested in both player seats and across multiple seeds to reduce overfitting.
- A leaderboard score is not treated as proof of prize eligibility.

## Current policy family

The v1 solver is a dynamic crop-and-labor controller. It prioritizes survival watering, harvesting, weeds, efficient planting, daily hiring, selective land expansion, price-aware selling, late liquidation, and opponent-aware cash pressure. The tuner searches the economic thresholds and labor intensity while preserving action legality.
