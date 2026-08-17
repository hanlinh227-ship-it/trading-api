# Trading API

Canonical live Trading repository.

## Architecture

- **V73** — frozen no-CUT statistical prior. Never rebuild during live use.
- **V74** — current live-analysis / execution playbook.
- **V75 Fast Data** — speed layer only. It does not change V73/V74 trading rules; it parallelizes data collection and creates compact decision snapshots.
- **Twelve Data Grow55** — direct strict source for supported Forex and spot metal/commodity data.
- **Crypto execution data** — exchange-native Binance / OKX / Bybit REST; universe scanner currently uses OKX spot.

## Fast read order

For live questions, read the smallest artifact first:

1. single symbol → `data/decision.json`;
2. Forex universe → `data/forex-fast.json`;
3. Crypto universe → `data/crypto-fast.json`;
4. only open `status.json`, `latest.json` or full scan files when deeper evidence is required.

This avoids repeatedly reading thousands of candle rows.

## Active workflows

- `.github/workflows/fetch-market.yml` — V75 single-symbol path.
- `.github/workflows/scan-forex.yml` — V75 28-pair Grow55 staged scan.
- `.github/workflows/live-crypto-v75-scan.yml` — V75 staged V74 crypto-universe scan.
- `.github/workflows/audit-market-data.yml` — cross-market integrity regression.
- `.github/workflows/validate-nocut-v73.yml` — frozen V73 validation.
- `.github/workflows/validate-live-v74.yml` — V74 playbook validation.

## Active scripts

- `scripts/twelvedata_market.py` — `V4-TWELVEDATA-FAST-STRICT`; exact non-crypto resolver + parallel 5-TF fetch + compact decision builder.
- `scripts/fetch_crypto.py` — `V2-CRYPTO-FAST-STRICT`; parallel 5-TF exchange-native single-symbol fetch.
- `scripts/scan_forex_v75.py` — 28-pair staged Grow55 engine.
- `scripts/scan_crypto_v75.py` — staged V74 crypto universe engine.
- `scripts/live_symbol_analysis_v74.py`
- `scripts/nocut_intraday_method_v73.py`
- `scripts/validate_nocut_v73.py`
- `scripts/audit_market_data.py`

## V75 speed design

### Single symbol

D1/H4/H1/M15/M5 are requested in parallel. M1 is no longer fetched by default. Indicators still use full history in memory, but only compact candle tails are stored. Final price/timestamp is refreshed independently.

### Forex universe

Grow55 budget remains **46/55 credits**:
- 28 H1 broad = 28;
- Top3 × D1/H4/M15/M5 = 12;
- Top3 × (`/quote` + `/price`) = 6;
- reserve = 9.

Network calls are parallelized. Benchmark run `32049900306` completed the market-data section in **0.643 s** for 28 pairs + Top3 deep analysis.

### Crypto universe

V74 defines 61 crypto identities. V75 checks exact OKX USDT spot availability, then runs:

`available universe H1 → Top12 M15/M5 → Top5 D1/H4 → exact bid/ask/timestamp`

Benchmark run `32050388431` found 57 exact OKX USDT instruments and analyzed **57/57 = 100%** with no errors in **5.427 s**. Missing identities are not remapped to another token.

## Data integrity rules

A ticker string alone never proves identity.

- exact canonical symbol / provider metadata required;
- closed candles only for EMA/RSI/ATR and structure;
- Twelve Data `/quote.last_quote_at` is the provider timestamp;
- `/price` is accepted only after identity is proven;
- Twelve Data quote >65 s → `DATA_BLOCK`;
- V74 Forex live review target remains <=30 s;
- Crypto final quote target <=10 s with real venue bid/ask;
- never fabricate bid/ask or spread;
- never proxy cash index with futures or futures with spot/cash.

The old Cloudflare shorthand Worker is not canonical runtime.

## Current Grow55 boundaries

- Forex: supported with exact `AAA/BBB` identity.
- Spot metals/commodities: supported when metadata/freshness pass.
- Cash indices NAS100/US500/DAX/N225 family: `DATA_BLOCK` until exact cash-index feed is integrated.
- Exact CME/COMEX/NYMEX NQ/MNQ/ES/MES/GC/SI/CL: `DATA_BLOCK` until an authoritative futures feed is integrated.

## Validation

Latest post-V75 cross-market audit run `32050497678`: **SUCCESS**, 17 cases = 7 PASS / 10 BLOCKED_AS_DESIGNED / 0 FAIL.

Latest V73 validator run `32050638267`: **SUCCESS**.

Latest V74 validator run `32050656054`: **SUCCESS**.

## Checkpoints

Read:
1. `docs/checkpoints/MASTER_TRADING_STATE.md`
2. `docs/checkpoints/CURRENT_HANDOFF.md`
3. relevant market/data checkpoint.

Historical research remains in Git history only and must not be confused with current live runtime.
