# TRADING CHAT HANDOFF — DURABLE CHECKPOINT

Last updated: 2026-08-18
Repository: hanlinh227-ship-it/trading-api
Production Worker: https://trading-v77-scanner.hanlinh227.workers.dev
Current verified production generation: V77.10.2 (always re-read index.js; newer state overrides this line)

## PURPOSE
This file is the canonical handoff/checkpoint for continuing the Trading project in a new ChatGPT conversation. A new chat must read this file FIRST, then inspect current canonical runtime and newest diagnostic/live-check files. Do not rely on chat memory or an old version number in the prompt.

## USER INTENT
Build and continuously harden an adaptive trading scanner/Hub for Forex, Crypto and Metals. Every supported symbol should be analyzable with a method/profile appropriate to that symbol, while all results normalize to one comparable Hub score/readiness model. Do not force every symbol through one identical entry recipe. Do not make rules so rigid that reasonable continuation/relative/momentum opportunities are discarded, but NEVER turn this into forced trading: WATCH and an indicative entry plan are acceptable when execution/news/trigger is not ready. TP/SL should follow market structure, liquidity/support-resistance and invalidation, not a fixed arbitrary RR. Real-time/fresh data must be preferred; never pretend stale data is live. Preserve exact-symbol integrity. Keep improving/testing autonomously when asked, but report truthfully and never call a failing verification PASS.

## CANONICAL RUNTIME
Primary runtime: cloudflare-worker/index.js
V73 reference/config: data/nocut_intraday_allpass_v73.json
Validation workflow: .github/workflows/validate-cloudflare-v77.yml
Current key diagnostics: V77102_DIAGNOSTIC.txt, V77102_FAST_LIVE.txt, V77102_MARKETS_LIVE.txt
Live verification workflows/check files may evolve; inspect repository rather than assuming filenames.

## ARCHITECTURE THAT MUST BE PRESERVED
- V73 remains a frozen prior/reference, not a standalone BUY/SELL engine.
- Adaptive setup scoring via methodAssessment/setupScore; Hub score means setup readiness/quality, NOT win probability.
- Each symbol can have a distinct family/profile. Current runtime normalizes families into adaptive modes such as TREND, RELATIVE, MEAN_REVERSION and GENERIC.
- Entry policy is profile-aware:
  - MEAN_REVERSION remains strict and prefers sweep/reclaim/reversal evidence.
  - TREND/MOMENTUM may use high-quality continuation zones and M5 momentum continuation instead of requiring the same sweep/retest recipe every time.
  - RELATIVE/HYBRID may combine strong relative context + HTF direction + M15/M5 continuation/break evidence.
  - GENERIC can use softer continuation only at higher quality thresholds.
- A soft/adaptive trigger does NOT bypass execution/news/freshness requirements.
- Structure/liquidity-based SL/TP and invalidation remain mandatory for an executable plan. TP1/TP2 come from usable liquidity/structure targets where possible; RR is an outcome of the structure, not a fixed command.
- Indicative plans are explicitly marked `indicative` / `Entry tham khảo` and are NOT executable orders.
- Forex: 28-pair universe, Twelve Data batch analysis; broker/execution quote still required before executable MARKET/LIMIT.
- Metals: XAUUSD/XAGUSD, Twelve Data analysis; broker/execution quote required before executable MARKET/LIMIT.
- Crypto: 61-symbol universe. Broad discovery can use Bybit/OKX/Binance bulk plus KuCoin/Gate broad feeds and short-lived KV cache. Broad data NEVER authorizes an executable trade.
- Crypto deep analysis is resilient:
  - canonical execution/deep venues remain Bybit/OKX/Binance;
  - KuCoin/Gate can supply ANALYSIS-ONLY 5TF fallback when canonical venues are unavailable/rate-limited;
  - an analysis-only quote/candle bundle can produce WATCH/indicative plan, but before MARKET/LIMIT the engine MUST replace it with a fresh exact canonical execution quote and require `executionVerified` bid/ask.
- Crypto candidate routing uses a larger ranked shortlist and skips/replaces deep-unavailable candidates rather than wasting one of the final Top3 slots.
- Direct per-symbol analysis exists at `/analyze?symbol=...`; Telegram supports `/coin BTC` and `/analyze KAITOUSDT` style commands.
- Strict news/context gate remains required where configured.
- Books must not leak legacy incomplete MARKET/LIMIT entries (e.g. `TP ?` or old fixed scores).
- Preserve KV/state safeguards, run lock, Twelve Data rate-budget logic, quote freshness and truthful diagnostics.

## VERSION HISTORY / IMPORTANT FIXES
- V77.9 migration fixed generator marker duplication and nested-backtick migration failures.
- V77.9.4 achieved Crypto broad coverage 59/61 but failed deep 0/3 because top broad candidates could be unavailable on canonical deep venues.
- V77.10.0 introduced Adaptive Entry Freedom:
  - profileMode / adaptiveLocationPolicy / adaptiveTriggerPolicy;
  - larger Crypto deep shortlist, sequential replacement of unavailable candidates;
  - `/analyze?symbol=` direct symbol engine;
  - indicative structural entry plans.
  Live V77.10.0: Crypto 59/61, deep 3/3; Forex 28/28 deep 3/3; Metal 2/2; candidate replacement worked.
- V77.10.1 polished Hub/Telegram:
  - `/coin BTC` and `/analyze SYMBOL` commands;
  - explicit `Entry tham khảo` versus executable order presentation;
  - accurate `deepRequested` for smaller universes;
  - manual news recheck routed through the adaptive engine.
  A heavy Crypto scan followed immediately by direct BTC analysis exposed canonical venue rate-limit coupling.
- V77.10.2 decoupled analysis from execution authority:
  - KuCoin/Gate analysis-only 5TF fallback added;
  - `reference.analysisOnly` can NEVER authorize execution;
  - final Crypto MARKET/LIMIT still requires fresh Bybit/OKX/Binance bid/ask and full gates.

## CURRENT VERIFIED PRODUCTION STATE — V77.10.2
Syntax/migration diagnostic PASS (`V77102_DIAGNOSTIC.txt`): generator=0, migration=0, Worker syntax=0; KuCoin/Gate fallback and analysisOnly execution guard present.

Fast Crypto live verification PASS (`V77102_FAST_LIVE.txt`):
- VERSION=V77.10.2, status OK.
- Crypto broad=59/61, deep=3/3.
- Deep attempted=5, skipped=0.
- KAITOUSDT WATCH 64, analysis source Gate Spot Analysis, planned=1.
- FILUSDT WATCH 49, analysis source Gate Spot Analysis.
- POLUSDT WATCH 44, analysis source Gate Spot Analysis, planned=1.
- BTC direct analyze immediately after Crypto scan: OK, WATCH, score 21, source Gate Spot Analysis; no DATA_BLOCK.
- KAITO direct analyze: OK, WATCH, score 64, planned indicative entry=1; no DATA_BLOCK.

Independent markets/Telegram plumbing verification PASS (`V77102_MARKETS_LIVE.txt`):
- Forex 28/28, deep 3/3, 0 broad errors.
- Metal 2/2, deep 2/2, 0 broad errors.
- Telegram webhook OK; URL points to production Worker; pending_update_count=0.
- Books Forex executable=0/0/0, Metal executable=0/0/0, Crypto executable=0/0/0 at that snapshot; WATCH books populated. This is correct because no setup had all execution/news gates cleared.

## INTERPRETATION / POLICY
The desired behavior is NOT “always produce a MARKET/LIMIT trade.” The desired behavior is:
1. Every supported symbol should get the best reasonable directional/context assessment that available fresh data permits.
2. If structure supports a sensible future entry, provide an INDICATIVE entry/SL/TP plan even while waiting for location/trigger/news/execution.
3. Use the symbol’s profile to decide what constitutes a reasonable entry trigger; do not force all assets through identical M15/M5 conditions.
4. Only promote to MARKET/LIMIT when the executable gate is genuinely satisfied.
This keeps the system flexible without making it reckless.

## NEXT ENGINEERING TARGETS
Do not regress the current PASS state. Possible improvements should be measured against it:
1. Improve per-symbol profile richness inside V73-derived intelligence (e.g. more explicit momentum vs breakout vs pullback vs mean-reversion behavior), but do not rewrite V73 blindly.
2. Improve broad ranking so candidates are selected by quality + context, not merely raw 24h movement.
3. Add correlation/exposure control to Hub so Top3 is not three versions of the same USD/BTC macro bet.
4. Add stronger Gold macro context (DXY/rates/news) only when a trustworthy canonical feed is available; never fabricate it.
5. Improve Telegram presentation, especially direct-symbol analysis and Hub stage labels, without leaking debug spam.
6. Continue testing cold-start, post-scan direct symbol analysis and provider rate-limit scenarios.
7. The 2/61 Crypto symbols missing from broad coverage should be treated honestly as provider coverage gaps; do not alias them to a different token. If a new exact/broad source is added, validate exact identity before counting coverage.

## SUCCESS CRITERIA BEFORE PROMOTING A FUTURE VERSION
- `/status` current version, ok=true, KV/Twelve Data/Telegram healthy.
- Crypto requested=61; broad target >=55/61 (prefer >=59); deep 3/3 when at least three analyzable candidates exist; replace unavailable candidates rather than returning a replaceable DATA_BLOCK in final Top3.
- A heavy Crypto scan followed by direct `/analyze?symbol=BTCUSDT` should still return a valid analysis (WATCH is fine), not a rate-limit DATA_BLOCK when analysis fallback is available.
- Any indicative entry must be labelled non-executable.
- Executable Crypto trade requires fresh exact canonical bid/ask + executionVerified + structural plan + news/context gate.
- Forex 28/28 deep 3/3 subject to honest Twelve Data quota handling.
- Metal 2/2 deep 2/2.
- Books contain no legacy incomplete executable entries.
- Telegram webhook/menu path works; pending updates should not accumulate abnormally.
- GitHub syntax validation and Wrangler dry-run pass.
- Never weaken a validator merely to make a build PASS.

## CONTINUATION PROTOCOL FOR A NEW CHAT
1. Read this file FIRST.
2. Fetch `cloudflare-worker/index.js` and determine ACTUAL `CONFIG.version`; newer repository state overrides every version written here.
3. Inspect newest `*_DIAGNOSTIC.txt`, `*_LIVE*.txt`, `*_MARKETS*.txt`, validation workflows and recent commits.
4. Reproduce/verify the newest failure before editing unless a newer diagnostic already proves it.
5. Make architecture-preserving fixes. Do not roll back to V77.7/V77.8/V77.9 legacy behavior and do not restore fixed score UI or `TP ?`.
6. Run generator/syntax/validator/Wrangler checks, then production live verification. Local syntax PASS alone is insufficient.
7. Leave diagnostic/live-check traces in GitHub for meaningful migrations.
8. Update THIS handoff file after a major architecture or verified-state change.

## SAFETY / TRUTHFULNESS RULE
A scanner result is analysis, not guaranteed profit. Never label data as realtime/live unless provider timestamp/freshness supports that claim. Never infer an executable trade from broad discovery or analysis-only fallback. Flexible entry logic must never become forced trading.
