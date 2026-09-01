# MT5 INTERLEAVED HEALING CHECKPOINT — BTC V12.93 / XAU V63.93

Updated: 2026-09-02 UTC+7

## Scope
This checkpoint is for the separate MT5/Forex branch only. It does not change Bybit production authority.

## Current MT5 authority
- BTC: `BTC_Quant_24x7_v12_93_INTERLEAVED_HEALING_FINAL.mq5`
- XAU: `XAU_Quant_Cent_Live_v63_93_INTERLEAVED_HEALING_FINAL.mq5`

## Why V12.93 / V63.93 exists
Live BTC evidence on V12.92 showed the EA harvesting winners and building healing reserve while old losing tickets were not being reduced quickly enough.

Concrete defects fixed:
1. **Harvest starvation** — harvest previously ran first every action opportunity and could repeatedly consume the broker-action slot before funded healing.
2. **All-or-nothing neutral compression shard** — the engine tested the maximum pair volume and skipped the pair if that one shard was too expensive, instead of stepping down to a smaller fundable partial pair.
3. **Reserve accounting asymmetry** — negative P/L on the first compression leg was not debited from the healing reserve.
4. **Single-leg healer used total-net gap** — after anti-hedge-spiral accounting, a large legacy core can be hidden by hedge while total net stays near target. The funded single-leg healer now uses `coreGap = target - coreNet`.

## V12.93 / V63.93 architecture
Recovery order is now interleaved:

`repair-turn -> harvest -> net-positive unwind -> neutral gross compression -> reserve-funded target healing -> invalidation cut -> bounded rescue -> hedge -> SMART GAP -> normal core`

After a profitable harvest in recovery, once reserve is economically meaningful, `g_recoveryRepairTurn=true`. On the next broker-action opportunity the engine tries:
1. neutral gross compression;
2. reserve-funded loser reduction;

before harvesting another winner.

## Neutral gross compression changes
- searches BUY/SELL matched volume downward by broker volume step;
- chooses the largest economically fundable partial pair rather than rejecting the pair because the configured max shard is too expensive;
- reserve use increases smoothly under DD stress;
- actual P/L from **both** close legs is applied to healing reserve;
- if the second leg fails, repair priority remains active.

## Symbol tuning
BTC V12.93:
- stress compression reserve-use ceiling: 82%
- repair-turn reserve threshold: 0.25% of reference equity, also subject to execution-cost floor

XAU V63.93:
- stress compression reserve-use ceiling: 72%
- repair-turn reserve threshold: 0.20% of reference equity, also subject to execution-cost floor

## Preserved invariants
- normal core sizing uses `coreGap`, not total net;
- SMART GAP uses only the real total-net mismatch and stays small/capped;
- no opposite-core rescue;
- rescue requires Q/agreement confirmation;
- ticket intelligence remains active;
- continuous growth/recovery separation remains active;
- sublinear equity scale-up remains active;
- legacy ownership remains active;
- no broker SL behavior remains active.

## Static audit
BTC:
- lines: 3669
- SHA256: `71112bf9fb06665850fe05fafa597d8ee49a5643adb1f73d8ee0331c0ff4173d`

XAU:
- lines: 3651
- SHA256: `7287b1dbd00ddaaba5b4ce8ef3412226db18710d706b75dd26200283dbd2037d`

Static checks:
- balanced delimiters PASS
- duplicate functions 0
- duplicate inputs 0
- dead inputs 0
- semantic architecture checks 22/22 PASS

## Verification requirement
MetaEditor compiler was not available in the build runtime. Do not call these files compile-verified until they are compiled in MetaEditor and show `0 errors / 0 warnings`.

## Risk statement
These fixes reduce concrete recovery scheduling/accounting conflicts. They do not guarantee profitable recovery, prevent all losses, or eliminate liquidation risk in leveraged no-SL trading.
