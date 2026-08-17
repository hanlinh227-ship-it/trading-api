# Trading API

Canonical live Trading repository for the current architecture.

## Current architecture

- **V73** — frozen no-CUT statistical prior. Frozen artifact: `data/nocut_intraday_allpass_v73.json`.
- **V74** — current live-analysis / execution playbook layered on V73.
- **Twelve Data Grow55** — direct strict source for supported Forex and spot metal/commodity data.
- **Crypto execution data** — exchange-native Binance / OKX / Bybit REST.
- **Canonical non-crypto resolver** — `scripts/twelvedata_market.py`. Do not duplicate Twelve Data aliases elsewhere.

V73 is frozen. Legacy optimizer/backtest generations are not part of the active tree and must not be reintroduced into live execution.

## Active workflows

- `.github/workflows/fetch-market.yml` — canonical one-symbol fetch. Crypto uses exchange-native APIs; supported non-crypto uses the direct strict Twelve Data client; unsupported/ambiguous instruments return `DATA_BLOCK`.
- `.github/workflows/scan-forex.yml` — direct 28-pair Grow55 Forex universe scan with strict metadata and freshness checks.
- `.github/workflows/live-crypto-v74-scan.yml` — crypto candidate scan using exchange-native data.
- `.github/workflows/audit-market-data.yml` — permanent cross-market regression audit.
- `.github/workflows/validate-nocut-v73.yml` — validates frozen V73 integrity.
- `.github/workflows/validate-live-v74.yml` — validates V74 live playbooks.

## Active scripts

- `scripts/nocut_intraday_method_v73.py`
- `scripts/validate_nocut_v73.py`
- `scripts/live_symbol_analysis_v74.py`
- `scripts/fetch_crypto.py`
- `scripts/twelvedata_market.py`
- `scripts/audit_market_data.py`

## Twelve Data integrity rules

A ticker string alone never proves instrument identity. The strict path requires:

1. explicit canonical mapping;
2. exact `/time_series` `meta.symbol`;
3. exact provider instrument `meta.type`;
4. `/quote` identity + `last_quote_at` timestamp;
5. `/price` only after identity has been proven;
6. closed candles only for EMA/RSI/ATR and M5 confirmation;
7. hard `DATA_BLOCK` when the provider quote is more than 65 seconds old;
8. no fabricated bid/ask or broker spread.

The old Cloudflare Worker is not part of the canonical live-data runtime.

### Current Grow55 boundaries

- **Forex:** supported through exact `AAA/BBB` mappings such as `EUR/USD`.
- **Spot metals/commodities:** supported when exact metadata and freshness pass, e.g. `XAU/USD`, `XAG/USD`, `WTI/USD`.
- **Cash indices:** current Grow55/core-endpoint combination cannot safely prove NAS100/NDX, US500/SPX, DAX or N225-family cash indices; these are `DATA_BLOCK`, never same-ticker substitutes.
- **Futures:** exact CME/COMEX/NYMEX NQ/MNQ/ES/MES/GC/SI/CL are not exposed as provable contracts in the current Grow55 catalog/search; these are `DATA_BLOCK` until an authoritative futures feed is integrated.

For MARKET execution, aggregated Twelve Data prices are not a substitute for broker/venue bid/ask. Exact execution spread must come from the execution venue when required by V74.

## Forex Grow55 budget

Current 28-pair scanner budget:
- 28 H1 broad scans = 28 credits;
- Top 3 × D1/H4/M15/M5, reusing H1 = 12 credits;
- Top 3 × (`/quote` + `/price`) = 6 credits;
- normal total = **46/55**;
- reserve = **9 credits**.

## Checkpoints

Read in this order:
1. `docs/checkpoints/MASTER_TRADING_STATE.md`
2. `docs/checkpoints/CURRENT_HANDOFF.md`
3. `docs/checkpoints/DATA_INFRA_STATE.md`
4. `docs/checkpoints/LIVE_SYMBOL_ANALYSIS_V74.md`
5. `docs/checkpoints/TWELVEDATA_GROW55_DATA_POLICY.md`
6. relevant market checkpoint for Futures, Cash Indices or Metals.

Historical research remains recoverable from Git history. It is intentionally excluded from the active tree so old experiments cannot be mistaken for current live logic.
