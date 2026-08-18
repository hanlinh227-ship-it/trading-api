# TRADING CHAT HANDOFF — DURABLE CHECKPOINT

Last updated: 2026-08-18
Repository: hanlinh227-ship-it/trading-api
Production Worker: https://trading-v77-scanner.hanlinh227.workers.dev
Current verified production generation: V77.13.1 (ALWAYS re-read cloudflare-worker/index.js; newer GitHub state overrides this line)

## PURPOSE
This is the durable canonical handoff for a new ChatGPT conversation. Read this file FIRST, then inspect current runtime, newest diagnostics/live reports, workflows and recent commits. Never rely on a version number remembered from chat.

## USER INTENT
Build an adaptive Trading Hub for Forex, Crypto, Metals and later Futures/MT5 execution. Every symbol should use its own knowledge/profile and the best regime currently allowed for that symbol, while all candidates normalize to one comparable Hub readiness/quality model. Do not force all symbols through one identical entry recipe. Entry freedom must never become forced trading. WATCH/indicative entry is acceptable when trigger/news/execution is not ready. SL/TP must follow invalidation, structure, liquidity/support-resistance and realistic room; RR is an outcome of structure, not a cosmetic fixed target. Never claim a guaranteed win rate. Only OOS/walk-forward/forward-shadow evidence may calibrate claimed performance.

## CANONICAL SOURCES
- Runtime: `cloudflare-worker/index.js`
- Frozen development prior: `data/nocut_intraday_allpass_v73.json`
- Machine-readable knowledge: `data/symbol_knowledge_registry.json`
- Durable live order state: KV `v775:books` (WATCH is NOT durable)
- Fresh scan snapshots: KV prefix `v7712:scan:` (TTL; analysis only)
- Order history: KV `v7712:order_history`
- Forward research/shadow setups: KV `v7713:shadow_setups`
- Massive secret already added in Cloudflare as `MASSIVE_API_KEY`; Futures integration is pending until current entry foundation is considered stable.

## CORE ARCHITECTURE — DO NOT REGRESS
- V73 is FROZEN PRIOR/REFERENCE, not a standalone production BUY/SELL engine. It is exposed development and must not be presented as untouched OOS proof.
- Symbol identity is exact. Current canonical rename: old TON user input maps intentionally to current `GRAMUSDT`; only the historical V73 prior key maps GRAM→TON. Market-data identity stays GRAM.
- Dynamic regime router: V73/knowledge determines ALLOWED modes; current D1/H4/H1/M15/M5 + context chooses ACTIVE mode. Modes include TREND, RELATIVE, MEAN_REVERSION, GENERIC.
- TREND/MOMENTUM may use quality continuation/reclaim/break entries; RELATIVE/HYBRID may use relative context + structure; MEAN_REVERSION remains stricter and requires reversal/extension evidence. Do not restore a single universal M15/M5 gate.
- Hub score = setup readiness/quality, NOT win probability.
- Structure/liquidity SL/TP is mandatory. V77.13 adds adaptive minimum structural RR quality rather than using a distant target merely to make RR look attractive.
- Analysis-only data NEVER authorizes execution.
- News/context gate remains strict where not automatically sourced; do not fabricate current news.

## CURRENT SYMBOL KNOWLEDGE — V2
`data/symbol_knowledge_registry.json` contains 91 profiles:
- 28 Forex pairs
- 61 Crypto symbols
- XAUUSD
- XAGUSD
Each entry stores canonical identity/aliases, families, allowed modes, entry style metadata, riskATR where known, information/news drivers, production SL/TP policy and calibration state. Forex/Crypto V73 statistics are explicitly tagged `PRIOR_ONLY_UNCALIBRATED`; Metal knowledge is also uncalibrated. XAU context requirements include USD/DXY regime, Treasury/real-yield proxy, Fed expectations, US CPI/PCE/NFP, safe-haven/geopolitical context, XAG relative strength and session/liquidity. XAG adds industrial/risk-cycle context.

## MARKET DATA / EXECUTION AUTHORITY
### Crypto
- Universe: 61 canonical symbols.
- Broad discovery: Bybit/OKX/Binance bulk + KuCoin/Gate broad + short-lived KV cache as needed.
- Deep analysis: exact 5TF. Bybit/OKX/Binance are canonical execution venues. KuCoin/Gate may provide ANALYSIS-ONLY 5TF fallback during canonical rate-limit/unavailability.
- Final MARKET/LIMIT requires fresh exact canonical bid/ask, executionVerified, structural plan, acceptable spread/cost and news/context clearance.
- Latest verified coverage has reached 60/61 with deep 3/3.
### Forex
- 28 pairs via Twelve Data batch analysis/reference data.
- Currency-strength context from the 28-pair matrix.
- MARKET/LIMIT remains blocked until a broker/MT5 execution quote exists.
### Metals
- XAUUSD/XAGUSD via Twelve Data analysis/reference data plus metal-relative context.
- MARKET/LIMIT remains blocked until broker/MT5 execution quote exists.
### Futures
- `MASSIVE_API_KEY` already exists in Cloudflare Secret.
- NQ/ES/MNQ/MES integration is the next separate project phase; do not let it regress current Forex/Crypto/Metal engine.

## FRESH SCAN VS DURABLE ORDERS — V77.12+
This invariant is mandatory:
1. Every Hub/group button press creates a NEW scan with a new `scanId` and `scannedAt` and fetches current available market data. Hub Top Setups come only from that run.
2. WATCH/setup candidates are ephemeral. They are never stored in durable Books. If a scan is BUSY or RATE_BUDGET_WAIT, Telegram must NOT substitute an old WATCH as a fresh result.
3. `/latest-scan?group=...` exposes the latest short-lived snapshot for diagnostics only.
4. Executable MARKET/LIMIT/PENDING orders are durable in KV and survive code/Worker updates.
5. A symbol already present in durable MARKET/LIMIT/PENDING state is excluded from the deep-entry candidate scan (`liveSymbolsSkipped`) so the engine does not treat an already-running trade as a new entry opportunity.
6. `/orders`/`/books` show durable executable state only; WATCH count should remain zero there.
7. Lifecycle events (limit fill/expiry, TP/SL where supported) are appended to persistent order history. Future MT5 positions must use broker ticket/execution authority and broker reconciliation as source of truth.

## VERIFIED V77.12 FRESH-STATE BEHAVIOR
`V77120_LIVE_CHECK.txt` PASS:
- Two consecutive Crypto button-style scans produced different scanIds.
- Both scans: Crypto 60/61 broad, deep 3/3.
- `/latest-scan` matched the second scan.
- Durable order state before/after scans was unchanged.
- Durable WATCH = 0.
- `/hub` created its own fresh hubScanId and new scanIds for Crypto/Forex/Metal.

## V77.13 / V77.13.1 QUALITY + CALIBRATION LAYER
V77.13 introduced:
- runtime import of symbol knowledge registry;
- realistic structural target tiering instead of choosing an arbitrary farthest target;
- adaptive `minimumQualityRR` and `RR_QUALITY_REQUIRED` gate;
- knowledge/calibration metadata in analyses;
- forward shadow setup recording to build future evidence;
- `/knowledge?symbol=...` and `/shadow` diagnostics.

Current adaptive minimum structural RR policy is deliberately modest and UNCALIBRATED: roughly MEAN_REVERSION 1.0, TREND 1.2, RELATIVE 1.15, GENERIC 1.25, with a small allowance for exceptionally high method fit. These are quality floors, not promised optimal values. Future data may change them.

V77.13.1 added:
- XAU/XAG knowledge profiles; knowledge registry count = 91.
- live/pending order symbols excluded from deep-entry scans.
- diagnostics include `liveSymbolsSkipped`.

## VERIFIED V77.13 / V77.13.1 STATE
`V77130_DIAGNOSTIC.txt`: generator=0, migration=0, Worker syntax=0; knowledge import, RR-quality layer, shadow log and endpoints present.
`V77130_ISOLATED_CHECK.txt`: syntax PASS, npm PASS, prepare-wrangler PASS, Wrangler dry-run PASS; isolated clean-minute Forex 28/28 deep 3/3, Metal 2/2 deep 2/2, zero broad errors, durable WATCH zero. A prior immediate test showing Forex/Metal 0/28 and 0/2 was Twelve Data quota contention from simultaneous workflows, not an entry-engine regression.
`V77131_DIAGNOSTIC.txt`: generator=0, migration=0, Worker syntax=0, knowledge count=91, XAU/XAG knowledge present, live-skip/fresh-scan/persistent-order invariants present.
`V77131_LIVE_CHECK.txt`: VERSION=V77.13.1, status OK, Crypto 60/61 deep 3/3, XAU knowledge endpoint OK, KAITO knowledge `TREND/RELATIVE`, durable orders preserved across scan, durable WATCH zero, VERDICT=PASS.

## FORWARD CALIBRATION — IMPORTANT
Current shadow setup storage is a DATA COLLECTION layer, not a completed win-rate model. It records prospective WATCH setups with valid plans and dedupes repeated symbol/mode samples. It does NOT yet resolve every setup into path-aware TP/SL/timeout outcomes. Therefore:
- do not call Hub score a win probability;
- do not quote V73 development WR as expected future WR;
- do not optimize thresholds from a handful of live examples;
- next research improvement is a path-aware shadow/walk-forward evaluator using future 5m candles and no lookahead, grouped by symbol + active mode + entry style + session/context.
Desired calibration metrics: sample size, fill rate, TP1/TP2, SL, timeout, mean/median R, profit factor, losing streak, and uncertainty/confidence bounds. Threshold changes should require enough independent samples and should be walk-forward validated.

## NEXT PRIORITIES
1. Build the path-aware forward/walk-forward outcome evaluator and calibration report. Do not auto-change production thresholds until evidence is sufficient.
2. Add correlation/exposure control so Hub Top3 does not represent three versions of the same USD/BTC macro bet.
3. Add a trustworthy automated macro/news source when available. The knowledge registry already defines WHAT information each symbol needs; until a feed is connected, keep the news gate honest/manual.
4. Integrate Massive Futures for NQ/ES/MNQ/MES, then use futures context for later NAS100/US500 MT5 cash-CFD analysis without confusing futures prices with broker CFD execution prices.
5. Build MT5 Bridge only after the analysis foundation remains stable. Cloudflare stays the brain; MT5/broker quote and ticket become execution truth.

## SUCCESS CRITERIA FOR ANY FUTURE PROMOTION
- GitHub generator/syntax/invariants/Wrangler dry-run PASS.
- Production `/status` reports the intended version and services healthy.
- Fresh Hub scan produces new scan identity; no stale WATCH masquerades as current.
- Durable live orders remain unchanged through scans/code updates unless lifecycle/broker state legitimately changes them.
- Active/pending order symbols are not treated as new entry candidates.
- Crypto broad >=55/61 (prefer >=59/61) and deep 3/3 when at least three analyzable candidates exist.
- Forex 28/28 deep 3/3 on a clean Twelve Data quota window; quota waits must be reported honestly.
- Metal 2/2 deep 2/2.
- No legacy `TP ?`, fixed fake scores, or broad/analysis-only execution leakage.
- Indicative entries are clearly non-executable.
- Executable orders require fresh execution authority + structure + cost + news gates.
- Never weaken a validator solely to get PASS.

## CONTINUATION PROTOCOL FOR A NEW CHAT
1. Read this file FIRST.
2. Fetch `cloudflare-worker/index.js` and determine ACTUAL `CONFIG.version`; newer GitHub state overrides this document.
3. Inspect newest `V*_DIAGNOSTIC.txt`, `V*_LIVE*.txt`, build/market reports, workflows and recent commits.
4. Reproduce/verify the newest failure before editing unless a newer diagnostic already proves it.
5. Preserve architecture and exact-symbol identity. Do not roll back to V77.7/V77.8/V77.9 legacy behavior.
6. Every major migration must leave diagnostic/build/live traces in GitHub.
7. Update THIS file after a major verified architecture/state change.

## SAFETY / TRUTHFULNESS
No scanner can guarantee a stable win rate. Optimize for robust expectancy after costs, drawdown control and repeatability, then measure with OOS/walk-forward data. Never label stale/reference data as executable live price. Never infer executable orders from broad discovery, analysis-only fallback, or a cosmetically attractive RR.
