# Trading API

Canonical live Trading repository for the current architecture.

## Current architecture

- **V73** — frozen no-CUT statistical prior. The frozen artifact is `data/nocut_intraday_allpass_v73.json`.
- **V74** — current live-analysis/execution playbook layered on V73.
- **Twelve Data Grow 55** — primary aggregated market-data provider for Forex and supported non-crypto instruments.
- **Crypto execution data** — exchange-native Binance / OKX / Bybit REST where available.
- **Canonical market registry** — `scripts/market_registry.py` owns market type, provider symbol and integrity rails. Do not duplicate aliases in workflows.

V73 is frozen. Legacy optimizer/backtest generations are not part of the active tree and must not be reintroduced into live execution.

## Active workflows

- `.github/workflows/fetch-market.yml` — canonical one-symbol fetch. Resolves the requested instrument, fetches data, validates identity, and refuses bad provider mappings before promotion to `data/latest.json`.
- `.github/workflows/scan-forex.yml` — 28-pair Grow55 Forex universe scan, deep Top 3 review.
- `.github/workflows/live-crypto-v74-scan.yml` — current crypto candidate scan using exchange-native data.
- `.github/workflows/audit-market-data.yml` — cross-market regression audit covering Forex, Crypto, spot commodities, cash indices and futures identity handling.
- `.github/workflows/validate-nocut-v73.yml` — validates frozen V73 integrity.
- `.github/workflows/validate-live-v74.yml` — validates all V74 live playbooks.

The old standalone fast-Forex refresh path was removed because it duplicated the canonical single-symbol path and could create conflicting data semantics.

## Active scripts

- `scripts/nocut_intraday_method_v73.py`
- `scripts/validate_nocut_v73.py`
- `scripts/live_symbol_analysis_v74.py`
- `scripts/fetch_crypto.py`
- `scripts/market_registry.py`
- `scripts/audit_market_data.py`

## Live-data integrity

A provider ticker string alone never proves instrument identity. Before data is promoted to `data/latest.json`, the canonical path checks:

- requested symbol and canonical market type;
- expected provider symbol;
- provider-reported market type and market symbol;
- broad price sanity rail for explicit cash indices / metals / futures;
- current price versus recent M5 reference for obvious corruption;
- timestamp freshness and bid/ask when the source actually exposes them.

If any identity check fails, `data/status.json` is written with `status=DATA_BLOCK`, while the previous accepted `data/latest.json` is preserved.

For MARKET execution:

- verify exact instrument / contract / venue;
- verify timestamp freshness;
- verify bid/ask and spread when the venue provides them;
- never invent bid/ask or spread;
- never substitute cash indices for futures or vice versa;
- never substitute spot commodity aggregates for exact CME futures;
- return `DATA_BLOCK` when the requested instrument cannot be proven.

## Checkpoints

Read in this order:

1. `docs/checkpoints/MASTER_TRADING_STATE.md`
2. `docs/checkpoints/CURRENT_HANDOFF.md`
3. `docs/checkpoints/DATA_INFRA_STATE.md`
4. `docs/checkpoints/LIVE_SYMBOL_ANALYSIS_V74.md`
5. `docs/checkpoints/TWELVEDATA_GROW55_DATA_POLICY.md`
6. the relevant market checkpoint for Futures, Cash Indices or Metals.

Historical research remains recoverable from Git history. It is intentionally excluded from the active tree so old experiments cannot be mistaken for current live logic.
