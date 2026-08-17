# CRYPTO / BREAKOUT STATE

Updated: 2026-08-17 (UTC+7)

## Scope
Crypto trading research and MARKET-entry engine for coins supported by Breakout. Exchange availability is not enough: verify Breakout support before claiming a coin belongs to the tradable universe.

## Data architecture
- Twelve Data is no longer the preferred crypto source because Basic coverage is incomplete for many altcoins.
- Crypto is fetched directly by GitHub runner from exchange REST APIs.
- Route: Binance -> OKX -> Bybit. Recent successful tests have primarily used OKX.
- Direct crypto exchange fetches do not consume Twelve Data credits.
- Required freshness gates for live use: requested/returned symbol match, fresh timestamp, bid/ask when available, stale=false, executionReady=true, symbolVerified=true, 5/5 analysis frames.
- Frames: D1/H4/H1/M15/M5; M1/latest for current execution price.

## Breakout universe
Official Breakout materials state roughly 62 crypto pairs. Previously observed/supported screener names include BTC, ETH, SOL, HYPE, SHIB, TRX, XRP, AAVE, ADA, ALGO, APT, ARB, ATOM, AVAX, BCH, BONK, CRV, DOGE, DOT, ETC, FIL, FLOKI, HBAR, INJ, WIF, WLD, AIXBT, ASTER, FARTCOIN, GRASS, IP, LIT, PUMP, VIRTUAL, XPL, ZEC and others. Re-verify the current universe whenever exact coverage matters.

## Core research conclusion
The best surviving direction is NOT indicator stacking. The surviving architecture family is:
1. short-horizon momentum: 6h + 24h + 72h;
2. H4/H1 market structure;
3. H4 EMA bias as context/filter;
4. relative strength versus BTC;
5. M15 location / anti-chase / structure;
6. first 5 minutes around the quarter-hour when using the microflow engine;
7. actual OKX taker BUY/SELL trade imbalance as micro confirmation;
8. market-wide price breadth + flow breadth/regime as context;
9. structure-based M15 SL + ATR/profile buffer;
10. dynamic RR based on alignment/confidence/liquidity room.

The locked June validation showed this family still has information but is **not robust enough as a final all-market engine**. V24 must remain research-only until a new hypothesis fixes the cross-regime directional failures and then survives a completely untouched blind block.

## Indicator roles
- EMA: trend/location only.
- RSI: momentum/exhaustion only; never standalone.
- ATR: volatility/SL floor.
- Volume/VWAP: participation/location when data is adequate.
- Price structure, momentum and actual flow are primary.
- Funding/OI may be useful context if historical coverage becomes reliable, but previous Bybit historical derivatives tests had effectively zero usable coverage in the current pipeline and must not be credited as if active.

## Coin profiles
Do not use identical volatility assumptions for all coins. Existing profiles distinguish majors, L1/L2, DeFi, AI/high-beta, meme, and new/high-beta tokens. Meme/new/high-beta coins generally require wider volatility buffers than majors. Structure remains the real invalidation.

June V24 validation exposed large profile dispersion:
- major: 50.0% resolved WR, +0.321R expectancy;
- meme: 55.1%, +0.456R;
- alt: 60.0%, +0.600R, but only 10 resolved trades;
- L1/L2: 41.11%, +0.091R;
- new/high-beta: 44.44%, +0.200R;
- AI/high-beta: 33.33%, -0.133R;
- DeFi: 23.08%, -0.395R.
These are diagnostic observations only. Do not retrofit profile filters on the same June dates and then call them blind.

## TP/SL philosophy
- Never force the same TP/SL distance on all coins.
- SL: recent M15/H1 structural invalidation first; ATR/profile buffer only prevents an unrealistically tight stop.
- TP: use liquidity room and confidence; do not move TP closer merely to inflate win rate.
- Current research RR zone is roughly 1.6R-2.0R when structure and flow justify it. Higher RR requires stronger alignment; weak/conflicted cases should not be given a cosmetic 2R target.
- V23 already proved that raising RR alone does not fix directional errors.

## Forced-MARKET blind-test rule
When the user requests the stress test, every coin with valid historical data MUST receive MARKET BUY or MARKET SELL. No WAIT, NO TRADE or LIMIT. Entry/SL/TP must be fixed before future candles are opened. This is a research constraint, not necessarily the optimal live rule.

## Version history and lessons
- V3: forced MARKET baseline around 37.5% win at ~1.5R; negative expectancy.
- V4: added complexity/indicators; materially worse; rejected.
- V5/V6: improved regime/profile handling; V6 achieved positive expectancy on some old/new samples and became an important baseline.
- V7: achieved >50% win in one test by pulling TP too close; average RR ~0.76R and expectancy negative; rejected.
- V8/V9: attempts to restore RR / breadth did not robustly improve results; rejected.
- V16/V17: short 6h-72h momentum outperformed longer weekly horizons in development; V17 true blind achieved about 43.4% win at 1.5R with positive expectancy on one fresh sample.
- V18-V21: various high-RR/regime/fade approaches were unstable across dates; not promoted.
- OKX tradeflow probe proved historical public taker trades can be collected; example BTC 5-minute sample had 500 trades and large positive OFI, confirming the data path works.
- V22: adding first-5m actual taker order flow improved the price-only baseline on both blind samples tested, but overall expectancy remained near/slightly below zero. This remains evidence that microflow adds information.
- V23: merely increasing RR did not fix directional errors; rejected as standalone improvement.
- V24 initial evidence: Jul04 = 41 TP / 15 SL, 73.21% WR, avg RR 1.679, +0.956R; Jul02 = 24 TP / 10 SL among resolved, 70.59% resolved WR, avg RR 1.641, +0.865R, with 22 unresolved. Both were `normal` regime.
- V24 locked five-date June validation used the exact same engine without changing weights, regime thresholds, SL or RR. Aggregate: 278 trades, 262 resolved, 112 TP / 150 SL, 42.75% resolved WR, avg planned RR 1.647, expectancy +0.132R, flow coverage 62.2%.
- June samples were highly unstable: Jun30 7.27% WR / -0.807R; Jun27 33.33% / -0.126R; Jun24 83.33% / +1.228R; Jun21 50.91% / +0.338R; Jun18 38.64% / +0.018R.
- Jun27 was the first locked `distribution_reversal` sample and remained negative, so the V24 regime guard is **not validated as a protective edge**.
- Microflow agreement still showed incremental information: agreement = 44.87% WR / +0.235R at avg 1.759R versus conflict = 38.55% / +0.002R at 1.6R. It is useful context, not a complete directional solution.

## Current research baseline
Treat **V24-Core as a diagnostic research baseline, not a validated main/live engine**. The June batch disproved the idea that the exceptional Jul04/Jul02 performance generalizes consistently.

Keep the useful V24-Core ingredients for comparison:
6h/24h/72h momentum + H4/H1 structure + H4 EMA + BTC relative strength + M15 anti-chase/location + first-5m OKX taker-flow + market breadth/flow context + structural SL + dynamic 1.6-2.0R.

Do not tune V24 against Jun30/Jun27 and then reuse those dates as blind evidence. The next candidate must be theory-driven from diagnostics, frozen, and tested on a wholly untouched date block.

## Next research direction
Before creating V25, diagnose the two failure samples at row level, especially Jun30 and Jun27:
- whether macro direction, microflow and final side agreed or conflicted;
- which profiles and regimes concentrated the losses;
- whether the failure is continuation-vs-reversal classification, cross-sectional breadth, or coin-specific directional persistence;
- whether the current regime guard is over/under-reacting rather than simply moving its thresholds to fit these dates.

Only after that diagnosis should a minimal V25 hypothesis be frozen. The same June dates become development/diagnostic data after this point and must never again be counted as unseen blind validation for V25. Use a completely untouched block, preferably May 2026, for the next true-blind test.

## Active research dependency chain
Keep the current reproducible lineage plus key validation evidence:
- `scripts/blind_backtest_crypto.py`
- `scripts/blind_backtest_crypto_v17.py`
- `scripts/blind_backtest_crypto_v22.py`
- `scripts/blind_backtest_crypto_v24.py`
- `data/blind_backtest_v17.json`
- `data/blind_backtest_v22.json`
- `data/blind_backtest_v24.json`
- `data/blind_backtest_v24_validation.json`
- `.github/workflows/blind-backtest-v24.yml`

The one-off five-date validation script/workflow may be removed after this conclusion is checkpointed; Git history preserves them. Historical rejected experiments and one-off diagnostics remain summarized in `docs/checkpoints/CRYPTO_RESEARCH_ARCHIVE.md`.

## Live entry standard
For actual current signals, do not blindly force MARKET across the universe and do not treat V24 as a validated live engine. Refresh the exact coin now; verify Breakout support; analyze D1/H4/H1/M15/M5 plus relevant catalysts/news/token unlocks where material; check order-flow context when available; then issue MARKET only if the live request/rules allow it and execution gates pass.

## Important event context
Coin-specific token unlocks, listings/delistings, protocol upgrades, exploits, governance, regulatory news and major BTC/ETH market events should be treated as event-risk/context layers, not automatic BUY/SELL triggers.

## Cross-chat continuation
New chat: read `MASTER_TRADING_STATE.md`, `CURRENT_HANDOFF.md`, this file, `CRYPTO_RESEARCH_ARCHIVE.md`, the V24 script and both V24 result files before changing the crypto method.