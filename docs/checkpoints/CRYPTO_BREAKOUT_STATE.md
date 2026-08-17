# CRYPTO / BREAKOUT STATE

Updated: 2026-08-17 (UTC+7)

## Scope
Crypto trading research and live entry evaluation for the Breakout-supported universe. Exchange availability alone does not prove Breakout support; verify exact live coverage when it matters.

## Data architecture
- Prefer direct exchange REST for crypto rather than Twelve Data.
- Live route: Binance -> OKX -> Bybit.
- Recent research primarily used OKX; historical trade-flow coverage becomes limited on older timestamps.
- Required live freshness: exact symbol match, fresh timestamp, executionReady/symbolVerified gates where implemented, D1/H4/H1/M15/M5 plus M1/latest for execution.

## Research universe
Current research list contains 61 symbols:
BTC, ETH, SOL, HYPE, SHIB, TRX, XRP, AAVE, ADA, ALGO, APT, ARB, ATOM, AVAX, BCH, BONK, CRV, DOGE, DOT, ETC, FIL, FLOKI, HBAR, INJ, JTO, JUP, KAITO, LDO, LINK, LTC, MOODENG, NEAR, ONDO, OP, ORDI, PENGU, PEPE, PNUT, POL, POPCAT, RENDER, S, STX, SUI, TAO, TIA, TON, TRUMP, UNI, WIF, WLD, AIXBT, ASTER, FARTCOIN, GRASS, IP, LIT, PUMP, VIRTUAL, XPL, ZEC.

## Surviving useful ingredients
Do not return to redundant indicator stacking. Useful research ingredients remain:
1. 6h/24h/72h momentum;
2. H4/H1 structure;
3. H4 EMA context;
4. BTC relative strength;
5. M15/M5 location, structure and anti-chase;
6. actual short-window taker flow when fresh/available;
7. market breadth/regime context;
8. structure-based SL with volatility floor;
9. realistic dynamic RR/liquidity room.

These are ingredients, not a validated all-market engine.

## Forced-MARKET stress test
When explicitly requested, every symbol with valid historical data receives BUY or SELL with entry/SL/TP frozen before future candles are revealed. This is a research stress condition only, not the preferred live rule.

## Key evidence
### V24
Initial Jul04/Jul02 blind samples were exceptional, but unchanged five-date June validation exposed instability:
- 278 trades, 262 resolved;
- 112 TP / 150 SL;
- 42.75% WR;
- avg RR 1.647;
- +0.132R;
- dates ranged from Jun30 7.27% / -0.807R to Jun24 83.33% / +1.228R.
V24 remains diagnostic only.

### V25 — rejected
Whole-market climax reversal failed; Jun30 became 0 TP / 56 SL. Do not revive it.

### V26 — rejected true-blind May
Macro-always-owns-direction failed:
- 79 TP / 193 SL;
- 29.04% WR;
- avg RR 1.646;
- -0.235R;
- 4/5 dates negative.

### V27 FINAL random blind — rejected
Cutoff `2026-04-09T12:00:00Z`, entry `12:15 UTC` after one completed M15.
Result (`data/blind_backtest_v27_final.json`):
- 55 tested of 61;
- 11 TP / 43 SL / 1 unresolved;
- WR 20.37%;
- expectancy -0.470R;
- 6h direction accuracy 21.82%;
- 24h direction accuracy 25.45%;
- price breadth 0.036;
- historical taker-flow coverage 0%.
Conclusion: waiting one completed M15 does not fix a bad market-state/directional sample.

### Final MARKET vs LIMIT blind comparison — Apr16
User explicitly requested an all-universe execution comparison using the surviving framework. Repo search confirmed `2026-04-16` had not been used before the rules/date were locked.

Frozen setup:
- observation starts `2026-04-16T12:00:00Z`;
- signal evaluated after one completed M15 at `12:15 UTC`;
- direction uses surviving V24/V22 architecture;
- MARKET enters at +15m observable price;
- LIMIT waits for a 0.35R pullback toward the same structural SL;
- LIMIT expires after 6h;
- LIMIT keeps the same absolute TP as MARKET;
- if TP is reached before LIMIT fills, cancel the pending order instead of allowing a late fill.

Result (`data/final_market_vs_limit_blind.json`):
- universe 61; tested 55;
- same 6 historical-data failures: POPCAT, TAO, TON, FARTCOIN, GRASS, IP;
- price breadth 0.964;
- historical taker-flow coverage 0%.

MARKET:
- 52 resolved;
- 27 TP / 25 SL;
- 3 unresolved;
- WR 51.92%;
- expectancy +0.350R;
- 6h direction accuracy 80.00%;
- 24h direction accuracy 89.09%;
- first 0.5R move favorable on 42 coins, adverse on 12, neither on 1.

LIMIT 0.35R:
- 42/55 filled = 76.36%;
- 3 hit MARKET TP before limit fill;
- 10 did not fill within 6h;
- among fills: 19 TP / 21 SL / 2 unresolved;
- WR among resolved fills 47.50%;
- avg effective RR 3.00R;
- expectancy among resolved filled trades +0.900R.

Execution interpretation:
- LIMIT did not improve win rate; its value came from improved entry geometry and much larger effective RR.
- LIMIT missed 8 MARKET winners: ARB, MOODENG, OP, ORDI, TIA did not pull back 0.35R within 6h; KAITO, TRUMP, AIXBT reached MARKET TP before the pending order could fill.
- LIMIT avoided 4 MARKET losses by not filling: FIL, JTO, WIF, XPL.
- DOT was MARKET unresolved and LIMIT not filled.
- About 20/25 MARKET SL trades still finished in the predicted direction after 24h. Many losses were therefore adverse-excursion/barrier problems rather than simply wrong direction.
- A fixed 0.35R LIMIT with the same SL cannot magically turn a filled MARKET loser into a winner if price continues through the same invalidation. The next meaningful live distinction is continuation-MARKET versus structurally expected pullback-LIMIT before entry.

## Final interpretation
Evidence across June, May and both April samples says:
- forcing a position on every coin is not robust across market states;
- bias ownership alone does not solve the problem;
- simply waiting one completed M15 does not solve it;
- extreme breadth alone is NOT an automatic reversal or no-trade signal: Apr09 extreme bearish breadth failed badly, Apr16 extreme bullish breadth produced very strong 24h directional accuracy;
- breadth must be combined with structure, continuation quality and adverse-excursion risk;
- entry path and barrier geometry are now as important as direction.

## Preferred live framework now
For current/live crypto requests:
1. refresh exact symbol and verify Breakout support;
2. assess BTC + market breadth/regime first;
3. analyze D1/H4/H1 structure and 6h/24h/72h momentum;
4. use M15/M5 for setup, trigger and anti-chase;
5. use actual order flow only when fresh/available;
6. define structural invalidation first;
7. classify execution as continuation-MARKET, pullback-LIMIT, or NO TRADE/CHAOS;
8. require realistic TP/liquidity room;
9. rank only the strongest few setups instead of forcing every coin.

## Rejected methods — do not return
- generic/redundant indicator stacking;
- tiny TP used to inflate WR;
- cosmetic RR changes without a better entry thesis;
- V25 synchronized whole-market climax reversal;
- V26 macro-always-owns-direction;
- V27 assumption that a completed M15 observation alone fixes forced-market performance;
- treating extreme breadth alone as an automatic reversal or automatic no-trade rule;
- blindly placing the same 0.35R LIMIT on every setup.

## Evidence/files to preserve
- `scripts/blind_backtest_crypto.py`
- `scripts/blind_backtest_crypto_v17.py`
- `scripts/blind_backtest_crypto_v22.py`
- `scripts/blind_backtest_crypto_v24.py`
- `data/blind_backtest_v17.json`
- `data/blind_backtest_v22.json`
- `data/blind_backtest_v24.json`
- `data/blind_backtest_v24_validation.json`
- `data/blind_backtest_v26.json`
- `data/blind_backtest_v27_final.json`
- `data/final_market_vs_limit_blind.json`
- `.github/workflows/blind-backtest-v24.yml`
- `docs/checkpoints/CRYPTO_RESEARCH_ARCHIVE.md`

One-off research runners/workflows should be removed from the active tree after conclusions are checkpointed; Git history preserves exact code.