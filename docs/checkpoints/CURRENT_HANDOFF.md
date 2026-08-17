# CURRENT HANDOFF — TRADING PROJECT

Updated: 2026-08-17 UTC+7

Read `MASTER_TRADING_STATE.md` first.

## CURRENT MODE

1. **V73 = frozen no-CUT statistical prior.**
2. **V74 = live-analysis / execution layer.**
3. **Twelve Data Grow55 direct strict V3 = supported Forex / spot metals / supported spot commodity path.**
4. **Crypto final data = exchange-native Binance / OKX / Bybit.**
5. **Unsupported/ambiguous cash index or futures instrument = DATA_BLOCK, never proxy.**

Do not rebuild or optimize V73 during live trading. Do not revive legacy research from Git history unless explicitly requested.

## MARKET-DATA PATCH — LOCKED 2026-08-17

The former Worker shorthand mapping was unsafe:
- `NAS100 -> NDX` resolved to Nordex SE ADR in Frankfurt around 19.4;
- `SPX` resolved to Stellar AfricaGold on TSXV around 0.085.

Those were ticker collisions, not index prices. They are permanently rejected.

Canonical direct client:
- `scripts/twelvedata_market.py`;
- version `V3-TWELVEDATA-DIRECT-STRICT`;
- GitHub secret `TWELVEDATA_API_KEY`;
- no Cloudflare Worker in canonical runtime.

Strict rules:
1. explicit canonical symbol mapping only;
2. every `time_series` timeframe validates exact `meta.symbol` and expected `meta.type`;
3. EMA/RSI/ATR and M5 confirmation use closed candles only;
4. `/quote` proves identity and supplies `last_quote_at`;
5. `/price` supplies latest aggregated value only after identity is proven;
6. large `/price` vs validated quote drift blocks data;
7. quote age >65 seconds => `DATA_BLOCK`;
8. V74 Forex MARKET review remains stricter at <=30 seconds;
9. Twelve Data broker bid/ask are not fabricated;
10. cash index/futures aliases unsupported by current Grow55 are explicitly blocked.

## CANONICAL PATHS

### Single symbol
Workflow: `.github/workflows/fetch-market.yml`
Trigger: `request.json`
Outputs: `data/status.json`, `data/latest.json`.

- Crypto -> `scripts/fetch_crypto.py`, exchange-native.
- Supported non-crypto -> `scripts/twelvedata_market.py`, direct Twelve Data.
- Unsupported/ambiguous index/futures -> `DATA_BLOCK` with no fake price.

### Forex universe
Workflow: `.github/workflows/scan-forex.yml`
Trigger: `scan-request.json`.

Grow55 normal budget:
- 28 H1 broad = 28 credits;
- Top3 × D1/H4/M15/M5, H1 reused = 12;
- Top3 × (`/quote` + `/price`) = 6;
- total = **46/55**, reserve = **9**.

### Crypto universe
Workflow: `.github/workflows/live-crypto-v74-scan.yml`
Trigger: `data/live_scan_request.txt`.

## CURRENT MARKET SUPPORT

### Forex
Supported through exact `AAA/BBB` mapping when provider type is `Physical Currency`. Current price uses validated `/price`; provider timestamp is `/quote.last_quote_at`.

### Crypto
Exchange-native quote required. Target age <=10s plus exact venue and real bid/ask.

### Spot metals / supported spot commodities
Examples:
- XAUUSD -> XAU/USD / `Precious Metal`;
- XAGUSD -> XAG/USD / `Precious Metal`;
- WTIUSD -> WTI/USD / `Energy Resource` only while freshness passes.

Correct symbol with stale quote is still `DATA_BLOCK`. Spot is never substituted for futures.

### Cash indices
Current Grow55/core endpoints do not safely prove NAS100/NDX, US500/SPX, DAX/GDAXI or N225-family cash index data. These are deliberately `DATA_BLOCK`. Never proxy with NQ/ES, CFDs, ETFs or same-text securities.

### Futures
Current Grow55 catalog/search does not expose exact provable CME/COMEX/NYMEX NQ/MNQ/ES/MES/GC/SI/CL contracts. These are deliberately `DATA_BLOCK`. Use an authoritative futures feed or user platform price until such a feed is integrated.

## AUDIT EVIDENCE

Permanent audit:
- `.github/workflows/audit-market-data.yml`;
- `scripts/audit_market_data.py`;
- `data/market-data-audit.json`.

Final strict V3 audit run **`32047340663` = SUCCESS**.
Latest evidence:
- 17 cases total;
- 7 PASS;
- 10 BLOCKED_AS_DESIGNED;
- 0 FAIL.

PASS set includes exchange-native BTCUSDT/ETHUSDT/SOLUSDT and strict Twelve Data EURUSD/GBPJPY/XAUUSD/XAGUSD. BLOCKED set includes NAS100/US500/DAX/N225 and NQ/MNQ/ES/MES/GC/CL, proving no same-ticker or cash/futures proxy is returned.

## V73 FROZEN RESULT

- Forex 28/28 PASS, minimum development WR 80.00%.
- Crypto 61/61 PASS, minimum development WR 80.22%.
- Forex H1; 59 Crypto H1; TON/IP 4H.
- frozen maps: 1 trade/day, RR1:1.
- exposed development all-pass, not untouched OOS.

Runtime source:
- `data/nocut_intraday_allpass_v73.json`
- `scripts/nocut_intraday_method_v73.py`
- `scripts/validate_nocut_v73.py`

## V74 LIVE RULES

1. exact instrument/venue/contract;
2. current timestamped price and market state;
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
- `audit_market_data.py`
- `nocut_intraday_method_v73.py`
- `validate_nocut_v73.py`
- `live_symbol_analysis_v74.py`

Legacy research and temporary diagnostics belong in Git history only.

## NEW CHAT INSTRUCTION

`Continue Trading from MASTER_TRADING_STATE.md and CURRENT_HANDOFF.md. Use V73 frozen + V74 live. Use direct strict Twelve Data V3 for supported Forex/spot metals, exchange-native crypto, and DATA_BLOCK unsupported/ambiguous cash indices or exact futures. Never trust shorthand ticker identity, never proxy cash/futures, never label stale data live, and never fabricate bid/ask.`
