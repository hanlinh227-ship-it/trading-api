# Trading API

Canonical live Trading repository.

## Architecture

- **V73** — frozen no-CUT statistical prior. Never rebuild/optimize during live use.
- **V74** — live-analysis / execution authority.
- **V75 Fast Data** — speed/data-integrity layer; it does not change V73/V74 trading rules.
- **V76 Entry** — isolated Forex entry/execution research + optional post-V75 live gate. Only R2 methods that pass DEV/VALIDATION/OOS gates may be live-eligible.
- **Twelve Data Grow55** — direct strict source for supported Forex and spot metal/commodity data.
- **Crypto execution data** — exchange-native Binance / OKX / Bybit REST; universe scanner currently uses exact OKX USDT spot.

## Fast live read order

1. single symbol → `data/decision.json`;
2. Forex universe → `data/forex-fast.json`;
3. Crypto universe → `data/crypto-fast.json`;
4. open `status.json`, `latest.json` or detailed scans only when deeper evidence is needed.

V76 research never sits in this live data path.

## Live workflows

- `fetch-market.yml` — V75 single symbol.
- `scan-forex.yml` — V75 28-pair Forex scan.
- `live-crypto-v75-scan.yml` — V75 staged Crypto scan.
- `audit-market-data.yml` — cross-market integrity audit.
- `validate-nocut-v73.yml` — frozen V73 validation.
- `validate-live-v74.yml` — V74 playbook validation.

## V76 workflows

- `research-v76-entry.yml` — explicit/manual research only; never auto-runs on ordinary live-data changes.
- `validate-entry-v76.yml` — compile/protocol/method validation.
- `summarize-v76.yml` — builds compact `data/v76_entry_summary.json` when locked methods change.

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
- `fetch_v76_history.py` — quota-safe grouped M5 history fetcher.
- `run_v76_entry_research.py` — canonical full R2 research runner.
- `entry_v76.py` — post-V75 live gate; blocks pilot/old methods and non-promoted methods.
- `summarize_v76.py` — compact result reader.

## V76 protocol

Six objective families A–F are tested: M15 sweep→M5 MSS, H1 trend→M15 pullback→M5 reclaim, sweep→FVG, breakout→retest continuation, failed breakout reversal, and IFVG reclaim.

Each tests 12 variants: CLOSE/RETEST/LIMIT_FVG × STRUCTURE/STRUCTURE_ATR × RR1/RR2 = **72 variants** total.

Research uses chronological **60% DEV / 20% VALIDATION / 20% untouched OOS**. DEV ranks, VALIDATION gates, OOS only promotes/rejects; OOS never retunes thresholds. Conservative LIMIT_FVG scoring prevents fill-bar order look-ahead. Historical news-window claims are not fabricated without a canonical timestamped macro-event feed; current V74 news checks remain mandatory.

Final live flow:
`V75 data → V74 HTF/context → V76 locked symbol method → M15 → M5 → current news → final venue quote/spread → MARKET / LIMIT / NO_ENTRY`.

## V75 speed

Forex Grow55 staged scan remains ~46/55 credits with 9 reserve. Benchmark `32049900306`: 28 pairs + Top3 deep market-data section **0.643 s** once runner was active.

Crypto benchmark `32050388431`: 57/57 exact available OKX USDT instruments analyzed, zero errors, **5.427 s** data section.

## Data integrity

A ticker string never proves identity. Require canonical mapping + exact provider metadata; indicators use closed candles; provider timestamp is distinct from fetch time; never fabricate bid/ask/spread; never proxy cash/futures/spot.

Twelve Data non-crypto quote >65s → `DATA_BLOCK`; V74 Forex MARKET target <=30s when a real timestamp exists. Crypto final quote target <=10s with venue bid/ask.

Cash NAS100/US500/DAX/N225 families and exact NQ/MNQ/ES/MES/GC/SI/CL remain `DATA_BLOCK` in the current Grow55 integration until authoritative exact feeds exist.

## Validation / checkpoints

Post-V75 cross-market audit `32050497678`: SUCCESS, 7 PASS / 10 BLOCKED_AS_DESIGNED / 0 FAIL.

V73 validator `32050638267`: SUCCESS. V74 validator `32050656054`: SUCCESS. V76 protocol validator `32054399860`: SUCCESS and explicitly proves pilot/older methods are blocked from live execution.

Read in order:
1. `docs/checkpoints/MASTER_TRADING_STATE.md`
2. `docs/checkpoints/CURRENT_HANDOFF.md`
3. `docs/checkpoints/ENTRY_EXECUTION_V76.md`
4. relevant data/market checkpoint.

Legacy optimizer/research generations remain in Git history and must not be confused with current runtime.
