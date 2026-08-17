# ITERATIVE 80WR RESEARCH V2

Updated: 2026-08-17 UTC+7
Provider market-data credits used in this entire iterative round: **0**

## Objective
Continuously improve Forex and Crypto as **two separate research systems** toward:
- TP/SL win rate >= 80%;
- average planned/effective RR between 1.0 and 1.5;
- positive expectancy;
- non-trivial held-out / chronological walk-forward sample;
- no future leakage;
- post-fill HOLD/CUT decisions may exclude CUT from displayed TP/SL WR, but total managed expectancy and CUT statistics must remain visible.

## Integrity stop rule
The target may NOT be manufactured by repeatedly tuning on already revealed validation outcomes. Once an independent block has been revealed, further tuning against that same block is development/research only and cannot be called a new blind result.

At the end of this round, the repository no longer contains a genuinely untouched, feature-complete per-trade Forex block suitable for validating a new selective entry rule. Later F11 evidence is aggregate/day-level only. For Crypto, the 12 corrected old dates plus Jul02/Jul04 V24 flow samples are now revealed. Further threshold changes on those same rows cannot honestly create a new independent 80% validation.

# FOREX — independent lineage only
Forex continues F8/V7 logic only. No BTC/breadth/crypto-profile features are allowed.

## Frozen broad comparator
F8 remains the broad stress benchmark:
- 20 trading days / 560 forced signals;
- MARKET 489 resolved, 248 TP / 241 SL;
- WR 50.72%;
- weighted expectancy about +0.233R;
- typical RR about 1.42–1.45.

## Strongest selective held-out candidate remains V7
Development May18–22:
- 26 trades;
- 21W / 5L = 80.77% WR;
- +0.945R;
- avg RR 1.425.

Held-out validation May25–29:
- 29 trades;
- 18W / 11L = **62.07% WR**;
- **+0.502R**;
- **avg RR 1.407**.

V7 remains the strongest non-trivial selective Forex candidate from the committed per-trade F8 data.

## V10 — nonlinear ML ensemble — REJECT
Run `32013940592`.
- baseline recovered: 231 rows / 10 dates, WR 49.78%, +0.199R, RR1.415;
- chronological walk-forward: 19 trades, 11W/8L = 57.89%, +0.403R, RR1.449;
- coarse genuine H+3 management: 1 CUT, TP11/SL7 among terminal trades, WR excluding CUT 61.11%, managed +0.428R.
- May26 collapsed to 14.29%, while May27 and May29 were each 83.33%.
Conclusion: nonlinear trade ranking did not beat V7. The large error source remained market/day-state recognition.

## V11 — Forex day-regime gate — SUPPORTING, NOT PROMOTED
Run `32014112682`.
- 17 trades / 4 active dates;
- 11W/6L = **64.71% WR**;
- +0.563R;
- RR1.412.
This is numerically above V7 WR but below the minimum non-trivial sample used for promotion. It also misclassified May26 as tradable and skipped May27, so day-regime recognition is not robust enough.

## V12 — legacy F4 multi-horizon/path gate — REJECT
Run `32014488805`.
Older committed F4 trade-level data were tested as an independent confirmation source.
- common-rule external validation: 43 trades, 12W/31L = 27.91%, -0.325R, RR1.461;
- chase-aware later dynamic validation: 9 trades, 1W/8L = 11.11%.
Do not revive the old F4 d6/d24/d72 path gate as a replacement for F8/V7.

## V13 — sequential H+3/H+6/H+12 HOLD/CUT — NO IMPROVEMENT
Run `32014813706`.
Used only genuine stored post-entry closes and only evaluated a checkpoint if `market.bars` showed the trade was still alive. No MFE/MAE or final-outcome leakage was used in a CUT decision.
- development V7 entries: 33, WR72.73%, +0.752R, RR1.431;
- validation V7 entries: 29, WR62.07%, +0.502R, RR1.407;
- frozen management rule `[None, None, -0.6]` generated **0 CUTs** in development and validation.
Conclusion: coarse 3h/6h/12h checkpoints do not rescue this V7 sample. This does not test missing H+1/H+2 snapshots.

## V14 — independent BUY/SELL branches — REJECT
Run `32014930533`.
BUY development rule became very strict:
- 17 trades, 15W/2L = 88.24%, +1.155R, RR1.448.
But held-out validation:
- 15 trades, 8W/7L = 53.33%, +0.325R, RR1.483.
SELL could not pass the development quality gate and was disabled.
Conclusion: tightening thresholds to make development exceed 80% overfits and reduces held-out quality.

## Later F11 aggregate evidence
F11 Jun08–12 is not per-trade feature-complete for applying new selective rules. It remains useful as an aggregate regime sanity check:
- Jun08 MARKET WR 65.38%;
- Jun09 63.64%;
- Jun10 56.00%;
- Jun11 39.13%;
- Jun12 34.62%.
Thus an aggregate day gate alone cannot demonstrate an 80% selective-entry system on that block.

## Forex conclusion
**Target NOT validated.**
Keep:
- F8 = broad benchmark;
- V7 = strongest selective per-trade candidate, 62.07% WR / +0.502R / RR1.407;
- V11 = supporting evidence that day-state gating is the next research direction, but n=17 is too small.
Reject V10/V12/V13/V14 as replacements.

# CRYPTO — independent lineage only
Crypto continues V24/Apr16 architecture only: BTC/risk regime + market breadth + HTF structure + momentum + M15/M5 path/anti-chase + fresh flow when actually available + per-symbol linked drivers. No Forex currency-factor logic is allowed.

## Parser correction — mandatory
A material research bug was discovered during this round:
- the generic `extract_crypto()` lineage in `offline_crossmarket_rolling_blind_v4.py` does not consistently propagate parent/day-level `priceBreadth`, `flowBreadth`, `flowCoverage`, and `marketRegime` into every child trade;
- the correct recursive context-inheritance pattern is preserved in `scripts/offline_crypto_regime_optimizer_v3_fast.py`.

Therefore **V28–V33 must NOT be used as promotion evidence where their result depends on the old generic parser/context fields**. Their code/history is retained for lineage, but the canonical Crypto base remains V24/Apr16. V35 was explicitly rebuilt with corrected parent-context inheritance.

## Surviving clean base
V24 five-date validation:
- 42.75% WR;
- +0.132R;
- original avg RR1.647;
- very unstable by date.

Apr16 clean MARKET holdout:
- 52 resolved;
- 27 TP / 25 SL = 51.92% WR;
- +0.350R original expectancy;
- 6h direction accuracy 80%;
- 24h direction accuracy 89.09%.
This remains important evidence that direction can be strong while barrier/entry adverse excursion remains weak.

## V34 — fresh-flow mode — PROMISING, BELOW TARGET
Run `32015123198`.
Directly parses the original `blind_backtest_v24.json`; it does not rely on the broken generic breadth parser.

Earlier Jul02 development:
- all 34 resolved: 24W/10L = 70.59%, +0.765R after conservative RR cap, RR1.5.

Later Jul04 full sample:
- 56 resolved: 41W/15L = 73.21%, +0.830R, RR1.5.

Frozen flow-compatible filter selected on Jul02, applied unchanged to Jul04:
- 37 trades;
- 29W/8L = **78.38% WR**;
- **+0.959R**;
- **RR1.5**.
This is the closest new clean Crypto result to the requested threshold, but remains below 80% and has only one later independent date for this exact flow mode.

## V34C — focused fresh-flow refinement — PROMISING, BELOW TARGET
Run `32015573168`.
Rule selection used Jul02 only; Jul04 remained the later check. Observable pre-entry dimensions were restricted to aligned OFI, score, HTF, relative strength, micro, breadth and BTC alignment.
- Jul02 selected development: 10 trades, 7W/3L = 70.00%, +0.750R, RR1.5;
- Jul04 frozen validation: **24 trades, 19W/5L = 79.17% WR, +0.979R, RR1.5**.
This misses the numerical 80% target by one outcome. Jul04 is now revealed; changing the rule after seeing 79.17% and reusing Jul04 as “blind” is forbidden.

## V35 — corrected symbol/regime walk-forward — REJECT AS REPLACEMENT
Run `32015273774`.
Correct context-inheritance parser, per-symbol/family priors and Crypto-only drivers.
- recovered all: 640 rows / 12 dates, 229W/411L = 35.78%, conservative RR cap1.5;
- expanding walk-forward selected: 28 trades / 6 dates;
- 8W/20L = 28.57%, -0.286R, RR1.5.
Do not replace V24/Apr16 with V35. Correcting the parser confirms that static/expanding profile-rule selection still does not generalize across old market states.

## Invalidated newer generic-parser branches
V31/V33 raw outputs and related V28–V32 profile/regime experiments are not canonical promotion evidence because the old parser could attach incorrect/missing day context. Preserve them only as research history. Do not quote their WR as a trusted improvement.

## Crypto conclusion
**Global target NOT validated.**
Keep two explicit modes:
1. `FLOW_AVAILABLE`: V24/V34 lineage; fresh actual flow is valuable. Best later one-day frozen result now 79.17% WR / +0.979R / RR1.5 on 24 trades (V34C), still below 80 and only one validation date.
2. `FLOW_MISSING`: keep conservative V24/Apr16 structure + BTC/breadth/regime + symbol-specific linked drivers + HTF/M15/M5 + NO TRADE. Corrected V35 proves current stored features do not support an 80% selector.

# Post-fill rolling management
Desired architecture remains H+1/H+2/H+3... HOLD/CUT using only state observable at each review.
- Old Crypto historical rows do not contain full hourly snapshots.
- Forex has genuine coarse 3h/6h/12h checkpoint data in some F8 records; V13 tested them honestly and found zero useful CUTs in the selected validation sample.
- Never derive a historical CUT from final MFE/MAE/outcome.

# What is needed for a legitimate next promotion test
To genuinely test a new candidate after this checkpoint, first freeze the next hypothesis and then use a **new, untouched, feature-complete block** containing:
- exact timestamped price path;
- entry-time market/regime features;
- H+1/H+2/H+3... review snapshots;
- point-in-time news/economic-calendar context where required;
- Crypto fresh flow/coverage flags and symbol-linked drivers;
- final TP/SL/CUT outcome.

Without a new untouched block, further tuning the current rows may be useful for diagnostics but cannot honestly establish a new 80% held-out system.

# Canonical status
- Forex: F8 broad comparator; **V7 best selective held-out = 62.07% / +0.502R / RR1.407**.
- Crypto: V24/Apr16 canonical base; **V34C FLOW_AVAILABLE later validation = 79.17% / +0.979R / RR1.5 on 24 trades**, promising but not globally validated and still below 80.
- Target >=80% on both markets: **NOT ACHIEVED**.
- Provider credits this round: **0**.
