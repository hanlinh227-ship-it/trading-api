# CURRENT HANDOFF — TRADING PROJECT

Updated: 2026-08-17 UTC+7

Read `MASTER_TRADING_STATE.md` first.

## CURRENT MODE

The active architecture is intentionally small:

1. **V73 = frozen no-CUT statistical prior.**
2. **V74 = live-analysis / execution layer.**
3. **Twelve Data Grow 55 = primary staged data source for Forex and supported non-crypto markets.**
4. **Crypto final quote = exchange-native when venue precision matters.**

Do not rebuild, optimize or reinterpret V73 during live trading. Do not revive deleted legacy workflows/scripts unless the user explicitly asks for historical research recovery from Git history.

## REPOSITORY CLEANUP — COMPLETED

The active `main` branch was rebuilt as a lean canonical tree in cleanup commit:
- `0b83ae9c199567ec6b8d336d57ff1202b8f19b29`

The active tree was reduced to **29 canonical files**:
- 6 active workflows;
- 4 active scripts;
- 6 active data/request/output files;
- 9 current checkpoint documents;
- 4 root files.

Removed from the active tree:
- V7–V72 optimizer/research generations;
- V73 rebuild machinery;
- legacy blind-test workflows;
- calibration suites;
- provider snapshot collectors;
- probe/debug workflows;
- obsolete Basic-plan throttling paths;
- temporary summary/result files not required by current runtime.

Nothing was permanently lost: historical research remains recoverable from Git history. It must not be restored to `main` unless explicitly needed for historical inspection or a new versioned research branch.

## POST-CLEANUP REGRESSION VALIDATION

All six active workflows have been exercised successfully after cleanup:

1. V73 frozen validator — run `32044530996` — **SUCCESS**.
2. V74 89-playbook validator — run `32044541554` — **SUCCESS**.
3. Canonical single-symbol crypto path — run `32044583127` — **SUCCESS**.
   - AAVEUSDT resolved to OKX;
   - exchange quote timestamp verified;
   - bid/ask verified;
   - quote age ~1.34s at validation;
   - 5/5 timeframes;
   - executionReady=true for that snapshot.
4. Grow55 28-pair Forex universe scan — run `32044589134` — **SUCCESS**.
   - 28/28 pairs scanned;
   - Top 3 deep 5-timeframe analysis completed;
   - `/price` semantics correctly remain aggregated-reference only.
5. Canonical single-symbol Forex path — run `32044639438` — **SUCCESS**.
   - EURUSD returned 5/5 analysis and latest Twelve Data `/price`;
   - quoteTimestampVerified=false;
   - bid/ask/spread unverified;
   - executionReady=false by design until venue confirmation.
6. Fast Forex aggregated-price refresh — run `32044677848` — **SUCCESS**.
7. Live Crypto V74 universe scan — run `32044672835`, job `95429938876` — **SUCCESS**.
   - OKX market fetch and V74 candidate ranking completed successfully.

Therefore there is no known active workflow dependency on the removed legacy files.

## V73 FROZEN RESULT

- Forex 28/28 PASS, minimum development WR 80.00%.
- Crypto 61/61 PASS, minimum development WR 80.22%.
- Forex H1.
- 59 Crypto H1.
- TON/IP dedicated 4H.
- current frozen maps use exactly 1 trade/day and RR1:1.
- classification: exposed development all-pass, not untouched OOS.

Runtime source of truth:
- `data/nocut_intraday_allpass_v73.json`
- `scripts/nocut_intraday_method_v73.py`
- `scripts/validate_nocut_v73.py`

V73 build/re-optimization files are intentionally absent from `main`.

## V74 LIVE RULES

For every live Forex/Crypto setup:
1. exact instrument/venue;
2. current price data and market state;
3. current symbol-specific news/context;
4. D1/H4 bias and liquidity;
5. H1 structure;
6. frozen V73 prior/router only;
7. M15 tradable location;
8. M5 close-confirmed MSS/displacement + retest;
9. structural SL first;
10. RR1 default, RR2 only with >=2.2R clean room after costs;
11. final venue/quote verification before MARKET.

V73 `signalHourUTC` is an observation anchor only. `DUAL_FADE` never means blindly place both sides.

## GROW 55 DATA POLICY

### Forex
Canonical full-universe workflow: `.github/workflows/scan-forex.yml`.

Normal scan allocation:
- 28 broad H1 scans ~28 credits;
- Top 3 x D1/H4/H1/M15/M5 ~15 credits;
- Top 3 latest `/price` refresh ~3 credits;
- normal total ~46/55, reserve ~9.

No routine Basic-plan 65-second waits.

### Single symbol
Canonical workflow: `.github/workflows/fetch-market.yml`.

For non-crypto it fetches in parallel:
- full D1/H4/H1/M15/M5 analysis;
- latest aggregated `/price`;
- M1 reference/context.

For crypto it uses `scripts/fetch_crypto.py` and prioritizes exchange-native bid/ask/timestamp.

### Critical price distinction
For Twelve Data `/price`, the integration receives a latest aggregated price but not an executable broker bid/ask or verified quote-tick timestamp. Therefore the system must not call fetch time a broker quote time and must not fabricate spread.

Crypto target quote age <=10s when exchange timestamp exists. Forex target quote age <=30s when a true quote timestamp exists.

If execution fields are insufficient, return `DATA_BLOCK` or require a venue/platform confirmation rather than fabricating a MARKET-ready quote.

## FUTURES / CASH / METALS

- MNQ/MES futures are separate from NDX/SPX cash.
- exact futures contract/feed must be verified before calling a value live.
- XAUUSD/XAGUSD spot are separate from GC/SI futures.
- cash indices must never silently use futures proxies.

Read the relevant market checkpoint when those instruments are requested.

## ACTIVE TREE

Active workflows only:
- `fetch-market.yml`
- `scan-forex.yml`
- `live-crypto-v74-scan.yml`
- `fast-forex-v74-refresh.yml`
- `validate-nocut-v73.yml`
- `validate-live-v74.yml`

Active scripts only:
- `fetch_crypto.py`
- `nocut_intraday_method_v73.py`
- `validate_nocut_v73.py`
- `live_symbol_analysis_v74.py`

Legacy research must remain outside the active tree. Git history is the archive.

## NEW CHAT INSTRUCTION

`Continue Trading from MASTER_TRADING_STATE.md and CURRENT_HANDOFF.md. Current repo is the cleaned 29-file canonical tree. Use only V73 frozen prior + V74 live playbook + Grow55 current data policy. Never re-optimize V73 or resurrect legacy research. Use staged 28-pair Forex scan, exchange-native crypto quotes, exact futures/cash/spot identity, current news/context, M15 location, M5 confirmed trigger and structural risk.`
