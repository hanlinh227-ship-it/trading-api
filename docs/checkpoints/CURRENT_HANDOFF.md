# CURRENT HANDOFF — TRADING PROJECT

Updated: 2026-08-18 UTC+7

Read `MASTER_TRADING_STATE.md` first, then `ENTRY_EXECUTION_V76.md`.

## CURRENT MODE

- **V73** = frozen no-CUT statistical prior. Never rebuild/optimize during live use.
- **V74** = live-analysis / execution authority.
- **V75 Fast Data** = current collection/ranking/read-speed layer.
- **V76 R2** = locked Forex entry research with a **negative live-promotion result**: no retained archetype, 0/28 promoted.
- Forex / spot metals = Twelve Data Grow55 direct strict V4.
- Crypto = exchange-native; exact venue/bid/ask/timestamp required.
- Unsupported/ambiguous cash index or exact futures = `DATA_BLOCK`, never proxy.

## FAST LIVE READ ORDER

1. single symbol → `data/decision.json`;
2. Forex universe → `data/forex-fast.json`;
3. Crypto universe → `data/crypto-fast.json`;
4. open detailed status/latest/scan files only when needed.

V76 research is not in this latency path.

## V76 R2 — FINAL LOCKED RESULT

Research run `32053656572` = SUCCESS.

Protocol:
- 28 Forex pairs;
- 30,000 M5 bars per pair, roughly 2026-05-05 → 2026-08-17;
- six objective setup families A–F;
- CLOSE/RETEST/LIMIT_FVG × STRUCTURE/STRUCTURE_ATR × RR1/RR2 = 72 variants;
- chronological 60% DEV / 20% VALIDATION / 20% untouched OOS;
- DEV ranks, VALIDATION gates, OOS only promotes/rejects;
- same-bar TP+SL=SL;
- conservative LIMIT_FVG fill-bar scoring;
- fixed historical cost 0.05R;
- no fabricated historical news-event labels.

Final:
- `retainedArchetypes = []`;
- `promotedSymbols = []`;
- all 28 symbols = `RESEARCH_ONLY`;
- 18 selected-best research candidates use `C_SWEEP_FVG`;
- 10 use `D_BREAK_RETEST_CONT`;
- A/B/E/F are fully rejected in this R2 hypothesis set;
- C/D are only research candidates, **not live-approved methods**.

Canonical evidence:
- `data/v76_entry_research.json`;
- `data/v76_entry_methods.json`;
- `data/v76_entry_summary.json`;
- `data/v76_pair_table.md`.

Post-R2 validator `32055039365` = SUCCESS and confirms `V76-ENTRY-METHODS-R2`, 28 pairs, retained=[], conservative scoring and V73 frozen.

### Live implication

**V76 R2 currently authorizes no Forex order.**

`scripts/entry_v76.py` accepts only `V76-ENTRY-METHODS-R2`; R1/pilot is blocked, and every current R2 method returns `NO_ENTRY / METHOD_NOT_OOS_PROMOTED` because `liveEligible=false`.

Do not loosen gates or retune thresholds after reading R2 OOS. Any new filters/hypotheses must become a separately versioned research generation with a new untouched OOS window.

Current Forex live entry therefore remains V74 using V75 data and current news/execution confirmation.

## SINGLE SYMBOL V75

Workflow: `.github/workflows/fetch-market.yml`.

Non-crypto engine: `scripts/twelvedata_market.py`, `V4-TWELVEDATA-FAST-STRICT`.
- D1/H4/H1/M15/M5 in parallel;
- closed candles only;
- full indicator history in RAM, compact tails stored;
- `/quote` proves identity/timestamp before `/price`;
- quote >65s => DATA_BLOCK;
- V74 Forex review target <=30s;
- Twelve Data broker bid/ask are never fabricated.

Crypto engine: `scripts/fetch_crypto.py`.
- exact exchange symbol;
- five TF in parallel;
- final ticker refresh;
- target quote age <=10s;
- real exchange bid/ask required.

## FOREX UNIVERSE V75

Workflow `scan-forex.yml`, engine `scan_forex_v75.py`, outputs `forex-fast.json` + deeper `forex-scan.json`.

Pipeline: 28 H1 broad → Top3 D1/H4/M15/M5 + quote/price. Grow55 budget ≈46/55, reserve 9.

Benchmark `32049900306`: data portion 0.643s once runner active.

## CRYPTO UNIVERSE V75

Workflow `live-crypto-v75-scan.yml`, engine `scan_crypto_v75.py`, output `crypto-fast.json`.

Pipeline: 61 V74 identities → exact OKX USDT availability → all available H1 → Top12 M15/M5 → Top5 D1/H4 → live bid/ask/timestamp.

Benchmark `32050388431`: 57 exact available instruments, 57/57 analyzed, 0 errors, 5.427s data portion.

Missing identities are never remapped to another token.

## DATA INTEGRITY LOCK

The old shorthand Worker is permanently deprecated.

Rules:
1. exact canonical identity;
2. exact provider symbol/type metadata;
3. closed candles for technical calculations;
4. provider timestamp != fetch time;
5. aggregated/reference price != executable quote;
6. no fabricated bid/ask/spread;
7. cash/futures/spot never interchangeable.

Cash NAS100/US500/DAX/N225-family and exact NQ/MNQ/ES/MES/GC/SI/CL remain `DATA_BLOCK` in current Grow55 integration until authoritative exact feeds exist.

## V74 EXECUTION RULES — STILL AUTHORITATIVE

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

V75 `m5TriggerPrefilter` is only a fast filter. V76 R2 negative research does not remove V74's discretionary evidence stack and does not authorize weaker mechanical entries.

## VALIDATION / RUNS

- Market-data audit `32050497678`: SUCCESS, 7 PASS / 10 BLOCKED_AS_DESIGNED / 0 FAIL.
- V73 validator `32050638267`: SUCCESS.
- V74 validator `32050656054`: SUCCESS.
- V76 R2 research `32053656572`: SUCCESS.
- V76 compact summary/table `32054967541`: SUCCESS.
- V76 post-R2 validator `32055039365`: SUCCESS.

## ACTIVE WORKFLOWS

Live/validation:
- `fetch-market.yml`
- `scan-forex.yml`
- `live-crypto-v75-scan.yml`
- `audit-market-data.yml`
- `validate-nocut-v73.yml`
- `validate-live-v74.yml`

Isolated V76:
- `research-v76-entry.yml`
- `validate-entry-v76.yml`
- `summarize-v76.yml`

## ACTIVE V76 SCRIPTS

- `research_v76_entry_forex.py`
- `evaluate_v76_entry_forex.py`
- `fetch_v76_history.py`
- `run_v76_entry_research.py`
- `entry_v76.py`
- `summarize_v76.py`

Legacy research/diagnostics stay in Git history only.

## NEXT RESEARCH DIRECTION

Do not retune V76 R2 from its OOS. The useful next step is forward observation/logging of C/D plus better historical execution-cost and timestamped macro-event data. A materially new hypothesis set should be a new research version (e.g. V77) with pre-registered rules and a new untouched OOS window.

Do not begin Crypto entry optimization merely to compensate for the negative Forex result. Crypto can be researched separately only with the same anti-overfit discipline when explicitly chosen as the next project stage.

## NEW CHAT INSTRUCTION

`Continue Trading from MASTER_TRADING_STATE.md + CURRENT_HANDOFF.md + ENTRY_EXECUTION_V76.md. Current state = V73 frozen prior + V74 live authority + V75 Fast Data + V76 R2 locked research-only. V76 R2 retained no archetype and promoted 0/28 Forex symbols, so it cannot authorize live entries. Do not retune R2 from OOS. Read decision.json / forex-fast.json / crypto-fast.json first; verify exact instrument, fresh timestamped data, current news/context, D1/H4/H1, M15 location, strict M5 trigger, structural SL and final execution-venue spread. Never proxy cash/futures or fabricate bid/ask.`
