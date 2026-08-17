# MASTER TRADING STATE

Updated: 2026-08-18 UTC+7
Purpose: single canonical state for the Trading project.

## Read order
1. `CURRENT_HANDOFF.md`
2. `ENTRY_EXECUTION_V76.md`
3. `NO_CUT_INTRADAY_ALLPASS_V73.md`
4. `LIVE_SYMBOL_ANALYSIS_V74.md`
5. `TWELVEDATA_GROW55_DATA_POLICY.md`
6. relevant market checkpoint.

# CURRENT ARCHITECTURE

## V73 — frozen statistical prior

V73 is frozen. No live or research workflow may rebuild/optimize it.

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

## V74 — live analysis / execution authority

V74 remains the live decision authority over V73.

Order:
1. exact instrument / venue / contract;
2. fresh timestamped data;
3. current symbol-specific news/context;
4. D1/H4 liquidity/regime;
5. H1 structure;
6. frozen V73 prior where applicable;
7. M15 tradable location;
8. strict M5 close-confirmed MSS/displacement + retest;
9. structural SL first;
10. RR1 default; RR2 only with >=2.2R clean room after costs;
11. final execution-venue quote/spread before MARKET;
12. forward-log without retuning from the outcome.

Coverage: 28 Forex + 61 Crypto = 89/89 V74 playbooks.

## V75 — Fast Data layer

V75 changes data latency/read efficiency only. It does not weaken V74 or modify V73.

Preferred live artifacts:
- single symbol → `data/decision.json`;
- Forex scan → `data/forex-fast.json`;
- Crypto scan → `data/crypto-fast.json`.

Supported non-crypto uses `scripts/twelvedata_market.py` (`V4-TWELVEDATA-FAST-STRICT`): exact identity/type, D1/H4/H1/M15/M5 parallel fetch, closed candles, `/quote.last_quote_at` provider time, `/price` only after identity proof, >65s hard stale block, no fabricated bid/ask.

Forex 28-pair benchmark `32049900306`: 28 H1 + Top3 deep data section 0.643s once runner active. Crypto universe benchmark `32050388431`: 57/57 exact available OKX USDT instruments analyzed, 0 errors, 5.427s data section.

## V76 — Forex Entry Research R2

V76 is a research/execution-gate layer after V75; it does not modify V73/V74/V75.

**R2 final result is locked and negative for live promotion:**
- six objective setup families A–F;
- CLOSE/RETEST/LIMIT_FVG × STRUCTURE/STRUCTURE_ATR × RR1/RR2 = 72 variants;
- exact 28-pair Forex research;
- 30,000 M5 bars/pair, approximately 2026-05-05 through 2026-08-17;
- chronological 60% DEV / 20% VALIDATION / 20% untouched OOS;
- DEV ranks, VALIDATION gates, OOS only promotes/rejects and never retunes;
- retained global archetypes: **NONE**;
- promoted Forex symbols: **0/28**;
- all 28 methods = `RESEARCH_ONLY`;
- research candidates only: `C_SWEEP_FVG`, `D_BREAK_RETEST_CONT`;
- fully rejected in R2: A_SWEEP_MSS, B_H1_PULLBACK_RECLAIM, E_FAILED_BREAK_REV, F_IFVG_RECLAIM.

No V76 R2 Forex method may authorize a live order. `scripts/entry_v76.py` accepts only methods version `V76-ENTRY-METHODS-R2` and returns NO_ENTRY for non-promoted methods. Pilot R1 is explicitly blocked.

Do not tune R2 after reading OOS. New filters/hypotheses require a separately versioned generation with a new untouched OOS window.

Canonical V76 files:
- `scripts/research_v76_entry_forex.py`
- `scripts/evaluate_v76_entry_forex.py`
- `scripts/fetch_v76_history.py`
- `scripts/run_v76_entry_research.py`
- `scripts/entry_v76.py`
- `scripts/summarize_v76.py`
- `data/v76_entry_research.json`
- `data/v76_entry_methods.json`
- `data/v76_entry_summary.json`
- `data/v76_pair_table.md`
- `docs/checkpoints/ENTRY_EXECUTION_V76.md`

Historical high-impact macro-event windows were not fabricated because the canonical research feed lacks a complete timestamped historical macro calendar. Current V74 news/context refresh remains mandatory live. Historical transaction cost is modeled as fixed 0.05R because historical broker bid/ask is unavailable.

# MARKET DATA INTEGRITY

The old Cloudflare shorthand Worker is not canonical runtime. Same-text ticker collisions are rejected.

Rules:
1. explicit canonical identity;
2. exact provider symbol/type metadata;
3. closed candles only for technical calculations;
4. provider timestamp != fetch time;
5. aggregated price != executable quote;
6. stale data is never called live;
7. no fabricated spread;
8. cash index, futures and spot are never interchangeable.

Current routing:
- Forex: direct strict Twelve Data Grow55 exact `AAA/BBB` mapping;
- Crypto: exchange-native Binance/OKX/Bybit; OKX exact USDT spot for universe scan;
- spot metals/energy: exact Twelve Data identity when supported/fresh;
- NAS100/US500/DAX/N225-family cash indices: `DATA_BLOCK` in current Grow55 integration;
- exact NQ/MNQ/ES/MES/GC/SI/CL futures: `DATA_BLOCK` until an authoritative exact-contract feed exists.

# VALIDATION EVIDENCE

- Market-data audit `32050497678`: SUCCESS, 7 PASS / 10 BLOCKED_AS_DESIGNED / 0 FAIL.
- V73 validator `32050638267`: SUCCESS.
- V74 validator `32050656054`: SUCCESS.
- V76 final R2 research `32053656572`: SUCCESS.
- V76 compact summary `32054967541`: SUCCESS.
- V76 post-R2 validator `32055039365`: SUCCESS; validates methods R2, 28 pairs, retained=[], conservative intrabar scoring and V73 frozen.

# ACTIVE REPOSITORY

Live workflows:
- `fetch-market.yml`
- `scan-forex.yml`
- `live-crypto-v75-scan.yml`
- `audit-market-data.yml`
- `validate-nocut-v73.yml`
- `validate-live-v74.yml`

Isolated V76 workflows:
- `research-v76-entry.yml`
- `validate-entry-v76.yml`
- `summarize-v76.yml`

Legacy optimizers, old blind tests, one-off diagnostics and obsolete live-data paths remain in Git history only.

# CURRENT LIVE ENTRY RULE

Because V76 R2 promoted 0/28, current Forex live decisions continue under V74 using V75 data. V76 R2 is evidence that the tested A–F mechanical entry families were not robust enough under the locked validation/OOS gates; it is not permission to weaken those gates.

DATA_BLOCK always overrides forced-trade research logic.

NQ/ES Futures: no backtest/live proxy from cash indices. Use exact authoritative futures data only; compare MNQ/MES and choose the stronger setup when such data is available. Structural SL first, then contract count; user framework roughly max SL $500 / target $1,500 when structure supports it.

## Handoff phrase

`Continue Trading with V73 frozen + V74 live authority + V75 Fast Data + V76 R2 locked research-only. V76 R2 retained no archetype and promoted 0/28 Forex symbols; do not retune R2 from OOS and do not let it authorize live orders. Read decision.json / forex-fast.json / crypto-fast.json first. Verify exact instrument, fresh timestamped data, current news/context, D1-H4-H1, M15 location, strict M5 trigger, structural SL and final execution-venue spread. Never proxy cash/futures and never label stale data live.`
