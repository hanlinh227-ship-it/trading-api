# TRADING CHAT HANDOFF — DURABLE CHECKPOINT

Last updated: 2026-08-18
Repository: hanlinh227-ship-it/trading-api
Production Worker: https://trading-v77-scanner.hanlinh227.workers.dev

## PURPOSE
This file is the canonical handoff/checkpoint for continuing the Trading project in a new ChatGPT conversation. A new chat must read this file FIRST, then inspect current canonical runtime and newest diagnostic/live-check files. Do not rely on chat memory or an old version number in the prompt.

## USER INTENT
Build and continuously harden an adaptive trading scanner/Hub for Forex, Crypto and Metals. Real-time/fresh data must be preferred. Never pretend stale data is live. Preserve exact-symbol integrity. Do not emit executable MARKET/LIMIT positions unless execution quote and all execution gates pass. Keep improving/testing autonomously when asked, but report truthfully and never call a failing verification PASS.

## CANONICAL RUNTIME
Primary runtime: cloudflare-worker/index.js
V73 reference/config: data/nocut_intraday_allpass_v73.json
Validation workflow: .github/workflows/validate-cloudflare-v77.yml
Live verification workflows/check files may evolve; inspect repository rather than assuming filenames.

## ARCHITECTURE THAT MUST BE PRESERVED
- Adaptive setup scoring via methodAssessment/setupScore; score means setup readiness, not a fake fixed legacy score.
- Structure/liquidity-based SL/TP and validExecutablePosition gate.
- Forex: 28-pair universe, Twelve Data batch analysis, execution quote requirement before executable trade.
- Metals: XAUUSD/XAGUSD, Twelve Data analysis, execution quote requirement before executable trade.
- Crypto: 61-symbol universe. Broad discovery may use exchange-wide public ticker sources/cache, but discovery data NEVER authorizes an executable trade.
- Crypto executable/deep layer must use exact-symbol exchange-native live data, 5TF analysis and fresh bid/ask/execution verification. Bybit/OKX/Binance are the canonical execution/deep venues unless the runtime is deliberately upgraded and revalidated.
- Strict news context/gate remains required where configured.
- Books must not leak legacy incomplete MARKET/LIMIT entries (e.g. TP ? or old fixed scores).
- Preserve KV/state safeguards, run lock, rate-budget logic and truthful diagnostics.

## IMPORTANT HISTORY / FIXES ALREADY DONE
V77.9 migration fixed generator marker duplication and nested-backtick migration failures. Production V77.9.0 came online. Crypto bulk initially failed 0/61 with EXACT_SPOT_UNAVAILABLE. V77.9.1 added resilient exact fallback and reached 57/61 broad + deep 3/3 on a warm attempt. V77.9.2 stabilized cold-start. V77.9.3 added persistent broad discovery cache. V77.9.4 added diversified broad discovery using KuCoin/Gate-style all-ticker sources while retaining strict execution/deep separation.

Forex/Metal verification at V77.9.2 was healthy: Forex 28/28 broad, deep 3/3, 0 broad errors; Metal 2/2, deep 2/2, 0 broad errors. Books had Forex/Metal/Crypto executable MARKET/LIMIT counts at zero when setups were only WATCH, confirming legacy executable leakage cleanup.

## CURRENT KNOWN BLOCKER — DO NOT IGNORE
Latest checked production V77.9.4 result:
STATUS_VERSION=V77.9.4
STATUS_OK=YES
TG_OK=YES
CRYPTO_REQUESTED=61
CRYPTO_BROAD=59
CRYPTO_DEEP=0/3
CRYPTO_ERRORS=2
Top broad candidates WLDUSDT, KAITOUSDT, FILUSDT all returned DATA_BLOCK / EXCHANGE_DEEP_UNAVAILABLE.
VERDICT=FAIL.

Interpretation: broad discovery coverage is now excellent (59/61), but candidate selection can choose symbols discovered by broad venues/cache that are temporarily unavailable to the canonical deep/execution venues, or the broad phase can consume/rate-limit the same venues before deep analysis. This must be fixed before declaring success.

## NEXT ENGINEERING TARGET
Decouple broad discovery from deep/execution availability. Preferred direction:
1. Do NOT spend Bybit/OKX/Binance exact-request budget merely to fill broad coverage when KuCoin/Gate/bulk/cache already provides discovery.
2. Before selecting Top3 for deep analysis, cheaply establish/maintain an execution-venue availability map for candidates, or rank a larger shortlist and skip/replace candidates that cannot be deep-fetched.
3. Deep-analyze sequentially from a ranked shortlist until 3 valid deep analyses are obtained or the shortlist is exhausted. A DATA_BLOCK candidate must not consume one of the final Top3 slots if a lower-ranked executable/deep-available candidate exists.
4. Add controlled cooldown/backoff between discovery and deep calls if needed; avoid request bursts that self-rate-limit.
5. Broad/cache data can rank candidates but can NEVER satisfy fresh bid/ask, executionVerified, 5TF deep analysis, news gate, entry, SL or TP requirements.
6. Keep diagnostics explicit: requested, broadOk, deepRequested, deepOk, skippedUnavailable, provider errors, elapsed time.

## SUCCESS CRITERIA BEFORE REPORTING COMPLETE
All of these should pass on production, preferably on first/cold run:
- /status reports current deployed version, ok=true, KV/TwelveData/Telegram/Hub healthy as applicable.
- Crypto requested=61; broad coverage target >=55/61 (prefer >=59); deepOk=3/3 when at least 3 executable/deep-available candidates exist; no final Top3 slot wasted on replaceable EXCHANGE_DEEP_UNAVAILABLE candidate.
- Forex broad=28/28, deep=3/3, no unexplained errors (subject to Twelve Data quota; quota wait must be reported honestly rather than treated as strategy failure).
- Metal broad=2/2, deep=2/2, no unexplained errors.
- Books contain no legacy incomplete executable entries; WATCH is fine when gates are not ready.
- /hub returns coherent adaptive ranking and does not fabricate MARKET/LIMIT trades.
- Telegram menu/send path works and shows current canonical behavior/version.
- GitHub syntax validation and Wrangler dry-run pass.
- Any live verification script must mark FAIL when deep/execution requirements fail; never weaken validators just to get PASS.

## CONTINUATION PROTOCOL FOR A NEW CHAT
1. Read this file.
2. Fetch cloudflare-worker/index.js and determine the ACTUAL current CONFIG.version; newer repository state overrides the version written here.
3. Inspect the newest *_DIAGNOSTIC.txt, *_LIVE_CHECK.txt, *_MARKETS_CHECK.txt and relevant workflows/commits. Do not assume V77.9.4 is still latest.
4. Reproduce/verify the latest failing condition before editing unless a newer diagnostic already proves it.
5. Make minimal, architecture-preserving fixes; leave a diagnostic/checkpoint trail in the repo for every meaningful migration.
6. Run syntax/validation, then production live verification. Do not stop at local syntax PASS.
7. Update THIS handoff file after a major architecture change or when the blocker/success state changes, so future chats always have a durable source of truth.
8. If verification fails, continue from the exact failure; do not roll back to obsolete V77.7/V77.8 logic and do not reintroduce legacy fixed scores/TP?.

## SAFETY / TRUTHFULNESS RULE
A scanner result is analysis, not guaranteed profit. Never label data as realtime/live unless its provider timestamp/freshness supports that claim. Never infer an executable trade from broad discovery alone.
