# Trading API

Canonical Trading repository.

## Architecture

- **V73** — frozen no-CUT statistical prior. Never rebuild/optimize during live use.
- **V74** — current live-analysis / execution authority.
- **V75 Fast Data** — speed/data-integrity layer; it does not change V73/V74 trading rules.
- **V76 Entry R2** — locked Forex entry research. Final result: **no retained archetype and 0/28 live-promoted Forex methods**. It is research evidence, not an active signal engine.
- **Twelve Data Grow55** — direct strict source for supported Forex and spot metal/commodity data.
- **Crypto execution data** — exchange-native Binance / OKX / Bybit REST; universe scanner currently uses exact OKX USDT spot.

## Fast live read order

1. single symbol → `data/decision.json`;
2. Forex universe → `data/forex-fast.json`;
3. Crypto universe → `data/crypto-fast.json`;
4. open `status.json`, `latest.json` or detailed scans only when deeper evidence is needed.

V76 research never sits in this live data path. Current Forex live decisions remain V74 using V75 data.

## Live workflows

- `fetch-market.yml` — V75 single symbol.
- `scan-forex.yml` — V75 28-pair Forex scan.
- `live-crypto-v75-scan.yml` — V75 staged Crypto scan.
- `audit-market-data.yml` — cross-market integrity audit.
- `validate-nocut-v73.yml` — frozen V73 validation.
- `validate-live-v74.yml` — V74 playbook validation.

## Isolated V76 workflows

- `research-v76-entry.yml` — explicit research only.
- `validate-entry-v76.yml` — compile/protocol/R2-method validation.
- `summarize-v76.yml` — builds compact JSON + 28-pair markdown summary.

## V76 R2 result

Research run `32053656572` completed successfully using 30,000 M5 bars per Forex pair, approximately 2026-05-05 through 2026-08-17.

Six objective setup families A–F were tested. Each had 12 variants:
`CLOSE / RETEST / LIMIT_FVG × STRUCTURE / STRUCTURE_ATR × RR1 / RR2` = **72 variants**.

Protocol: chronological **60% DEV / 20% VALIDATION / 20% untouched OOS**. DEV ranks; VALIDATION gates; OOS only promotes/rejects and never retunes. LIMIT_FVG fill-candle scoring is deliberately conservative and same-bar TP+SL is SL.

Final:
- retained archetypes: **NONE**;
- promoted symbols: **0/28**;
- all 28 methods: `RESEARCH_ONLY`;
- C_SWEEP_FVG = best available research candidate for 18 pairs;
- D_BREAK_RETEST_CONT = best available research candidate for 10 pairs;
- A_SWEEP_MSS, B_H1_PULLBACK_RECLAIM, E_FAILED_BREAK_REV and F_IFVG_RECLAIM are fully rejected in this R2 hypothesis set.

C/D are **not live-approved strategies**. Do not retune R2 after seeing OOS to force a pass.

Compact evidence:
- `data/v76_entry_summary.json`;
- `data/v76_pair_table.md`;
- detailed `data/v76_entry_research.json` and `data/v76_entry_methods.json`.

`scripts/entry_v76.py` accepts only `V76-ENTRY-METHODS-R2`, blocks pilot/old methods, and returns NO_ENTRY for every current R2 method because none is OOS-promoted.

## Active data / execution scripts

- `twelvedata_market.py` — `V4-TWELVEDATA-FAST-STRICT`.
- `fetch_crypto.py` — exchange-native single-symbol Crypto.
- `scan_forex_v75.py` — fast 28-pair Forex scan.
- `scan_crypto_v75.py` — fast staged Crypto scan.
- `live_symbol_analysis_v74.py` — V74 playbooks.
- `nocut_intraday_method_v73.py` + `validate_nocut_v73.py` — frozen V73 reader/validator.
- `audit_market_data.py` — data integrity audit.

## V76 scripts

- `research_v76_entry_forex.py` — objective setup primitives/metrics; not the canonical full research entrypoint.
- `evaluate_v76_entry_forex.py` — conservative R2 evaluator.
- `fetch_v76_history.py` — grouped quota-safe M5 history fetcher.
- `run_v76_entry_research.py` — canonical full R2 research runner.
- `entry_v76.py` — post-V75 safety gate.
- `summarize_v76.py` — compact result/table builder.

## Historical-data limitations

Historical broker bid/ask was unavailable, so R2 uses a fixed 0.05R round-trip cost model. A complete timestamped historical high-impact macro calendar was not available in the canonical research feed, so V76 does not fabricate before/after-news labels from volatility. Current V74 news/context checks remain mandatory live.

## V75 speed

Forex Grow55 staged scan remains ~46/55 credits with 9 reserve. Benchmark `32049900306`: 28 pairs + Top3 deep market-data section **0.643 s** once runner was active.

Crypto benchmark `32050388431`: 57/57 exact available OKX USDT instruments analyzed, zero errors, **5.427 s** data section.

## Data integrity

A ticker string never proves identity. Require canonical mapping + exact provider metadata; indicators use closed candles; provider timestamp is distinct from fetch time; never fabricate bid/ask/spread; never proxy cash/futures/spot.

Twelve Data non-crypto quote >65s → `DATA_BLOCK`; V74 Forex MARKET target <=30s when a real timestamp exists. Crypto final quote target <=10s with venue bid/ask.

Cash NAS100/US500/DAX/N225 families and exact NQ/MNQ/ES/MES/GC/SI/CL remain `DATA_BLOCK` in the current Grow55 integration until authoritative exact feeds exist.

## Validation / checkpoints

- Post-V75 cross-market audit `32050497678`: SUCCESS, 7 PASS / 10 BLOCKED_AS_DESIGNED / 0 FAIL.
- V73 validator `32050638267`: SUCCESS.
- V74 validator `32050656054`: SUCCESS.
- V76 R2 research `32053656572`: SUCCESS.
- V76 summary/table `32054967541`: SUCCESS.
- V76 post-R2 validator `32055039365`: SUCCESS; methods R2, 28 pairs, retained=[], promoted=[], conservative fill behavior and V73 frozen all validated.

Read in order:
1. `docs/checkpoints/MASTER_TRADING_STATE.md`
2. `docs/checkpoints/CURRENT_HANDOFF.md`
3. `docs/checkpoints/ENTRY_EXECUTION_V76.md`
4. relevant data/market checkpoint.

Legacy optimizer/research generations remain in Git history and must not be confused with current runtime. Any future entry hypothesis after V76 R2 must be separately versioned with a new untouched OOS window rather than rewriting R2.
