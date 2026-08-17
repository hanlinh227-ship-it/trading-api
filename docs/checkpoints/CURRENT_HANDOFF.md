# CURRENT HANDOFF — TRADING PROJECT

Updated: 2026-08-17 UTC+7

Read `MASTER_TRADING_STATE.md` first.

## CURRENT MODE

1. **V73 = frozen no-CUT statistical prior.**
2. **V74 = live-analysis / execution layer.**
3. **Twelve Data Grow 55 direct strict client = primary supported non-crypto data path.**
4. **Crypto final data = exchange-native Binance / OKX / Bybit.**
5. **Unsupported/ambiguous index or futures instruments = DATA_BLOCK, never proxy.**

Do not rebuild/optimize V73 during live trading. Do not revive legacy research files from Git history unless explicitly requested.

## DATA INTEGRITY PATCH — 2026-08-17

The previous Worker shorthand mapping was proven unsafe for cash indices:
- `NAS100 -> NDX` returned an unrelated value near `19.4`;
- `SPX` returned an unrelated value near `0.085`;
- `N225` did not return a usable 5-timeframe dataset.

Those values are rejected and must never be used as Nasdaq-100/S&P 500/Nikkei cash-index prices.

Canonical direct Twelve Data client:
- `scripts/twelvedata_market.py`
- client version `V2-TWELVEDATA-DIRECT-STRICT`
- uses the GitHub Actions secret `TWELVEDATA_API_KEY`;
- uses explicit canonical symbol mappings;
- calls Twelve Data directly instead of trusting the old Worker mapping;
- uses `/quote` and `last_quote_at` for current aggregated price/time;
- validates `/time_series` metadata (`symbol` + expected `type`) on every timeframe;
- uses closed candles only for D1/H4/H1/M15/M5/M1 calculations;
- never fabricates bid/ask/spread;
- returns `DATA_BLOCK` for ambiguous/unsupported instruments.

Canonical single-symbol workflow:
- `.github/workflows/fetch-market.yml`

Crypto remains exchange-native through:
- `scripts/fetch_crypto.py`

Canonical mapping/integrity registry:
- `scripts/market_registry.py`

Cross-market regression audit:
- `.github/workflows/audit-market-data.yml`
- `scripts/audit_market_data.py`
- `data/market-data-audit.json`

The redundant `fast-forex-v74-refresh.yml` workflow and `data/forex_fast_request.txt` trigger were removed to prevent conflicting data paths.

## CURRENT MARKET SUPPORT

### Forex
Direct Twelve Data is supported when exact `Physical Currency` metadata matches.
Current strict target for V74: verified quote timestamp age <=30s. Bid/ask may still be unavailable from Twelve Data, so executable broker spread is not invented.

### Crypto
Exchange-native quote required. Target age <=10s plus real bid/ask and exact venue identity.

### Spot metals
XAUUSD/XAGUSD are supported as Twelve Data `Precious Metal` instruments (`XAU/USD`, `XAG/USD`) when metadata/timestamp checks pass. Keep spot metals separate from GC/SI futures.

### Cash indices
Current Grow55/core endpoint diagnostics do **not** prove safe exact NAS100/US500/DAX/N225 cash-index data. Therefore these aliases are deliberately `DATA_BLOCK` in the strict Twelve client. Never use NQ/ES as a silent proxy.

### Futures
Current Grow55 catalog/search did not expose exact provable CME/COMEX/NYMEX NQ/MNQ/ES/MES/GC/CL contracts. These are deliberately `DATA_BLOCK`. For MNQ/MES use an authoritative futures feed or the user's platform price until an exact futures feed is integrated.

## AUDIT EVIDENCE

Initial audit run `32046515521` proved:
- BTCUSDT / ETHUSDT / SOLUSDT exchange-native data valid;
- EURUSD / GBPUSD / USDJPY Twelve Data mappings valid;
- XAUUSD / XAGUSD symbol/price valid but old registry type label needed correction;
- NAS100 / SPX mappings were wrong and caught by sanity rails;
- N225 unusable;
- NQ/MNQ/ES/MES correctly blocked instead of proxied.

Strict direct audit run `32046893468` then proved:
- BTCUSDT, ETHUSDT, SOLUSDT PASS with sub-2s exchange timestamps and bid/ask;
- EURUSD, GBPJPY PASS with direct Twelve Data `last_quote_at`, 5/5 frames;
- XAUUSD PASS with `Precious Metal` metadata and direct timestamp;
- NAS100/US500/DAX/N225 BLOCKED_AS_DESIGNED;
- NQ/MNQ/ES/MES/GC/CL BLOCKED_AS_DESIGNED;
- the only FAIL in that run was WTIUSD because its quote was ~38 minutes old, so it was correctly rejected as stale.

A final V3 audit removes WTI from the supported-live regression set and tests XAGUSD instead.

## V73 FROZEN RESULT

- Forex 28/28 PASS, minimum development WR 80.00%.
- Crypto 61/61 PASS, minimum development WR 80.22%.
- Forex H1; 59 Crypto H1; TON/IP dedicated 4H.
- frozen maps: 1 trade/day, RR1:1.
- classification: exposed development all-pass, not untouched OOS.

Runtime source of truth:
- `data/nocut_intraday_allpass_v73.json`
- `scripts/nocut_intraday_method_v73.py`
- `scripts/validate_nocut_v73.py`

## V74 LIVE RULES

For every live setup:
1. exact instrument/venue/contract;
2. current timestamped price data and market state;
3. current symbol-specific news/context;
4. D1/H4 bias/liquidity;
5. H1 structure;
6. frozen V73 prior/router where applicable;
7. M15 tradable location;
8. M5 close-confirmed MSS/displacement + retest;
9. structural SL first;
10. RR1 default, RR2 only with >=2.2R clean room after costs;
11. final execution-venue quote/spread verification before MARKET.

## ACTIVE WORKFLOWS

- `fetch-market.yml`
- `scan-forex.yml`
- `live-crypto-v74-scan.yml`
- `audit-market-data.yml`
- `validate-nocut-v73.yml`
- `validate-live-v74.yml`

## ACTIVE SCRIPTS

- `fetch_crypto.py`
- `twelvedata_market.py`
- `market_registry.py`
- `audit_market_data.py`
- `nocut_intraday_method_v73.py`
- `validate_nocut_v73.py`
- `live_symbol_analysis_v74.py`

Legacy research remains in Git history only.

## NEW CHAT INSTRUCTION

`Continue Trading from MASTER_TRADING_STATE.md and CURRENT_HANDOFF.md. Use direct strict Twelve Data for supported Forex/metals, exchange-native crypto, and DATA_BLOCK unsupported/ambiguous cash indices or exact futures. Never trust shorthand ticker identity, never proxy cash/futures, never fabricate bid/ask, and never revive legacy research.`
