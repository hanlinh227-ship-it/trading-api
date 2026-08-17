# MASTER TRADING STATE

Updated: 2026-08-18 UTC+7
Purpose: single canonical state for the Trading project.

## Read order
1. `CURRENT_HANDOFF.md`
2. `NO_CUT_INTRADAY_ALLPASS_V73.md`
3. `LIVE_SYMBOL_ANALYSIS_V74.md`
4. `TWELVEDATA_GROW55_DATA_POLICY.md`
5. relevant market checkpoint.

# CURRENT ARCHITECTURE

## V73 — frozen statistical prior

V73 is frozen. No live workflow may rebuild or optimize it.

Frozen development result remains:
- Forex 28/28 PASS, minimum development WR 80.00%;
- Crypto 61/61 PASS, minimum development WR 80.22%;
- Forex H1; 59 Crypto H1; TON/IP 4H;
- frozen passing maps currently use 1 trade/day and RR1:1.

Classification: **exposed development all-pass, not untouched OOS; never promise future/live WR.**

Canonical files:
- `data/nocut_intraday_allpass_v73.json`
- `scripts/nocut_intraday_method_v73.py`
- `scripts/validate_nocut_v73.py`

## V74 — live analysis / execution rules

V74 remains the decision authority over V73.

Live order:
1. exact instrument / venue / contract;
2. fresh timestamped market data;
3. current symbol-specific news/context;
4. D1/H4 liquidity/regime;
5. H1 structure;
6. frozen V73 prior where applicable;
7. M15 tradable location;
8. strict M5 close-confirmed MSS/displacement + retest;
9. structural SL first;
10. RR1 default; RR2 only with >=2.2R clean room after costs;
11. final execution-venue quote/spread before MARKET;
12. forward-log without retuning from that outcome.

Coverage remains 28 Forex + 61 Crypto = 89/89 V74 playbooks.

## V75 — Fast Data layer

V75 changes **data latency and read efficiency only**. It does not weaken V74 and does not modify V73.

Preferred live-read artifacts:
- single symbol → `data/decision.json`;
- Forex scan → `data/forex-fast.json`;
- Crypto scan → `data/crypto-fast.json`.

Detailed files are opened only when necessary.

### Single-symbol non-crypto

`scripts/twelvedata_market.py` = `V4-TWELVEDATA-FAST-STRICT`.

- D1/H4/H1/M15/M5 fetched in parallel;
- M1 disabled by default;
- indicators still use full history in memory;
- only compact candle tails stored;
- `/quote` proves identity/timestamp before `/price` is accepted;
- closed candles only;
- Twelve Data quote >65s => DATA_BLOCK;
- V74 Forex freshness target remains <=30s;
- no fabricated bid/ask.

Benchmark USDJPY run `32049389246`: data stage ~**0.38s** once runner was ready.

### Forex universe

Engine: `scripts/scan_forex_v75.py`.
Workflow: `.github/workflows/scan-forex.yml`.

Pipeline: `28 H1 broad → Top3 D1/H4/M15/M5 + quote/price` with independent calls parallelized.

Grow55 budget: 46/55 credits, reserve 9.

Benchmark run `32049900306`: **28 pairs + Top3 deep in 0.643s** data time.

### Crypto single symbol

`scripts/fetch_crypto.py` = `V2-CRYPTO-FAST-STRICT`.

- exchange-native exact symbol;
- 5 TF in parallel;
- closed candles only;
- no mandatory M1;
- final ticker refresh;
- quote target <=10s with real bid/ask.

BTCUSDT benchmark run `32050032469`: 5/5 frames, quote age 241ms, data stage ~**1.27s**.

### Crypto universe

Engine: `scripts/scan_crypto_v75.py`.
Workflow: `.github/workflows/live-crypto-v75-scan.yml`.

Pipeline:
`61 V74 identities → exact OKX USDT availability → all available H1 → Top12 M15/M5 → Top5 D1/H4 → live bid/ask/timestamp`.

Benchmark run `32050388431`:
- 61 identities requested;
- 57 exact OKX USDT instruments available;
- 57/57 analyzed = 100% coverage;
- errors 0;
- data stage **5.427s**.

Missing identities are never substituted with another token.

# MARKET DATA INTEGRITY

The old Cloudflare shorthand Worker is not canonical runtime. Same-text ticker collisions are permanently rejected.

Rules:
1. explicit canonical identity;
2. exact provider symbol/type metadata;
3. closed candles only for technical calculations;
4. provider timestamp != fetch time;
5. `/price` accepted only after identity proof;
6. stale data is never called live;
7. no fabricated spread;
8. cash index, futures and spot are never interchangeable.

## Current support

Forex: direct Twelve Data Grow55 exact `AAA/BBB` mapping.

Crypto: exchange-native Binance/OKX/Bybit for single-symbol; OKX exact USDT spot for universe scan.

Spot metals/commodities: exact Twelve Data identity when supported/fresh.

Cash indices NAS100/US500/DAX/N225-family: current Grow55 path cannot safely prove exact cash index → `DATA_BLOCK`.

Exact futures NQ/MNQ/ES/MES/GC/SI/CL: current Grow55 path cannot prove exact CME/COMEX/NYMEX contract → `DATA_BLOCK` until an authoritative feed is integrated.

# VALIDATION

Post-V75 market-data audit run `32050497678` = SUCCESS:
- 17 total;
- 7 PASS;
- 10 BLOCKED_AS_DESIGNED;
- 0 FAIL.

V73 validator run `32050638267` = SUCCESS.
V74 validator run `32050656054` = SUCCESS.

# ACTIVE REPOSITORY

Workflows:
- `fetch-market.yml`
- `scan-forex.yml`
- `live-crypto-v75-scan.yml`
- `audit-market-data.yml`
- `validate-nocut-v73.yml`
- `validate-live-v74.yml`

Scripts:
- `twelvedata_market.py`
- `fetch_crypto.py`
- `scan_forex_v75.py`
- `scan_crypto_v75.py`
- `audit_market_data.py`
- `nocut_intraday_method_v73.py`
- `validate_nocut_v73.py`
- `live_symbol_analysis_v74.py`

Legacy optimizers, blind tests, one-off diagnostics and obsolete live-data paths remain in Git history only.

# REMAINING BOTTLENECK

The engines themselves are now fast. The main remaining end-to-end delay is GitHub Actions runner provisioning, checkout and commit. To remove that, move V75 runtime to a persistent service/edge cache; further API micro-optimization alone cannot remove runner startup latency.

# SPECIAL MARKET RULES

NQ/ES Futures: compare MNQ/MES and normally choose one stronger setup. Structural SL first, then contract count. User framework remains roughly max SL $500 / target $1,500 when structure supports it.

DATA_BLOCK always overrides any forced-trade research rule.

## Handoff phrase

`Continue Trading with V73 frozen + V74 execution rules + V75 Fast Data. Read decision.json / forex-fast.json / crypto-fast.json first. Verify exact instrument, fresh timestamped data, current news/context, D1-H4-H1, M15 location, strict M5 trigger, structural SL and final execution-venue spread. Never proxy cash/futures and never label stale data live.`
