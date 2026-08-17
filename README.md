# Trading API

Canonical live Trading repository for the current architecture.

## Current architecture

- **V73** — frozen no-CUT statistical prior. The frozen artifact is `data/nocut_intraday_allpass_v73.json`.
- **V74** — current live-analysis/execution playbook layered on V73.
- **Twelve Data Grow 55** — primary aggregated market-data provider for Forex and supported non-crypto instruments.
- **Crypto execution data** — exchange-native Binance / OKX / Bybit REST where available.

V73 is frozen. Legacy optimizer/backtest generations are not part of the active tree and must not be reintroduced into live execution.

## Active workflows

- `.github/workflows/fetch-market.yml` — one-symbol market data: full 5-timeframe analysis plus final price/reference data.
- `.github/workflows/scan-forex.yml` — 28-pair Grow 55 Forex universe scan, deep Top 3 review.
- `.github/workflows/live-crypto-v74-scan.yml` — current crypto candidate scan using exchange-native data.
- `.github/workflows/validate-nocut-v73.yml` — validates frozen V73 integrity.
- `.github/workflows/validate-live-v74.yml` — validates all V74 live playbooks.
- `.github/workflows/fast-forex-v74-refresh.yml` — lightweight final aggregated-price refresh for a Forex finalist.

## Active scripts

- `scripts/nocut_intraday_method_v73.py`
- `scripts/validate_nocut_v73.py`
- `scripts/live_symbol_analysis_v74.py`
- `scripts/fetch_crypto.py`

## Live-data integrity

A current aggregated price is not automatically an executable broker quote. For MARKET execution:

- verify exact instrument / contract / venue;
- verify timestamp freshness;
- verify bid/ask and spread when the venue provides them;
- never invent bid/ask or spread;
- never substitute cash indices for futures or vice versa;
- return `DATA_BLOCK` when the required execution data cannot be verified.

## Checkpoints

Read in this order:

1. `docs/checkpoints/MASTER_TRADING_STATE.md`
2. `docs/checkpoints/CURRENT_HANDOFF.md`
3. `docs/checkpoints/LIVE_SYMBOL_ANALYSIS_V74.md`
4. `docs/checkpoints/TWELVEDATA_GROW55_DATA_POLICY.md`
5. the relevant market checkpoint for Futures, Cash Indices or Metals.

Historical research remains recoverable from Git history. It is intentionally excluded from the active tree so old experiments cannot be mistaken for current live logic.
