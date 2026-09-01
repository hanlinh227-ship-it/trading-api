# MT5 PROFITABLE RECOVERY CHECKPOINT — BTC V12.90 / XAU V63.90

Updated: 2026-09-02
Scope: MT5 BTCUSDc/XAUUSDc quant EAs only. This checkpoint does not change Bybit production authority.

## Current MT5 versions
- BTC: `BTC_Quant_24x7_v12_90_PROFITABLE_RECOVERY_FINAL.mq5`
- XAU: `XAU_Quant_Cent_Live_v63_90_PROFITABLE_RECOVERY_FINAL.mq5`

## Objective
Keep quantitative trading active while repairing a losing/locked book, with recovery driven first by realized winners, net-positive unwind and gross compression rather than by simply adding more exposure.

## Recovery priority
1. Bank valid standalone winners first and credit realized profit to healing reserve.
2. Net-positive winner/loser unwind.
3. Neutral gross compression using matched opposite BUY/SELL volume when self-funded after costs or safely funded by realized reserve.
4. Target-aware reserve-funded loser reduction.
5. Ticket-level invalidation cut.
6. Confirmed bounded rescue.
7. Single-layer hedge management.
8. Continuous core alpha with a separate recovery-compressed growth budget.

## Key architecture
- `TryNeutralGrossCompression()` reduces matched opposite inventory while approximately preserving net exposure.
- `RecoveryModeActive()` detects stressed/locked books using DD, gross utilization and gross/net lock ratio.
- `RecoveryGrowthScale()` keeps new alpha active but compresses growth exposure while recovery is active.
- Existing V12.80/V63.80 protections are retained: no opposite-core rescue, Q/agreement confirmation for rescue, target-gap-capped healing, ticket intelligence, continuous target compression and sublinear equity scaling.
- Legacy position ownership and strict no-broker-SL behavior are retained.

## Symbol-specific tuning
### XAU V63.90
- neutral compression starts around gross utilization 1.05 or gross/net lock ratio 5.0
- max matched compression 0.020 lot/action
- up to 45% of realized reserve available to fund compression deficit
- recovery growth floor 22%
- recovery mode from about 3% DD or gross utilization 1.05

### BTC V12.90
- neutral compression starts around gross utilization 1.15 or gross/net lock ratio 5.5
- max matched compression 0.050 lot/action
- up to 55% of realized reserve available to fund compression deficit
- recovery growth floor 28%
- recovery mode from about 4% DD or gross utilization 1.15

## Static audit
- XAU: 3478 lines; SHA256 `48144cf80e915fa8b45622f5d8367c22c1ab0122b744e8e7665b8e841c37e2a9`
- BTC: 3501 lines; SHA256 `bba0eb8674891c47950db8383a25402a014659a32e4149d84b3052ad6d986f99`
- balanced delimiters: PASS
- duplicate functions: 0
- duplicate inputs: 0
- dead inputs: 0
- semantic checks: 10/10 PASS

## Validation status
MetaEditor compiler is not available in the current runtime. Both EAs must be compiled in MetaEditor before live use. Static audit is not equivalent to compilation.

## Risk note
This architecture is designed to reduce destructive rescue loops and allow realized profits to be harvested during recovery. It cannot guarantee profitable recovery, eliminate drawdown, or prevent liquidation in every leveraged no-SL scenario.
