# CURRENT HANDOFF — TRADING PROJECT

Updated: 2026-08-18 UTC+7

Read `MASTER_TRADING_STATE.md` first.

## CURRENT MODE

- **V73** = frozen no-CUT statistical prior. Never rebuild/optimize during live use.
- **V74** = live-analysis / execution rules. These rules remain unchanged.
- **V75 Fast Data** = current speed layer. It only improves collection/ranking/read latency.
- **Forex / spot metals** = Twelve Data Grow55 direct strict V4.
- **Crypto** = exchange-native; exact venue/bid/ask/timestamp required.
- Unsupported/ambiguous cash index or exact futures = `DATA_BLOCK`, never proxy.

## FAST READ ORDER

Use the smallest artifact first:

1. single symbol → `data/decision.json`;
2. Forex universe → `data/forex-fast.json`;
3. Crypto universe → `data/crypto-fast.json`;
4. open `status.json`, `latest.json` or full scan detail only when needed.

## SINGLE SYMBOL V75

Workflow: `.github/workflows/fetch-market.yml`.

Non-crypto engine: `scripts/twelvedata_market.py`, version `V4-TWELVEDATA-FAST-STRICT`.

- D1/H4/H1/M15/M5 fetch in parallel;
- M1 disabled by default;
- full 220-candle history still used in RAM for EMA200/RSI/ATR;
- only compact candle tails are stored;
- `/quote` proves identity/timestamp, then `/price` gives latest aggregated price;
- closed candles only;
- quote >65s => DATA_BLOCK; V74 Forex review target <=30s;
- Twelve Data broker bid/ask are never fabricated.

USDJPY benchmark run `32049389246`: actual Twelve Data 5-TF + quote/price section completed in about **0.38s** once the runner was ready.

Crypto engine: `scripts/fetch_crypto.py`, version `V2-CRYPTO-FAST-STRICT`.

- 5 TF fetch in parallel;
- no mandatory M1;
- final ticker refresh after TF analysis;
- strict quote target <=10s;
- real exchange bid/ask required.

BTCUSDT benchmark run `32050032469` = SUCCESS: OKX, 5/5 frames, quote age **241ms**, data stage about **1.27s**.

## FOREX UNIVERSE V75

Workflow: `.github/workflows/scan-forex.yml`.
Engine: `scripts/scan_forex_v75.py`.
Outputs: `data/forex-scan.json`, `data/forex-fast.json`.

Pipeline: `28 H1 broad → Top3 D1/H4/M15/M5 + quote/price`, all independent calls parallelized.

Grow55 budget remains **46/55 credits**, reserve 9.

Benchmark run `32049900306` = SUCCESS: **28 pairs + Top3 deep data in 0.643s**.

## CRYPTO UNIVERSE V75

Workflow: `.github/workflows/live-crypto-v75-scan.yml`.
Engine: `scripts/scan_crypto_v75.py`.
Output: `data/crypto-fast.json`.

Pipeline:
`61 V74 identities → exact OKX USDT availability → all available H1 → Top12 M15/M5 → Top5 D1/H4 → live bid/ask/timestamp`.

429 handling uses lower concurrency + backoff/retry.

Benchmark run `32050388431` = SUCCESS:
- 61 identities requested;
- 57 exact OKX USDT instruments available;
- **57/57 broad analyzed = 100% coverage**;
- errors = 0;
- data section = **5.427s**.

Missing symbols are never remapped to another token.

## INTEGRITY LOCK

Former Worker shorthand mapping is permanently deprecated. It previously allowed ticker collisions such as NAS100/NDX resolving to an unrelated ~19.4 security and SPX resolving to another unrelated ticker.

Rules:
1. exact canonical identity required;
2. Twelve Data timeframes validate `meta.symbol` + `meta.type`;
3. indicators/structure use closed candles only;
4. `/quote.last_quote_at` is provider time;
5. `/price` only after identity proof;
6. no fabricated spread;
7. cash / futures / spot are never interchangeable.

Cash NAS100/US500/DAX/N225 family and exact NQ/MNQ/ES/MES/GC/SI/CL remain `DATA_BLOCK` in the current Grow55 integration until an authoritative exact feed is integrated.

## VALIDATION

Post-V75 audit run `32050497678` = **SUCCESS**: 17 cases, 7 PASS, 10 BLOCKED_AS_DESIGNED, 0 FAIL.

V73 validator run `32050638267` = **SUCCESS**.
V74 validator run `32050656054` = **SUCCESS**.

V73 historical development all-pass claims remain unchanged and are not guaranteed live/OOS win rates.

## V74 EXECUTION RULES — UNCHANGED

1. exact instrument/venue/contract;
2. fresh price + market state;
3. current news/context;
4. D1/H4 bias/liquidity;
5. H1 structure;
6. V73 prior where applicable;
7. M15 tradable location;
8. strict M5 close-confirmed MSS/displacement + retest;
9. structural SL first;
10. RR1 default; RR2 only with >=2.2R clean room after costs;
11. final execution-venue quote/spread before MARKET.

V75 `m5TriggerPrefilter` is only a fast filter, not a replacement for strict V74 confirmation.

## ACTIVE RUNTIME

Workflows: `fetch-market.yml`, `scan-forex.yml`, `live-crypto-v75-scan.yml`, `audit-market-data.yml`, `validate-nocut-v73.yml`, `validate-live-v74.yml`.

Scripts: `twelvedata_market.py`, `fetch_crypto.py`, `scan_forex_v75.py`, `scan_crypto_v75.py`, `audit_market_data.py`, `nocut_intraday_method_v73.py`, `validate_nocut_v73.py`, `live_symbol_analysis_v74.py`.

Legacy research/diagnostics stay in Git history only.

## REMAINING LATENCY

The data engines are now very fast. The main remaining user-facing delay is **GitHub Actions runner provisioning + checkout + commit**. Removing that requires a persistent live service/edge cache; more micro-optimization inside the API calls will not remove runner startup latency.

## NEW CHAT INSTRUCTION

`Continue Trading with V73 frozen + V74 execution rules + V75 Fast Data. Read decision.json / forex-fast.json / crypto-fast.json first. Never trust shorthand ticker identity, never proxy cash/futures, never label stale data live, and never fabricate bid/ask.`
