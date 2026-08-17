# MASTER TRADING STATE

Updated: 2026-08-17 UTC+7
Purpose: single canonical state for the Trading project after repository cleanup.

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

**V73 is frozen. Rebuild/optimizer generations are no longer part of the active tree.** Their history remains recoverable in Git history and in the frozen artifact itself. This prevents accidental retuning or executing an old research version.

Integrity classification:
**EXPOSED DEVELOPMENT ALL-PASS; NOT UNTOUCHED OOS.**
The historical development WR is not a future/live guarantee.

## V74 — current live-analysis / execution layer
Every live Forex/Crypto analysis uses V74 over the frozen V73 prior.

Canonical files:
- `scripts/live_symbol_analysis_v74.py`
- `docs/checkpoints/LIVE_SYMBOL_ANALYSIS_V74.md`
- `.github/workflows/validate-live-v74.yml`

Coverage validation remains:
- 28 Forex + 61 Crypto = 89/89 live playbooks;
- all current crypto identities mapped explicitly;
- no live generic `OTHER` profile fallback;
- V73 signal hour is an observation anchor only;
- `DUAL_FADE` is geometry, never a blind two-sided order.

# LIVE DECISION ORDER
1. Resolve exact symbol / instrument / venue / contract.
2. Refresh current market data.
3. Refresh current symbol-specific news/macro/project context.
4. D1/H4 draw-on-liquidity, regime, premium/discount.
5. H1 structure and only point-in-time observable features.
6. Read the frozen V73 prior/router without optimizing it.
7. Require M15 tradable location.
8. Require M5 close-confirmed MSS/displacement + retest for strict execution.
9. Structural SL first; ATR only a volatility floor.
10. Default RR1; RR2 only when at least 2.2R clean structural room remains after costs.
11. Verify final price / timestamp / spread before MARKET.
12. Record the forward result without retuning from that outcome.

# DATA ARCHITECTURE — GROW 55

Primary policy: `TWELVEDATA_GROW55_DATA_POLICY.md`.

## Forex
- Twelve Data Grow 55 is the primary aggregated data source.
- 28-pair scan uses staged quota allocation: broad universe -> Top 3 deep D1/H4/H1/M15/M5 -> final latest price refresh.
- Current normal budget is approximately 46/55 credits per full scan, leaving reserve for retries or final refresh.
- fixed Basic-plan `sleep 65` batches are removed.

## Crypto
- final execution quote is exchange-native Binance / OKX / Bybit where supported;
- exact venue, bid, ask and exchange timestamp take priority over an aggregated quote;
- Twelve Data may enrich/cross-check history or broader market context when useful.

## Futures
- Futures are separate from cash indices;
- MNQ/MES are the preferred execution instruments for the NQ/ES system;
- use Twelve Data only if the exact futures instrument/contract is verified;
- otherwise use an authoritative futures feed or the user's platform price;
- never proxy cash NAS100/SPX as NQ/ES or vice versa.

## Cash indices
- use actual cash-index symbols/feeds only;
- never substitute NQ/ES/MNQ/MES;
- verify provider entitlement and market state before calling a value live.

## Metals
- XAUUSD/XAGUSD spot remain separate from COMEX futures;
- use verified spot/commodity identity and current macro context.

# PRICE INTEGRITY

For live execution, distinguish three concepts:
1. **latest aggregated price fetched now**;
2. **market quote timestamp freshness**;
3. **executable venue bid/ask spread**.

They are not interchangeable.

- Crypto target quote age <=10s and should normally have exchange bid/ask.
- Forex target quote age <=30s when a true quote timestamp is available.
- Twelve Data `/price` can provide the latest aggregated price but this integration does not treat its fetch timestamp as a broker quote timestamp and does not invent bid/ask.
- If exact venue/contract, quote freshness or required spread cannot be verified, return `DATA_BLOCK` rather than fabricate execution data.

# ACTIVE REPOSITORY SCOPE

Active workflows:
- `fetch-market.yml`
- `scan-forex.yml`
- `live-crypto-v74-scan.yml`
- `fast-forex-v74-refresh.yml`
- `validate-nocut-v73.yml`
- `validate-live-v74.yml`

Active scripts:
- `fetch_crypto.py`
- `nocut_intraday_method_v73.py`
- `validate_nocut_v73.py`
- `live_symbol_analysis_v74.py`

Legacy blind tests, calibration suites, one-off provider probes, old optimizer versions, old result JSONs and snapshot-fetch workflows are not part of the current architecture and are removed from the active tree after conclusions are checkpointed. Git history remains the archive.

# SPECIAL MARKET RULES

## NQ/ES Futures
Compare NQ/ES or MNQ/MES and normally choose one better setup. Structural SL is set first, then contract count. User risk framework remains approximately USD 500 maximum SL and USD 1,500 target when structure genuinely permits it.

## Live trade frequency
The frozen V73 minimum-trade research rule does not authorize fabricated prices or stale MARKET orders. `DATA_BLOCK` remains mandatory when data integrity fails.

## Handoff phrase
`Tiếp tục Trading từ MASTER_TRADING_STATE.md. Current state = V73 frozen prior + V74 live layer + Twelve Data Grow55 staged market-data policy. Do not rebuild/re-optimize V73 or resurrect deleted legacy research. For live analysis verify exact instrument, current data, current news/context, D1-H4-H1 bias, V73 prior, M15 location, M5 confirmed trigger, structural SL and final execution data.`
