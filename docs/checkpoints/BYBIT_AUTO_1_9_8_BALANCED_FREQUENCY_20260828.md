# BYBIT AUTO 1.9.8 — Balanced Frequency

Date: 2026-08-28

## Authority
- Runtime: `BYBIT-AUTO-1.9.8`
- Signal authority: closed 5m
- Context authority: closed 15m
- M1 entry authority: disabled
- Entry setup families: `TREND_PULLBACK`, `TREND_CONTINUATION`, `BREAKOUT`
- Final AI gate: strict Claude + Codex 2/2
- Post-AI quote revalidation: retained

## Frequency balance change
This release promotes the Aug 28 balanced-frequency tuning into a new runtime version. TREND_CONTINUATION discovery is moderately widened while quality gates remain intact:
- max 5m fast-EMA continuation distance: `1.30 ATR`
- minimum continuation volume ratio: `0.78`
- maximum continuation VWAP distance: `2.05 ATR`
- VWAP directional alignment remains mandatory
- adaptive threshold and profile minimum score remain mandatory
- regime direction-fit gate remains mandatory
- structural SL/TP and minimum RR remain mandatory
- portfolio risk, margin, correlation, direction cap and cooldown remain mandatory
- strict Claude + Codex 2/2 and post-AI freshness remain mandatory

## Diagnostics
The VPS Adaptive Entry Review is configured to use DEMO/public market routing so scan funnel diagnostics no longer require production private Bybit credentials. It records analyzed, rawCandidates, qualified, correlation rejections and selected setup details without placing an order.

## Risk locks retained
No daily trade quota was introduced. No hard risk caps were raised. No M1 authority was restored. No AI quorum was weakened. No production credential mode was changed by this release.
