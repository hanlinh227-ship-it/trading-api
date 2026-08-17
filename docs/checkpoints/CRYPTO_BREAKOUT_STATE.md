# CRYPTO / BREAKOUT STATE

Updated: 2026-08-17 (UTC+7)

## Scope
Crypto trading research and live MARKET-entry evaluation for the Breakout-supported universe. Exchange availability alone does not prove Breakout support; verify exact live coverage when it matters.

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
When explicitly requested, every symbol with valid historical data receives BUY or SELL with entry/SL/TP frozen before future candles are revealed. No WAIT/NO TRADE/LIMIT.

This is a research stress condition only. It is no longer the preferred live rule.

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
Random cutoff selected before outcomes: `2026-04-09T12:00:00Z`. Entry delayed until `12:15 UTC` after one completed M15 observation.

Result (`data/blind_backtest_v27_final.json`):
- universe 61;
- 55 symbols had valid historical frames;
- 6 historical-data failures: POPCAT, TAO, TON, FARTCOIN, GRASS, IP;
- 54 resolved;
- 11 TP / 43 SL;
- 1 unresolved;
- WR 20.37%;
- avg RR 1.60;
- expectancy -0.470R;
- 6h directional accuracy 21.82%;
- 24h directional accuracy 25.45%.

Pre-entry price breadth was 0.036, an extreme bearish market state. Historical OKX taker-flow coverage at this April cutoff was 0%, so the sample effectively tested the retained price/structure family without usable microflow.

TP symbols: BTC BUY, SOL SELL, HYPE BUY, TRX BUY, ARB BUY, ATOM BUY, BCH SELL, BONK SELL, FLOKI BUY, NEAR BUY, WLD BUY. KAITO SELL was unresolved.

## Final interpretation
Do not cherry-pick another date because V27 failed.
Evidence across June, May and the final random April sample says:
- forcing a position on every coin is not robust;
- bias ownership alone does not solve the problem;
- simply waiting one completed M15 does not solve it;
- extreme breadth repeatedly acts as a market-quality warning;
- actual flow is useful only when genuinely available/fresh and cannot be assumed to rescue every regime.

## Preferred live framework now
For current/live crypto requests:
1. refresh exact symbol and verify Breakout support;
2. assess BTC + market breadth/regime first;
3. analyze D1/H4/H1 structure and 6h/24h/72h momentum;
4. use M15/M5 for setup, trigger and anti-chase;
5. use actual order flow only when fresh/available;
6. define structural SL first;
7. require realistic TP/liquidity room;
8. permit `NO TRADE / CHAOS` when market quality is poor;
9. rank only the strongest few setups instead of forcing every coin.

This selective framework is preferred over further forced-all-market version churn unless the user explicitly requests more research.

## Rejected methods — do not return
- generic/redundant indicator stacking;
- tiny TP used to inflate WR;
- cosmetic RR changes;
- V25 synchronized whole-market climax reversal;
- V26 macro-always-owns-direction;
- V27 assumption that a completed M15 observation alone fixes forced-market performance.

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
- `.github/workflows/blind-backtest-v24.yml`
- `docs/checkpoints/CRYPTO_RESEARCH_ARCHIVE.md`

Rejected one-off V25/V26/V27 runners should be removed from the active tree after conclusions are checkpointed; Git history preserves exact code.
