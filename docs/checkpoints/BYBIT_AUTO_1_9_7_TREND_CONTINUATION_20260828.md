# BYBIT AUTO 1.9.7 — TREND CONTINUATION ENTRY EXPANSION

Updated: 2026-08-28 UTC+7
Status: SOURCE CHANGE PENDING VALIDATION/DEPLOYMENT

## Problem
After the profile score/chase tuning, candidate starvation can still occur before sizing/2AI because the deterministic detector only accepts a narrow TREND_PULLBACK or a long-lookback BREAKOUT. A valid 5m continuation aligned with 15m trend can therefore return NO_SETUP before downstream safety gates are reached.

## Change
- Runtime version: `BYBIT-AUTO-1.9.7`.
- Keep closed 5m signal + closed 15m context; M1 remains disabled for signal authority.
- Add `TREND_CONTINUATION` as a third deterministic setup type alongside `TREND_PULLBACK` and `BREAKOUT`.
- Continuation requires 15m trend alignment, 5m fast/slow EMA alignment, a closed candle in the trend direction, no excessive distance from fast EMA, VWAP alignment, volume ratio >= 0.85 and VWAP distance <= 1.85 ATR.
- Continuation starts at score 73 and still must pass the existing adaptive threshold, regime gate, structural SL/TP, minimum RR, sizing, portfolio risk/margin, correlation, strict Claude+Codex 2/2 review and mandatory post-AI quote freshness validation.

## Non-changes
- No M1 entry authority.
- No daily profit target or trade quota.
- No weakening of hard risk/leverage/portfolio limits.
- No change to anti-sweep SL/TP or Smart CUT.
- No bypass of strict 2AI.
- No reset of TRADING_STATE or learning history.

## Expected effect
Increase legitimate candidate flow, especially in BTC/ETH/SOL and other liquid trending markets, without converting the system into a noisy short-horizon scalper.

## Deployment requirement
Do not claim runtime active until GitHub validation/deployment succeeds and deployed `/runtime/contract` + `/bybit/health` match the merged revision/version.
