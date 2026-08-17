# MASTER TRADING STATE

Updated: 2026-08-17 UTC+7
Purpose: single canonical state for the Trading project.

## Read order
1. `CURRENT_HANDOFF.md`
2. `NO_CUT_INTRADAY_ALLPASS_V73.md`
3. `LIVE_SYMBOL_ANALYSIS_V74.md`
4. `TWELVEDATA_GROW55_DATA_POLICY.md`
5. relevant market checkpoint: `FUTURES_NQ_ES_STATE.md`, `CASH_INDICES_STATE.md`, or `METALS_STATE.md`

# CURRENT ARCHITECTURE

## V73 — frozen statistical prior
V73 is the frozen no-CUT forced-daily prior.

Hard rules retained in the frozen artifact:
- no CUT;
- no discretionary whole-day NO TRADE;
- 1–3 trades per eligible day;
- frozen development maps currently use exactly 1 trade/day;
- RR only 1:1 or 1:2;
- frozen passing maps use RR1:1;
- TIMEOUT = non-win;
- same-bar TP+SL = SL conservatively.

Frozen development result:
- Forex: 28/28 PASS, minimum pair WR 80.00%;
- Crypto: 61/61 PASS, minimum symbol WR 80.22%;
- Forex: H1;
- 59 Crypto: H1;
- TON/IP: dedicated 4H methods.

Canonical V73 runtime files:
- `data/nocut_intraday_allpass_v73.json`
- `scripts/nocut_intraday_method_v73.py`
- `scripts/validate_nocut_v73.py`
- `.github/workflows/validate-nocut-v73.yml`

**V73 is frozen. Rebuild/optimizer generations are not part of the active tree.** Historical research remains recoverable from Git history. This prevents accidental retuning or execution of an obsolete research engine.

Integrity classification:
**EXPOSED DEVELOPMENT ALL-PASS; NOT UNTOUCHED OOS.**
Historical development WR is not a future/live guarantee.

## V74 — current live-analysis / execution layer
Every live Forex/Crypto analysis uses V74 over the frozen V73 prior where applicable.

Canonical files:
- `scripts/live_symbol_analysis_v74.py`
- `docs/checkpoints/LIVE_SYMBOL_ANALYSIS_V74.md`
- `.github/workflows/validate-live-v74.yml`

Coverage:
- 28 Forex + 61 Crypto = 89/89 live playbooks;
- current crypto identities explicitly mapped;
- no generic `OTHER` live fallback;
- V73 signal hour = observation anchor only;
- `DUAL_FADE` = geometry, never a blind two-sided order.

# LIVE DECISION ORDER
1. Resolve exact symbol / instrument / venue / contract.
2. Refresh current market data and validate identity/timestamp.
3. Refresh current symbol-specific news/macro/project context.
4. D1/H4 draw-on-liquidity, regime, premium/discount.
5. H1 structure and point-in-time observable features only.
6. Read frozen V73 prior/router without optimizing it.
7. Require M15 tradable location.
8. Require M5 close-confirmed MSS/displacement + retest for strict execution.
9. Structural SL first; ATR only a volatility floor.
10. Default RR1; RR2 only with >=2.2R clean structural room after costs.
11. Verify final venue/price/timestamp/spread before MARKET.
12. Record forward result without retuning from that outcome.

# DATA ARCHITECTURE — GROW55 DIRECT STRICT V3

Primary policy: `TWELVEDATA_GROW55_DATA_POLICY.md`.
Canonical non-crypto client: `scripts/twelvedata_market.py` version `V3-TWELVEDATA-DIRECT-STRICT`.

The old Cloudflare Worker shorthand mapping is not part of the canonical runtime after ticker-collision diagnostics proved it unsafe for cash indices.

## Forex
- direct Twelve Data Grow55;
- explicit `AAA/BBB` mapping;
- every timeframe validates exact provider `meta.symbol` + `meta.type`;
- indicators and M5 confirmation use closed candles only;
- `/quote` proves identity and supplies `last_quote_at`;
- `/price` supplies latest aggregated value only after identity is proven;
- quote age >65s => DATA_BLOCK;
- V74 MARKET review target remains <=30s;
- full 28-pair staged scan budget = approximately 46/55 credits, leaving 9 reserve.

## Crypto
- final execution quote is exchange-native Binance / OKX / Bybit where supported;
- exact venue, bid, ask and exchange timestamp take priority over aggregated sources;
- target quote age <=10s.

## Futures
- futures are separate from cash indices;
- MNQ/MES preferred execution instruments for the NQ/ES system;
- current Grow55 diagnostics do not expose exact provable NQ/MNQ/ES/MES/GC/SI/CL contracts;
- Twelve Data therefore returns DATA_BLOCK for those exact futures symbols;
- use authoritative futures feed or user platform price until exact contract feed is integrated;
- never proxy cash/spot data.

## Cash indices
- current Grow55/core endpoints do not safely prove NAS100/NDX, US500/SPX, DAX/GDAXI or N225-family cash indices;
- those aliases deliberately return DATA_BLOCK;
- never substitute futures, CFDs, ETFs or a same-text security.

## Metals / spot commodities
- XAUUSD/XAGUSD use verified spot identities such as `XAU/USD`, `XAG/USD`;
- spot remains separate from GC/SI futures;
- correct identity with a stale timestamp still returns DATA_BLOCK.

# PRICE INTEGRITY

Distinguish four concepts:
1. provider market timestamp (`last_quote_at` / exchange timestamp);
2. our fetch time;
3. latest aggregated price value (`/price` after identity validation);
4. executable venue bid/ask spread.

They are not interchangeable.

- Crypto normally has exchange bid/ask and exact exchange timestamp.
- Twelve Data non-crypto does not provide executable broker bid/ask in this integration; do not invent spread.
- If exact identity, timestamp freshness or required execution fields cannot be verified, return DATA_BLOCK rather than fabricate execution data.

# CANONICAL AUDIT

Permanent cross-market audit:
- `.github/workflows/audit-market-data.yml`
- `scripts/audit_market_data.py`
- `data/market-data-audit.json`

Final V3 audit run `32047340663` completed SUCCESS with 17 cases: 7 PASS, 10 BLOCKED_AS_DESIGNED, 0 FAIL.

# ACTIVE REPOSITORY SCOPE

Active workflows:
- `fetch-market.yml`
- `scan-forex.yml`
- `live-crypto-v74-scan.yml`
- `audit-market-data.yml`
- `validate-nocut-v73.yml`
- `validate-live-v74.yml`

Active scripts:
- `fetch_crypto.py`
- `twelvedata_market.py`
- `audit_market_data.py`
- `nocut_intraday_method_v73.py`
- `validate_nocut_v73.py`
- `live_symbol_analysis_v74.py`

Legacy blind tests, calibration suites, one-off provider diagnostics, old optimizer versions, old result JSONs and obsolete snapshot/refresh workflows are not part of the current architecture. Git history remains the archive.

# SPECIAL MARKET RULES

## NQ/ES Futures
Compare NQ/ES or MNQ/MES and normally choose one stronger setup. Structural SL first, then contract count. Risk framework remains approximately USD 500 maximum SL and USD 1,500 target when structure genuinely permits it.

## Live trade frequency
Frozen V73 minimum-trade research rules never authorize fabricated prices, stale quotes or wrong-instrument MARKET orders. DATA_BLOCK overrides forced-trade research logic when data integrity fails.

## Handoff phrase
`Tiếp tục Trading từ MASTER_TRADING_STATE.md. Current state = V73 frozen prior + V74 live layer + Twelve Data Grow55 direct strict V3. Do not rebuild/re-optimize V73 or resurrect legacy research. For live analysis verify exact instrument, current timestamped data, current news/context, D1-H4-H1 bias, V73 prior where applicable, M15 location, M5 close-confirmed trigger, structural SL and final execution-venue data.`
