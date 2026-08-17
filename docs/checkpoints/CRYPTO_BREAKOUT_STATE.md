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
The best surviving direction is NOT indicator stacking. The preferred architecture is:
1. short-horizon momentum: 6h + 24h + 72h;
2. H4/H1 market structure;
3. H4 EMA bias as context/filter;
4. relative strength versus BTC;
5. M15 location / anti-chase / structure;
6. first 5 minutes around the quarter-hour when using the microflow engine;
7. actual OKX taker BUY/SELL trade imbalance as micro confirmation;
8. market-wide price breadth + flow breadth/regime as a higher-level guard;
9. structure-based M15 SL + ATR/profile buffer;
10. dynamic RR based on alignment/confidence/liquidity room.

## Indicator roles
- EMA: trend/location only.
- RSI: momentum/exhaustion only; never standalone.
- ATR: volatility/SL floor.
- Volume/VWAP: participation/location when data is adequate.
- Price structure, momentum and actual flow are primary.
- Funding/OI may be useful context if historical coverage becomes reliable, but previous Bybit historical derivatives tests had effectively zero usable coverage in the current pipeline and must not be credited as if active.

## Coin profiles
Do not use identical volatility assumptions for all coins. Existing profiles distinguish majors, L1/L2, DeFi, AI/high-beta, meme, and new/high-beta tokens. Meme/new/high-beta coins generally require wider volatility buffers than majors. Structure remains the real invalidation.

## TP/SL philosophy
- Never force the same TP/SL distance on all coins.
- SL: recent M15/H1 structural invalidation first; ATR/profile buffer only prevents an unrealistically tight stop.
- TP: use liquidity room and confidence; do not move TP closer merely to inflate win rate.
- Current research RR zone is roughly 1.6R-2.0R when structure and flow justify it. Higher RR requires stronger alignment; weak/conflicted cases should not be given a cosmetic 2R target.

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
- V22: adding first-5m actual taker order flow improved the price-only baseline on both blind samples tested, but overall expectancy remained near/slightly below zero. This is strong evidence that microflow adds information.
- V23: merely increasing RR did not fix directional errors; rejected as standalone improvement.
- V24: added market-level price breadth + flow breadth/regime guard while retaining V22 core. Two unseen samples were very strong: 2026-07-04 12UTC = 41 TP / 15 SL, 73.21% win, avg planned RR 1.679, expectancy +0.956R; 2026-07-02 12UTC = 24 TP / 10 SL among resolved, 70.59% resolved win, avg RR 1.641, expectancy +0.865R, but 22 trades unresolved. Both samples were classified `normal`, so these results support the core more than they validate the new guard itself.

## Current research baseline
Treat **V24-Core** as the most promising research direction, NOT yet a final proven live engine. Freeze the architecture and validate on multiple additional untouched dates before promotion.

V24-Core = 6h/24h/72h momentum + H4/H1 structure + H4 EMA + BTC relative strength + M15 anti-chase/location + first-5m OKX taker-flow + market breadth/flow regime + structural SL + dynamic 1.6-2.0R.

## Active research dependency chain
To keep the repository lean, the active tree now retains only the crypto code needed to reproduce/extend the current lineage:
- `scripts/blind_backtest_crypto.py`
- `scripts/blind_backtest_crypto_v17.py`
- `scripts/blind_backtest_crypto_v22.py`
- `scripts/blind_backtest_crypto_v24.py`
- key result files `data/blind_backtest_v17.json`, `data/blind_backtest_v22.json`, `data/blind_backtest_v24.json`
- current workflow `.github/workflows/blind-backtest-v24.yml`
Historical rejected experiments and one-off diagnostic/raw outputs were summarized before removal from the active tree. Their conclusions are preserved in `docs/checkpoints/CRYPTO_RESEARCH_ARCHIVE.md`; old Git commits still provide forensic recovery if ever required.

## Live entry standard
For actual current signals, do not blindly force MARKET across the universe. Refresh the exact coin now; verify Breakout support; analyze D1/H4/H1/M15/M5 plus relevant catalysts/news/token unlocks where material; check order-flow context when available; then issue MARKET only if the live request/rules allow it and execution gates pass.

## Important event context
Coin-specific token unlocks, listings/delistings, protocol upgrades, exploits, governance, regulatory news and major BTC/ETH market events should be treated as event-risk/context layers, not automatic BUY/SELL triggers.

## Cross-chat continuation
New chat: read `MASTER_TRADING_STATE.md`, `CURRENT_HANDOFF.md`, this file, `CRYPTO_RESEARCH_ARCHIVE.md` when historical context is needed, and the current V24 script/result before changing the crypto method.