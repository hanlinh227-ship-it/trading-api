# SIGNALHUB_V3_CHECKPOINT_06 — Crypto Stability + Simple UI

## Scope
SignalHub is Crypto-only. Forex signal generation remains disabled. Two engines only: CRYPTO SCALP and CRYPTO SWING.

## Parent
- V3.13 final source: `d9af4382b7fe898bc055090e6fb9bd4e17c08407`
- Working branch: `signalhub-v314-simple-ui-stability`
- Backend target: `SIGNALHUB-V3-GATEWAY-3.14.0`
- Android: `3.14.0` / versionCode 20

## Production audit before tuning (2026-09-09)
Infrastructure was healthy: 4 active Crypto signals / 4 unique symbols, 2 SCALP + 2 SWING, server monitor running, 460 provider quotes in the sampled monitor cycle, no monitor errors. Trading evidence was NOT proven. SCALP had only 4 resolved trades and all 4 were SL (-4R); SWING had 0 resolved trades. The SCALP sample is too small for a reliable win-rate estimate, but the four losses are a concrete warning and motivated this tuning.

## V3.14 engine changes
- No numeric setup score and no time/cooldown admission gate.
- SCALP no longer accepts a generic trend/EMA pullback alone. New trades need liquidity sweep/reclaim, displacement+structure reclaim, or confirmed breakout evidence.
- SWING requires H4/D1 direction plus H1 execution confirmation.
- Secondary provider must positively confirm direction; neutral/opposing is not called confirmation.
- Provider bid/ask is used for pending activation and exit tracking.
- Pending setup cancels when its structural invalidation is broken before entry, not only after reaching the wider SL.
- Higher turnover and tighter spread requirements for new entries.
- Portfolio risk clusters prevent correlated meme-beta signals from filling the book: maximum one MEME exposure active at a time; max two in another risk cluster.
- Performance remains resolved TP/SL only. No predicted win-rate is shown.

## UX/UI
- Four tabs only: Home / Signals / Stats / Settings. Alerts remain Android system notifications.
- System font instead of monospace everywhere.
- Vector app/logo/navigation/crypto assets are bundled locally.
- Home is one-glance: connectivity, SCALP/SWING counts, real closed-trade evidence, latest signal.
- Signal cards show only Symbol, Side, Order state, Current, Entry, SL, TP3, progress and one short regime line. Full TP ladder/reasoning stays in detail.
- LIVE uses red/green risk gauge; pending LIMIT/STOP uses yellow distance-to-entry gauge.

## Stability truth
`/v3/stability` separates infrastructure health from trading evidence. Infrastructure can be STABLE while the strategy sample remains NOT_YET_PROVEN. Do not call the strategy statistically stable until each style has a meaningful resolved sample.

## Rollback
Rollback source remains V3.13 branch/tag and APK if V3.14 production validation fails.
