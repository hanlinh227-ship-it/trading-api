# BYBIT AUTO 1.9.7 — ENTRY FREQUENCY BALANCE

Updated: 2026-08-28 UTC+7
Status: SOURCE CHANGE PENDING VALIDATION/DEPLOYMENT

## Problem observed
Recent adaptive entry diagnostics showed a broad scan with 110 analyzed symbols and zero qualified setups. Source audit found candidate starvation primarily before the final 2AI gate: symbol profile minimum scores were effectively 74–76 even though the adaptive floor is 66, and breakout chase allowances were narrow enough that otherwise valid closed-5m breakouts could disappear before reaching the quality/AI stages.

## Changes
- Runtime version bumped to `BYBIT-AUTO-1.9.7`.
- Preserve closed 5m signal authority + closed 15m context. M1 remains disabled as signal authority.
- Preserve deterministic spread, liquidity, regime, VWAP-distance, breakout-volume, structural SL/TP, minimum RR, sizing, portfolio risk/margin, correlation and post-AI freshness gates.
- Preserve strict Claude + Codex 2/2 final-entry review. No third provider/fallback is added.
- Reduce profile minimum score only moderately while staying above the global adaptive floor:
  - BTC/ETH: 74 -> 72
  - SOL/XRP: 75 -> 73
  - dynamic core/high/filtered profiles: 74/75/76 -> 72/73/74
- Increase per-profile `maxChaseAtr` moderately so a closed-5m breakout has more time to survive into final review:
  - BTC 0.52 -> 0.66
  - ETH 0.54 -> 0.68
  - SOL 0.58 -> 0.72
  - XRP 0.56 -> 0.70
  - dynamic profiles raised to 0.68/0.72/0.70 respectively.

## Explicit non-changes
- No daily quota/target was added.
- No M1 entry authority.
- No weakening of structural SL/TP or minimum RR.
- No removal of strict 2AI quorum.
- No weakening of post-AI quote drift validation.
- No increase in leverage/risk limits.
- No change to Smart CUT.
- No reset of `TRADING_STATE` or learning history.

## Expected effect
More technically valid 5m/15m candidates should reach sizing/risk/2AI review, especially BTC/ETH/SOL/XRP and high-liquidity symbols, without turning the system into an M1/noise scalper. This change intentionally targets candidate starvation rather than bypassing downstream safety gates.

## Deployment authority
Do not claim this version LIVE from source alone. Required: validation workflow PASS, deployment workflow PASS, `/runtime/contract` revision/version match, and `/bybit/health` authenticated runtime verification.
