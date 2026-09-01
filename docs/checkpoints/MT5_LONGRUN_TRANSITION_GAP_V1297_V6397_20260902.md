# MT5 LONG-RUN TRANSITION GAP — BTC V12.97 / XAU V63.97

Updated: 2026-09-02 UTC+7

## Purpose
Final theoretical baseline for extended forward running of the MT5 BTCUSDc/XAUUSDc no-broker-SL quantitative EAs.

## Current files
- BTC: `BTC_Quant_24x7_v12_97_LONGRUN_TRANSITION_GAP_FINAL.mq5`
- XAU: `XAU_Quant_Cent_Live_v63_97_LONGRUN_TRANSITION_GAP_FINAL.mq5`

## Main architecture
- continuous quant core flow remains active
- anti-hedge-spiral CORE accounting uses `coreGap = target - coreNet`
- target-aware hedge release and hedge anti-overshoot cap
- interleaved profit-to-heal scheduler
- partial fundable neutral gross compression
- reserve-funded loser healing
- ticket-level invalidation
- bounded rescue with Q/agreement confirmation
- Quant Gap Ladder
- Vacancy Opportunity Entry
- Smart Gap Entry
- NEW Transition Gap Entry
- sublinear equity scale-up
- legacy ownership preserved
- broker SL remains disabled; EA-side healing/cuts remain active

## Transition Gap Entry
Designed for the case where legacy CORE points one way, but current quant target + effective-net error + a genuine price vacancy support a small corrective entry in the opposite direction.

Rules:
- recovery active
- fresh signal
- sufficient |Q|, agreement and edge
- genuine ATR vacancy
- entry must reduce `|target-totalNet|`
- volume capped by real net error and symbol-specific max shard
- deep-DD scaling reduces shard size further
- order is booked as protective/transition inventory (`hedge=true`), not as a second opposite CORE stack
- projected gross must remain inside the compressed gross envelope

### BTC V12.97
- transition |Q| >= 0.22
- agreement >= 0.34
- edge >= 0.28
- vacancy >= 0.60 ATR
- fill 16% of real net gap
- max transition shard 0.018 lot before scaling
- deep recovery multiplier 35%

### XAU V63.97
- transition |Q| >= 0.28
- agreement >= 0.42
- edge >= 0.34
- vacancy >= 0.50 ATR
- fill 12%
- max transition shard 0.008 lot before scaling
- deep recovery multiplier 30%

## Recovery priority
winner harvest -> target-aware hedge release -> neutral gross compression -> reserve-funded healing -> invalidation cut -> bounded rescue -> hedge management -> TRANSITION GAP -> VACANCY OPPORTUNITY -> SMART GAP -> normal CORE

## Audit result
- BTC: 4107 lines, SHA256 `4331d81c77b72ff5e7fa78299af7f2824a6ddb6257f6f8b055f1270f3312415f`
- XAU: 4089 lines, SHA256 `57e76d52ac9adb5584f680b1fbacabb48fc777a5cbdf451deaa10bde8e4916c7`
- balanced delimiters PASS
- duplicate functions 0
- duplicate inputs 0
- dead inputs 0
- semantic architecture checks 26/26 PASS

## Important limitation
MetaEditor compiler was unavailable in the patching runtime. These files must be compiled in MetaEditor before live use. Static audit is not compile verification.

No leveraged no-SL architecture can guarantee profitable recovery, non-liquidation or uninterrupted profit. This checkpoint records the final theoretical baseline for the next extended forward-test period.
