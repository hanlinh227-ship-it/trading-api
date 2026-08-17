# DATA / INFRA STATE

Updated: 2026-08-17 (UTC+7)
Repo: `hanlinh227-ship-it/trading-api`

## Core repository files
- `request.json`: requested symbol / id trigger.
- `.github/workflows/fetch-market.yml`: main market-data workflow.
- `scripts/fetch_crypto.py`: direct crypto exchange fetcher.
- `data/status.json`: validated current output.
- `data/latest.json`: raw/full output.
- Active crypto blind-test lineage: `scripts/blind_backtest_crypto.py`, `scripts/blind_backtest_crypto_v17.py`, `scripts/blind_backtest_crypto_v22.py`, `scripts/blind_backtest_crypto_v24.py` plus key V17/V22/V24 result files.

## Cloudflare / Twelve Data
Cloudflare Worker: `forex-chart-api`.
Twelve Data is primarily used for Forex/metals/cash-index routes, subject to plan entitlement.
Basic quota context: approximately 800 API calls/day; reset at 00:00 UTC = 07:00 Vietnam time (UTC+7).
Do not spend Twelve Data credits on crypto when direct exchange REST works.

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
7. Validate all required timeframes.
8. For crypto, validate currentPriceTime / quote age, stale=false, executionReady=true, symbolVerified=true, bid/ask where available.
9. Only then quote an executable/current price or issue a MARKET decision.

## Current market-type routing principles
- Forex: Twelve Data.
- Metals: Twelve Data unless a better explicitly validated route is configured.
- Cash indices: Twelve Data mappings, but entitlement may block some symbols; never substitute futures.
- Crypto: exchange direct via GitHub runner.

## Cash-index mapping / protection
Resolver supports cash aliases including SPX/US500, NDX/USTEC/NAS100, DJI, DAX, FTSE, CAC, N225/NIKKEI, HSI and others.
True futures NQ/ES/MNQ/MES must remain blocked in cash-index handling.

## Known entitlement limitation
NASDAQ-100 cash `NDX` has returned a Twelve Data message that the symbol requires Grow or Venture. This is a provider-plan issue, not permission to use NQ futures as a proxy for live execution.

## Blind-test integrity
- Decision, entry, SL and TP must be generated exclusively from data at/before cutoff.
- Future candles are opened only after the decision is locked.
- A timestamp previously used to tune rules is not a true unseen sample.
- Keep development/regression samples distinct from untouched validation samples.
- Do not cherry-pick only winning dates.

## Repository retention / cleanup policy
The active Git tree should remain lean. Keep:
- live pipeline/workflow/config files;
- active strategy engine and only the code dependency chain required to reproduce it;
- key validation result files that support the current method;
- canonical checkpoints and compact research archives;
- reusable non-crypto calibration/backtest infrastructure that is still relevant to Forex/metals/indices.

Remove from the active tree after conclusions are checkpointed:
- rejected strategy-version scripts that are no longer dependencies;
- one-off diagnostic/grid/probe workflows;
- large raw probe dumps that can be regenerated from providers;
- duplicate/obsolete method docs superseded by canonical checkpoints;
- old rejected-version result JSONs once their conclusions are summarized.

Do NOT delete a file solely because it is old if it is still imported by the active engine or is part of the live Forex/metals/index infrastructure. Git history retains old commits, so active-tree cleanup mainly prevents future clutter; a destructive history rewrite is unnecessary unless repository history eventually becomes genuinely large.

## Current crypto cleanup status
On 2026-08-17 the repo was pruned so the current crypto lineage keeps base + V17 + V22 + V24 code and key results, while retired V8–V23 artifacts that were not dependencies and one-off diagnostics/probes were removed from the active tree after being summarized in `docs/checkpoints/CRYPTO_RESEARCH_ARCHIVE.md`.

## Cross-chat protocol
New chat should first read:
1. `docs/checkpoints/MASTER_TRADING_STATE.md`
2. `docs/checkpoints/CURRENT_HANDOFF.md`
3. relevant market checkpoint
4. this file
5. current `data/status.json` or latest retained backtest result as required.

If pipeline health is uncertain, verify the current workflow run rather than relying on an old successful run.