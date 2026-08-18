# V77.18.16 — BALANCED ENTRY ALL MARKETS

Updated: 2026-08-18 UTC+7

## PURPOSE
Increase useful entry frequency across SIGNAL Forex, Metals, Futures and PROP without removing hard safety/data gates or reverting to generic methods.

## SIGNAL CHANGES
Signal engine is now V77.16.9 inside canonical runtime V77.18.16.

### Coverage
- Forex deep shortlist increased from 3 to 6 candidates per scan.
- Metals keep both XAUUSD and XAGUSD deep coverage.
- Futures keep NQ/ES leader analysis mirrored to MNQ/MES with micro risk sizing.

### Balanced soft gates
Hard gates remain: data readiness, V73/V74 authority, news context, structural SL, valid target, execution-authority separation, stale quote block, Futures $500 one-contract risk rule.

Soft gates were relaxed modestly:
- Forex trend RR floor roughly 1.22; mean-reversion about 1.12.
- Metal trend RR floor roughly 1.32; mean-reversion about 1.20.
- Futures RR floor 1.40.
- MARKET chase tolerance increased from 0.48 ATR to 0.65 ATR with RSI extreme guard retained.
- LIMIT geometry upper distance increased from 0.90 ATR to 1.05 ATR.
- trend/relative/generic continuation method-fit thresholds reduced moderately.
- M5 continuation RSI and structural trigger thresholds widened modestly.
- structural fallback method-fit floor reduced from 48 to 44.

These changes are designed to convert more technically valid setups into MARKET_PLAN/LIMIT_PLAN, not to fabricate executable broker orders.

## SIGNAL AUTO-SCAN
Previously cron auto-scanned Crypto only. V77.18.16 adds automatic non-crypto discovery:
- Crypto: existing every 5 minutes.
- Forex: once per hour at UTC minute 02.
- Metals: once per hour at UTC minute 12.
- Futures: every 15 minutes at UTC minutes 07/22/37/52.

Only valid MARKET_PLAN/LIMIT_PLAN notifications are sent. Dedup key `v771816:signal:auto_notify:*` prevents repeated alerts for the same setup for 30 minutes.

Non-crypto Signal remains analysis/plan only until a real execution authority/broker quote is connected; it must not be inserted into LIVE ORDERS merely from Twelve Data/Massive analysis.

## PROP CHANGES
A-tier quality is unchanged.
B-tier is intentionally more practical but lower-risk:
- near RR floor: max(1.40, symbol minRR - 0.35);
- distance allowance: up to 1.35x symbol-specific distance;
- B riskMultiplier reduced to 0.45;
- regular AUTO micro confirmation threshold reduced from 0.58 to 0.54;
- funding block, BTC filter where configured, per-symbol strategy, portfolio guard, anti-mirror, telemetry, native SL/TP and dynamic risk remain mandatory.

C-tier LIMIT threshold is slightly more permissive but still structural and funding-aware.

## NON-NEGOTIABLE STATE
Do not reset or migrate away from the existing `TRADING_STATE` namespace.
Keep all Signal LIVE ORDERS, PROP TK1/TK2 state, anti-mirror, position-manager, notification, execution/idempotency and PERSONAL state.
The new Signal notification dedup keys are additive only.

## DO NOT REGRESS
- Do not restore a single generic method across symbols/markets.
- Do not remove news/freshness/execution-authority hard gates to increase frequency.
- Do not convert non-crypto analysis-only plans into broker-executable LIVE ORDERS without a real broker quote/bridge.
- Do not increase PROP A frequency by lowering A quality; use B at reduced risk instead.
