# DATA / INFRA STATE

Updated: 2026-08-17 (UTC+7)
Repo: `hanlinh227-ship-it/trading-api`

## Core repository files
- `request.json`: requested symbol / id trigger.
- `.github/workflows/fetch-market.yml`: main current-symbol market-data workflow.
- `.github/workflows/scan-forex.yml`: existing 28-pair Forex scan infrastructure.
- `.github/workflows/backtest-market.yml`: reusable strict anti-lookahead single-symbol backtest infrastructure.
- `scripts/fetch_crypto.py`: direct crypto exchange fetcher.
- `scripts/blind_backtest_forex_f2.py`: active efficient Forex cross-pair research engine.
- `data/blind_backtest_forex_f2.json`: retained F2 blind result.
- `data/status.json`: validated current output.
- `data/latest.json`: raw/full current-symbol output.
- Active crypto lineage: base + V17 + V22 + V24 and retained validation evidence described in crypto checkpoints.

## Cloudflare / Twelve Data
Cloudflare Worker: `forex-chart-api`.
Twelve Data is primarily used for Forex/metals/cash-index routes, subject to plan entitlement.
Do not spend Twelve Data credits on crypto when direct exchange REST works.

Current plan context used by the project:
- Basic plan has 8 API credits/minute and 800/day at the time of the 2026-08-17 verification.
- `/time_series` costs 1 API credit per symbol.
- Batch requests reduce HTTP overhead but do not reduce symbol-credit consumption: seven symbols in one `/time_series` batch still cost seven credits.
- Re-check provider documentation before relying on these plan limits in the future because pricing/limits can change.

## Efficient Forex research architecture — validated technically
The old generic backtest/live path can fetch D1/H4/H1/M15/M5/M1 separately. That remains reusable for deep single-symbol analysis, but it is too credit-expensive for repeated 28-pair research.

F1/F2 proved a cheaper universe approach:
1. Fetch one sufficiently long M15 `/time_series` per Forex pair.
2. Batch at most seven pairs under the current 8-credit/min Basic quota and wait between groups.
3. Derive H1 and H4 OHLC locally from M15.
4. Derive 6h/24h/72h cross-currency strength locally from the same cached data.
5. Run all blind decisions and future-path evaluation locally after the dataset is fetched.
6. Do not commit raw 28-pair historical dumps; retain only the compact result JSON and active engine.

A 28-pair historical dataset therefore targets 28 Twelve Data symbol credits, independent of the number of locally calculated features.

## Efficient Forex live-scan target architecture
Preferred staged design for future live scans:
- Stage 1: 28-pair M15 universe scan = 28 symbol credits.
- Derive H1/H4 + 6h/24h/72h currency strength locally.
- Stage 2: fetch M5 only for up to three candidates that pass the quality gate = up to 3 more credits.
- Stage 3: fetch M1/latest only for genuinely executable finalists = up to 3 more credits.
- Target full scan cost with three finalists: about 34 symbol credits, instead of requesting all detailed timeframes for every pair.

Do not automatically deploy this architecture as a live signal engine merely because F2 had a good four-trade selective holdout. The live quality gate must retain `NO TRADE` and current-price/news safeguards.

## Crypto route
GitHub Actions direct REST route: Binance -> OKX -> Bybit.
Recent environment behavior:
- Binance has been inaccessible/restricted in some runs.
- OKX has been the reliable source for many pairs.
- Bybit is fallback and useful for some linear/perpetual history.
- Cloudflare direct crypto attempts previously suffered geographic/rate/JSON issues; GitHub runner route is preferred.

## Refresh workflow for a current symbol
1. Read current `request.json`.
2. Change to the exact requested symbol and increment `id`.
3. Commit so GitHub Actions runs.
4. Wait for `Fetch Market Data` success/data commit.
5. Read `data/status.json`.
6. Validate requested == returned symbol.
7. Validate all required timeframes/context.
8. For crypto, validate currentPriceTime / quote age, stale=false, executionReady=true, symbolVerified=true, bid/ask where available.
9. For Forex, M1/latest is execution data only; do not spend M1 credits on the full universe.
10. Only then quote an executable/current price or issue a MARKET decision.

## Current market-type routing principles
- Forex: Twelve Data / Worker, with local resampling preferred for universe research.
- Metals: Twelve Data unless a better explicitly validated route is configured.
- Cash indices: Twelve Data mappings, but entitlement may block some symbols; never substitute futures.
- Crypto: exchange direct via GitHub runner.

## Cash-index mapping / protection
Resolver supports cash aliases including SPX/US500, NDX/USTEC/NAS100, DJI, DAX, FTSE, CAC, N225/NIKKEI, HSI and others.
True futures NQ/ES/MNQ/MES must remain blocked in cash-index handling.

## Known entitlement limitation
NASDAQ-100 cash `NDX` has returned a Twelve Data message that the symbol requires a higher entitlement. This is a provider-plan issue, not permission to use NQ futures as a proxy for live execution.

## Blind-test integrity
- Decision, entry, SL and TP must be generated exclusively from data at/before cutoff.
- Future candles are opened only after the decision is locked.
- A timestamp previously used to tune rules is not a true unseen sample.
- Keep development/regression samples distinct from untouched validation samples.
- Do not cherry-pick only winning dates.
- A strong result on only a handful of selected trades must be labeled small-sample evidence, not a stable win rate.

## Repository retention / cleanup policy
The active Git tree should remain lean. Keep:
- live pipeline/workflow/config files;
- active strategy engine and only the code dependency chain required to reproduce it;
- key validation result files that support the current method;
- canonical checkpoints and compact research archives;
- reusable non-crypto calibration/backtest infrastructure still relevant to Forex/metals/indices.

Remove after conclusions are checkpointed:
- rejected strategy-version scripts that are no longer dependencies;
- one-off diagnostic/grid/probe workflows;
- large raw probe dumps that can be regenerated from providers;
- duplicate/obsolete method docs superseded by canonical checkpoints;
- old rejected-version result JSONs once conclusions are summarized.

Do NOT delete a file solely because it is old if it is still imported by the active engine or is part of live Forex/metals/index infrastructure. Git history retains old commits.

## Current cleanup status
- Crypto active tree was pruned on 2026-08-17 as documented in crypto checkpoints.
- Forex F1 is diagnostic/rejected and should be removed from the active tree after its conclusion is checkpointed.
- Forex F2 engine/result are retained as the current reusable research candidate.

## Cross-chat protocol
New chat should first read:
1. `docs/checkpoints/MASTER_TRADING_STATE.md`
2. `docs/checkpoints/CURRENT_HANDOFF.md`
3. relevant market checkpoint
4. this file
5. current `data/status.json` or latest retained backtest result as required.

If pipeline health is uncertain, verify the current workflow run rather than relying on an old successful run.