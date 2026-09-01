# MT5 SMART-GAP RECOVERY CHECKPOINT — BTC V12.92 / XAU V63.92

Updated: 2026-09-02 UTC+7

## Scope
This checkpoint applies only to the separate MT5/Forex branch. It does not change Bybit production authority or Cloudflare runtime.

## Current MT5 authority
- BTC: `BTC_Quant_24x7_v12_92_SMART_GAP_RECOVERY_FINAL.mq5`
  - SHA256: `6992525f2d6e2b2ed154039cb9e552c796c9c85a0c5b4f4885c794eae6189054`
- XAU: `XAU_Quant_Cent_Live_v63_92_SMART_GAP_RECOVERY_FINAL.mq5`
  - SHA256: `1179b98deb0229bc777196ff7031021fd16c8f2968c33ac3a8995abce955eaf4`

## Why V12.92 / V63.92 exists
V12.91/V63.91 fixed the hedge-spiral accounting error by making normal CORE and rescue sizing use `coreGap = TargetCoreNetLots() - coreNet` rather than total net including protective hedge.

The next requirement is to keep entry flow alive during recovery without reopening that failure. V12.92/V63.92 adds a separate Smart Recovery Gap Entry path.

## Smart-gap architecture
Normal CORE sizing remains authoritative:
`coreGap = TargetCoreNetLots() - coreNet`

Smart recovery gap sizing is separate:
`netGap = TargetCoreNetLots() - totalNet`

Smart-gap entry is allowed only when all of the following are true:
- recovery mode is active;
- signal is fresh;
- Q magnitude, factor agreement and combined edge score pass symbol-specific thresholds;
- entry direction reduces the real `|target-totalNet|` error;
- it does not create an opposite CORE stack;
- requested lot is capped by the actual total-net gap;
- symbol-specific max smart-gap shard and recovery growth compression remain active.

This prevents a huge legacy core hidden by a huge hedge from manufacturing a huge new core order, while still allowing a small alpha entry to correct a genuine total-net mismatch.

## Symbol tuning
### BTC V12.92
- Smart-gap Q >= 0.30
- Agreement >= 0.48
- Combined edge >= 0.39
- Fill fraction = 32% of real net gap
- Max smart-gap shard = 0.040 lot/action before scale compression

### XAU V63.92
- Smart-gap Q >= 0.36
- Agreement >= 0.54
- Combined edge >= 0.46
- Fill fraction = 25% of real net gap
- Max smart-gap shard = 0.015 lot/action before scale compression

## Recovery execution order
`winner harvest -> net-positive unwind -> neutral gross compression -> reserve-funded target healing -> invalidation cut -> confirmed bounded rescue -> hedge management -> SMART GAP entry -> normal core rebalance`

Hedge management gets the first chance to reduce excess hedge because that improves net while reducing gross. Smart-gap only adds after no hedge action was available.

## Preserved invariants
- continuous quantitative trading; no global cooldown added;
- anti-hedge-spiral core accounting;
- profit-first healing and reserve funding;
- neutral gross compression;
- ticket-level intelligence;
- target-aware funded loser reduction;
- confirmed bounded rescue;
- recovery/growth budget separation;
- sublinear equity scale-up;
- legacy position ownership/adoption;
- no broker SL architecture remains unchanged.

## Validation status
Static audit only:
- BTC: 3596 lines
- XAU: 3578 lines
- balanced delimiters: PASS
- duplicate functions: 0
- duplicate inputs: 0
- dead inputs: 0
- semantic architecture checks: 22/22 PASS

MetaEditor compiler is not available in the current runtime. Do not call V12.92/V63.92 compile-verified until MetaEditor shows 0 errors / 0 warnings.

## Risk note
Smart-gap recovery can keep valid alpha entries active during healing, but it cannot guarantee profitable recovery, non-liquidation, or uninterrupted profit. Leveraged no-SL trading retains tail-loss risk.
