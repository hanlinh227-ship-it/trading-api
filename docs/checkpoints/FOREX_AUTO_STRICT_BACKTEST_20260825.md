# FOREX AUTO — STRICT RANDOM WALK-FORWARD CHECKPOINT

Updated: 2026-08-25 UTC+7
Status: RESEARCH / PAPER_ONLY
Canonical Forex version at start: `FOREX-AUTO-0.3.0-PAPER`

## USER HARD TARGET
- Do not beautify results and do not cherry-pick periods.
- Every symbol must exceed 80% out-of-sample win rate.
- RR 1:1 and RR 1:2 are evaluated independently; BOTH must exceed 80% for EACH symbol.
- Failed windows, failed symbols and failed rounds must be retained as evidence.
- Backtests must be repeated on random periods, but a round may not be discarded merely because it fails.

## UNIVERSE
`EURUSD GBPUSD USDJPY USDCHF AUDUSD NZDUSD USDCAD EURJPY GBPJPY EURGBP XAUUSD`

## CURRENT BASELINE FAIL
Previous `FOREX-TWELVEDATA-WALKFORWARD-2`, seed `1085158877`, used 2 x 16-day random windows that overlapped.
EURUSD holdout: 14 trades, 6 wins, 8 losses, 42.86% WR; all 14 were RR 1:2 and RR 1:1 had zero samples.
Therefore the old gate is invalid for the new target and is retained only as FAIL evidence.

## STRICT V3 VALIDATION CONTRACT
Source: Twelve Data 5-minute historical data.
No lookahead.
60% prefix training / 40% sequential holdout inside each window.
Same-bar TP+SL is scored pessimistically as SL first.
Timeout is scored as loss.
Random windows inside a round must not overlap.
RR 1:1 and RR 1:2 are run as separate hypothetical evaluation profiles on every holdout test day.
Minimum test trades per symbol per RR: 18.
Strict gate: win rate >80%, not >=80%.
Global PASS requires all 11 symbols to pass both RR profiles.

Current batch configuration:
- 6 non-overlapping random windows
- 24 calendar days per window
- target >80%
- 18 minimum holdout trades per symbol/RR

Implementation commit: `8057c9c6bdd2064ade76788e7e3e633edf3a600e`
Workflow-strengthening commit: `9da1b2ae6c0c91a553c07c2b0029ee40e30ab355`

## ANTI-OVERFIT ITERATION RULE
Do not run seeds until one happens to pass and then report only that seed.
Each round uses a precommitted random sample and persists all results. If the round fails, inspect failure modes and allow the 3-AI Forex council to propose bounded strategy/filter changes. A changed strategy becomes a new research version and must be tested on fresh random windows that were not used to choose that change.

3-AI canonical roles from current Forex source:
- Claude: market scout / context / regime.
- DeepSeek: entry structure / execution critic.
- ChatGPT: lead trader / synthesis / final research decision.

AI may improve filters/selection logic but may not edit historical outcomes, weaken the >80% target, remove losing symbols, introduce lookahead, or suppress failed evidence.
