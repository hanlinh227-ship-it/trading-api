# CRYPTO / BREAKOUT STATE

Updated: 2026-08-17 (UTC+7)

## Scope
Crypto trading research and MARKET-entry engine for coins supported by Breakout. Exchange availability is not enough: verify Breakout support before claiming a coin belongs to the tradable universe.

## Data architecture
- Twelve Data is not the preferred crypto source because Basic coverage is incomplete for many altcoins.
- Crypto research uses direct exchange REST APIs through GitHub runner.
- Route: Binance -> OKX -> Bybit; recent successful tests primarily used OKX.
- Direct crypto exchange fetches do not consume Twelve Data credits.
- Live freshness gates: requested/returned symbol match, fresh timestamp, bid/ask when available, stale=false, executionReady=true, symbolVerified=true, 5/5 analysis frames.
- Frames: D1/H4/H1/M15/M5; M1/latest for current execution price.

## Breakout universe
Official Breakout materials state roughly 62 crypto pairs. Previously observed/supported screener names include BTC, ETH, SOL, HYPE, SHIB, TRX, XRP, AAVE, ADA, ALGO, APT, ARB, ATOM, AVAX, BCH, BONK, CRV, DOGE, DOT, ETC, FIL, FLOKI, HBAR, INJ, WIF, WLD, AIXBT, ASTER, FARTCOIN, GRASS, IP, LIT, PUMP, VIRTUAL, XPL, ZEC and others. Re-verify the current universe whenever exact coverage matters.

## Surviving research family
Do NOT return to generic indicator stacking. Useful ingredients retained for research comparison are:
1. short-horizon momentum: 6h + 24h + 72h;
2. H4/H1 structure;
3. H4 EMA as context;
4. BTC relative strength;
5. M15 location / anti-chase / structure;
6. first minutes after the quarter-hour for execution context;
7. actual OKX taker BUY/SELL imbalance;
8. market-wide price breadth + flow breadth/median;
9. structure-based SL + ATR/profile floor;
10. dynamic RR based on setup quality/liquidity room.

No current version is validated as the final/main/live engine. V24 remains the diagnostic baseline because it preserves the strongest useful lineage while later V25/V26 hypotheses were rejected.

## Indicator roles
- EMA: trend/location only.
- RSI: momentum/exhaustion only; never standalone.
- ATR: volatility/SL floor.
- Volume/VWAP: participation/location when reliable.
- Price structure, momentum and actual flow are primary information sources.
- Funding/OI are not an active edge until historical coverage is reliable; previous Bybit derivatives tests had effectively unusable historical coverage.

## TP/SL philosophy
- Never force identical TP/SL distances across coins.
- SL: structural invalidation first; ATR/profile buffer only prevents unrealistic tightness.
- TP: liquidity room and setup quality; do not shrink TP simply to inflate win rate.
- Research RR has generally been around 1.6R–2.0R when justified.
- V23 proved cosmetic RR increases do not solve directional errors.

## Forced-MARKET stress rule
When the user asks for the forced blind stress test, every coin with valid historical data MUST receive MARKET BUY or MARKET SELL. No WAIT, NO TRADE or LIMIT. Entry/SL/TP must be frozen before future candles are revealed. This is a research stress condition, not necessarily the optimal live rule.

A future live `CHAOS / NO TRADE` gate may be valid, but it must be developed separately and must never be used to make forced-MARKET statistics look better.

## Version history and conclusions
- V3: forced MARKET baseline around 37.5% win at ~1.5R; negative expectancy.
- V4: indicator complexity worsened performance; rejected.
- V5/V6: regime/profile simplification recovered performance; useful baseline lineage.
- V7: >50% WR achieved by tiny TP, avg RR ~0.76R and negative expectancy; rejected.
- V8/V9: RR/breadth attempts not robust; rejected.
- V16/V17: short 6h–72h momentum beat longer horizons in development; V17 one true-blind sample ~43.4% WR at 1.5R with positive expectancy.
- V18–V21: high-RR/regime/fade variants unstable; rejected.
- V22: actual first-5m taker flow improved the same price-core baseline on Jul12/Jul10 but aggregate expectancy remained near/slightly below zero; evidence that flow can add information, not proof of a universal confirmation rule.
- V23: raising RR alone failed; rejected.

### V24 diagnostic baseline
Initial untouched evidence:
- Jul04: 41 TP / 15 SL = 73.21% WR, avg RR 1.679, +0.956R.
- Jul02: 24 TP / 10 SL among resolved = 70.59%, avg RR 1.641, +0.865R; 22 unresolved.
Both were `normal` regime.

Locked five-date June validation on the unchanged V24 engine:
- 278 trades, 262 resolved;
- 112 TP / 150 SL;
- 42.75% resolved WR;
- avg RR 1.647;
- expectancy +0.132R;
- flow coverage 62.2%.
Per date: Jun30 7.27% / -0.807R; Jun27 33.33% / -0.126R; Jun24 83.33% / +1.228R; Jun21 50.91% / +0.338R; Jun18 38.64% / +0.018R.
Conclusion: V24 is not robust enough for promotion and its regime guard is not validated.

Row-level June diagnostics:
- Jun30: 51/56 V24 decisions were SELL; SELL had 4 TP / 46 SL, BUY 0/5; even macro/flow agreement only 8% WR; |score|>=4 had 1 TP / 23 SL.
- Direct V24 SELL vs V25 BUY comparison on Jun30: among 51 changed sides, 46 hit SL in BOTH directions, 0 changed from V24-SL to V25-TP, and 4 previously winning SELLs became losing BUYs.
- Therefore Jun30 is primarily a **market-quality/timing/barrier failure**, not a simple wrong-direction failure.
- Jun27 showed flow agreement better than conflict and V24 regime flips all lost, motivating a clean macro-anchor hypothesis for testing.

### V25 development — rejected
V25 kept macro as direction anchor but added synchronized extreme breadth + same-direction OFI as a whole-market climax reversal rule. It was tested only on already-revealed June development dates.
- aggregate: 278 trades, 263 resolved, 111 TP / 152 SL, 42.21% WR, avg RR 1.624, +0.114R;
- Jun30 `sell_climax`: 0 TP / 56 SL = -1R;
- Jun27 improved to 38.89% / +0.019R.
Conclusion: **global climax reversal is rejected**. Do not revive it.

### V26 true-blind May — rejected
V26 isolated one hypothesis before May outcomes were read: BUY/SELL direction always followed the macro momentum/structure score; microflow and V24 regime context could change confidence/RR but could not flip direction. Five May cutoffs had no prior `2026-05-*` references in the repository search before locking.

Locked May result:
- 275 trades, 272 resolved;
- 79 TP / 193 SL;
- 3 unresolved;
- 29.04% WR;
- avg RR 1.646;
- expectancy **-0.235R**.
Per date:
- May30 32.73% / -0.145R;
- May27 25.93% / -0.311R;
- May24 21.82% / -0.429R (`distribution_reversal`);
- May21 43.64% / +0.163R;
- May18 20.75% / -0.460R.
Four of five dates were negative. **Macro-always-owns-direction is rejected as a general solution.** The Jun27 development improvement did not generalize.

## V26 May diagnostic lessons
These are diagnostic markers only; May is now development data and must not be reused as unseen validation.

Breadth buckets across the five May samples:
- extreme bearish breadth <=0.10: 107 resolved, 25 TP / 82 SL, 23.36% WR, -0.385R;
- middle breadth 0.30–0.70: 55 resolved, 24 TP / 31 SL, 43.64% WR, +0.163R;
- bullish breadth 0.70–0.90: 32.73% WR, -0.145R;
- extreme bullish breadth >=0.90: 21.82% WR, -0.429R.
This makes extreme breadth a strong **risk marker worth further study**, but not a finalized threshold because there are only five date-level samples.

Flow was not universally confirmatory on May:
- flow aligned with V26 macro side: 24.64% WR, -0.320R;
- flow conflict/neutral: 39.66% WR, +0.031R;
- flow unavailable: 26.90% WR, -0.301R.
Therefore do not hard-code “flow agreement = better trade” from June alone; the interaction is regime-dependent.

Barrier timing:
- overall median SL occurred around 39 M5 candles versus median TP around 70;
- May24 median SL 23 candles; May18 21.5 candles.
Combined with Jun30 two-sided SL behavior, this points the next research toward **market quality, entry timing and barrier geometry**, not more direction flipping.

## Current research baseline and next direction
Treat **V24-Core only as a diagnostic baseline**, not a validated live engine. V25 and V26 are rejected.

Next research should study pre-entry market-quality and timing features across already-revealed June + May development data without overfitting exact breadth thresholds. Candidate questions:
- can extreme breadth + volatility/structure identify whipsaw/terminal phases before entry?
- does observing longer than the first 5 minutes improve barrier survival in extreme conditions?
- does M5/M15 expansion, reclaim/failure or structural distance explain two-sided SL states better than direction scores?
- should live trading have a separate CHAOS/NO-TRADE quality gate while forced-MARKET research continues to issue BUY/SELL?

Only after a minimal theory-driven successor is frozen should it be tested on a completely untouched block, preferably April 2026. June and May must never again be counted as unseen validation for that successor.

## Active research dependency chain
Keep:
- `scripts/blind_backtest_crypto.py`
- `scripts/blind_backtest_crypto_v17.py`
- `scripts/blind_backtest_crypto_v22.py`
- `scripts/blind_backtest_crypto_v24.py`
- `data/blind_backtest_v17.json`
- `data/blind_backtest_v22.json`
- `data/blind_backtest_v24.json`
- `data/blind_backtest_v24_validation.json`
- `data/blind_backtest_v26.json` temporarily as key negative blind evidence / next diagnostic source
- `.github/workflows/blind-backtest-v24.yml`

Retired V25/V26 one-off scripts/workflows and diagnostics may be removed after conclusions are checkpointed; Git history preserves them.

## Live entry standard
For actual current signals, never blindly force MARKET across the universe and do not treat V24/V25/V26 as a validated live engine. Refresh the exact coin now; verify Breakout support; analyze D1/H4/H1/M15/M5 and event risk; check flow/market-quality context when available; issue MARKET only when live execution gates pass.

## Cross-chat continuation
New chat: read `MASTER_TRADING_STATE.md`, `CURRENT_HANDOFF.md`, this file, `CRYPTO_RESEARCH_ARCHIVE.md`, V24 and the retained validation evidence before changing the crypto method.