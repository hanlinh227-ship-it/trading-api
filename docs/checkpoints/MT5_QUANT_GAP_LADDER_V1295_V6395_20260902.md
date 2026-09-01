# MT5 QUANT GAP LADDER — V12.95 / V63.95

Updated: 2026-09-02 UTC+7

## Scope
This checkpoint applies only to the separate MT5 Forex/Crypto EA branch. It does not change Bybit production authority.

## Current MT5 authority
- BTC: `BTC_Quant_24x7_v12_95_QUANT_GAP_LADDER_FINAL.mq5`
- XAU: `XAU_Quant_Cent_Live_v63_95_QUANT_GAP_LADDER_FINAL.mq5`

## Why this revision exists
Live BTC recovery showed that previous versions had fixed hedge-spiral, gross expansion and hedge persistence, but new entry actions during both normal and recovery phases still needed better quantitative quality scaling and better distribution across distinct price zones.

## V12.95 / V63.95 design
1. `QuantEntryQualityScale()` continuously scales lot size from:
   - absolute Q strength,
   - factor agreement,
   - regime add multiplier,
   - direction agreement.
   This is a soft quantitative sizing layer, not a global entry pause.

2. `NearestCoreSideDistanceATR()` measures the current price distance from the nearest same-direction CORE position in M15 ATR units.

3. `PriceVacancyScale()` reduces repeated entry size in already-crowded price zones and allows larger shards in genuinely new price gaps.

4. `QuantGapActionScale()` combines quality, price vacancy and recovery growth compression.

5. Applied to:
   - normal core rebalance,
   - Smart Recovery Gap Entry,
   - Dual-Loss Rescue sizing.

## BTC V12.95 tuning
- normal entry quality floor: 0.32
- normal vacancy target: 0.34 ATR
- recovery vacancy target: 0.58 ATR
- crowded-zone minimum scale: 0.24
- weak-edge action scale: 0.38

## XAU V63.95 tuning
- normal entry quality floor: 0.36
- normal vacancy target: 0.28 ATR
- recovery vacancy target: 0.46 ATR
- crowded-zone minimum scale: 0.20
- weak-edge action scale: 0.34

## Preserved architecture
- anti hedge-spiral core accounting
- target-aware hedge release
- hedge anti-overshoot cap
- interleaved harvest -> repair scheduling
- partial fundable neutral gross compression
- target-aware/core-gap funded healing
- Smart Gap total-net correction
- Q/agreement confirmed bounded rescue
- continuous target compression
- sublinear equity scale-up
- legacy position ownership
- strict no broker SL

## Static audit
BTC SHA256: `4caa93c4fee729d0749c6b33e1cf1caa555461bbdf9bbf7ce1dcf92f5f40f247`
XAU SHA256: `87f699a7126fae12e6229ad3751fa340b43ecadc05f88b95370c722b95ae32b1`

Balanced delimiters PASS. Duplicate functions 0. Duplicate inputs 0. Dead inputs 0. Semantic architecture checks 24/24 PASS.

## Validation warning
MetaEditor compiler is not available in the current ChatGPT runtime. Both EAs must be compiled in MetaEditor before live replacement. Static audit is not equivalent to compile verification.

## Risk note
This revision improves wrong-entry clustering control and recovery geometry, but cannot guarantee every entry is correct, guarantee profitable recovery, eliminate drawdown, or prevent liquidation in leveraged no-SL trading.
