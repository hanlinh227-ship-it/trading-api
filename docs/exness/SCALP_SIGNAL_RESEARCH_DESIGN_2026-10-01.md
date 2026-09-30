# Exness scalp signal research — candidate design

Status: DESIGN CANDIDATE. No live signal authority, no order route, no paid API call, no production deployment.
Owner: trading-api Exness read-only research surface. Runtime boundary: `cloudflare-worker/exness-*`; Bybit execution and Model Mesh authority remain unchanged.

## Purpose and constraints

- One private mobile viewer scans the 28 FX crosses made from USD, JPY, EUR, GBP, CHF, AUD, CAD and NZD.
- The Exness signed ticks WebSocket supplies Bid/Ask to a market-data Durable Object. Reception and display must never wait for AI. The browser disconnecting does not imply a guaranteed persistent upstream: durable lifetime and quota need a separate measured design before promising 24/7 collection.
- Two explicit actions: `Signal` evaluates the current snapshot and asks DeepSeek for a bounded research review; `Đánh giá` refreshes prices/candles and asks DeepSeek to challenge the saved candidate set. No periodic AI calls.
- Never pass Exness keys, account data, browser IP, Cloudflare secrets, or raw upstream frames to DeepSeek. No trading endpoint, order mutation, automatic order proposal, or automatic method promotion.
- Existing project policy `FREE_ONLY` and retired Forex method authority conflict with paid DeepSeek-backed live signals. Candidate remains gated until a separate approved policy/expense decision and a method validation release. The user's request for DeepSeek API is an intent to use that provider, not evidence that an account has available balance or that Worker secrets are bound.

## Proposed button flow

1. Private authenticated browser asks the Exness-specific research endpoint for a scan. The existing public `/exness/live` cannot safely expose a billable AI call. Use a separate access gate whose credential is never sent to DeepSeek, plus CSRF/origin and per-user request controls.
2. The DO returns one sanitized snapshot per pair: symbol, bid, ask, source time, receive time and freshness. Collect broker-matched CLOSED M1, M5 and H1 candles, preferably cached incrementally and with dynamic API limits. Never fetch 84 candle requests synchronously inside one Worker Free invocation. Fail closed when insufficient candles, quote freshness, spread history, limits or news-risk evidence are unavailable.
3. One deterministic method `FX_CONTEXT_STRUCTURE_TRIGGER_V1` produces evidence and NO_SIGNAL reasons. It has versioned input adapters and feature definitions, not a vote among separate strategies. Initially it is a research hypothesis, not a promoted method.
4. Rank valid candidates only, deduplicate correlated crosses/direction, pass at most a few concise candidates to DeepSeek model `deepseek-flash` (currently served by V4.1 Flash; verify at deployment). Request JSON with 0–2 reviewed candidates and evidence references. Validate JSON schema and match every symbol, direction, number and timestamp to the original snapshot. DeepSeek can veto or explain; it cannot invent a quote, set a price, restore a rejected setup, or revise strategy code.
5. Persist a bounded audit record with snapshot hash, source times, single method version and active feature versions, model name, cost usage, rejection reasons and expiry. Do not store raw secrets, hidden chain of thought, or sensitive account fields.
6. On `Đánh giá`, re-read market data and reject expired candidates before a NEW DeepSeek request. Show keep/reject/wait, invalidation and exact evidence; no stale candidate can silently remain actionable.

## One method: FX Context → Structure → Trigger → Cost

One method receives immutable, normalized FX observations and returns `{methodId, version, instrument, direction, evidence, closedCandleTimes, invalidation, reason}` or a typed rejection. It has **one decision path**:

1. **Currency context:** derive each currency's empirical behavior from the same Exness 28-pair universe: rolling volatility, spread by session, quote cadence, cross-pair strength and pair correlation. Normalize pair inversion/sign and avoid counting triangularly dependent crosses as independent votes. Update profiles from historical windows with versioned samples; never hard-code stereotypes such as “JPY always does X”. Match macro-event evidence from verifiable dated first-party central bank/public calendar sources, where available; otherwise `EVENT_RISK_UNKNOWN` and no event-dependent claim. No live web search on every button press.
2. **H1 regime/structure:** classify trend, range or indeterminate from completed bars and explicit swing definitions. Regime changes the *interpretation* of the same method; it is not an additional trading authority.
3. **M5 location:** require a relevant pullback, range edge or failed break at a measurable level, with closed-candle evidence. “Liquidity sweep”, FVG and indicator labels can describe an observation but never prove an entry on their own. Old V76 patterns are counterexamples and candidate features for testing, not preapproved setups.
4. **M1 trigger:** require a completed bar, directionally consistent break/reclaim/retest and current broker Bid/Ask. A currently forming bar stays `WAIT`. If M1 cannot be obtained and validated, no scalp candidate.
5. **Cost and invalidation:** use current spread and broker conditions to check plausible room after spread/slippage; structural invalidation and research risk/reward use the observed quote semantics. With unknown costs, session/event gap, stale tick or unsupported symbol, return `NO_SIGNAL`. Rank at most two independently useful candidates, accounting for shared-currency exposure; zero is acceptable.

This is one method with regime-aware logic and modular *evidence adapters*. It must be tested with market costs, news periods, correlated positions, look-ahead bias, out-of-sample stability and false alerts. Existing V76 R2 had 0/28 Forex methods promoted, so none is inherited as live signal authority.

The single-method registry holds feature/adaptor metadata, tests and immutable versions. A proposed input source or feature is added in a separate pull request with fixtures and out-of-sample evidence; it does not create another primary method. There is no runtime self-modifying code or model-written prompt/rule promotion. The learning loop logs outcomes in paper research, aggregates false-positive and failure-mode metrics, tests new versions on untouched periods and requires human-reviewed release gates. A model's self-assessment is not performance evidence.

## Existing GPT and GitHub skill coverage

- GPT `trading-research` is the research and backtest discipline; `market-candle-reader` verifies OHLC and candle-close status; `market-candle-analysis` supplies bounded price-action context. These are *design/reference skills* in this ChatGPT session, not files automatically available to Cloudflare or imported executable functions.
- GitHub `AI_SKILL_LIBRARY/skills/trading/market_analysis.md`, `quant_backtesting.md`, `risk_execution.md`, and `multi_market_analysis.md` provide source/freshness, costs, out-of-sample and evidence-normalization rules. Reuse their concepts through a small, explicit contract; do not create another router or automatically invoke the whole Brain on each tick.
- GPT `volume-profile-footprint` is excluded for the current Exness tick/candle feed: neither executed bid/ask volume by price nor consolidated FX order flow was verified. Do not fabricate delta/POC/footprint evidence.
- Optional `research-search` can source dated first-party economic releases ahead of time. Keep source URL, event timestamp, currency scope, observation time, entitlement and expiry. News text is untrusted and cannot change method rules.

## Evidence from both GitHub accounts (2026-10-01 review)

| Account / source | Role in this feature | Admission |
| --- | --- | --- |
| `appvn553-byte/linhai-system-core` `README.md`, `catalog/repositories.json` | Catalog and recovery governance; it says the repo does not contain running Brain V2 or Control source. | Reference for ownership only. It provides no verified Forex method or production trading runtime. |
| `appvn553-byte/linhai-memory-continuity` | Documentation-only continuity archive per the core catalog. | Reference only; no executable strategy imports. |
| `hanlinh227-ship-it/trading-api` `data/v76_entry_summary.json`, `data/v76_entry_methods.json`, `data/v76_pair_table.md` | 28-pair experiment provenance, per-pair development/validation/out-of-sample metrics and rejected method IDs. | Historical research. `promotedSymbols=[]`, `retainedArchetypes=[]`. Never turn a past top-ranked pair into a live signal by copying the table. |
| `hanlinh227-ship-it/trading-api` `AI_SKILL_LIBRARY/skills/trading/trading_router.md` and `docs/checkpoints/CURRENT_HANDOFF.md` | Evidence hierarchy, routing and active Bybit authority. | Trading research guidance only; do not alter Bybit production execution or revive retired Forex authority. |

Use this source manifest as *input metadata* for features within the one method: `{repo, path, revisionSha, featureId, dataPeriod, venue, timeframe, fees, validationMetrics, authority:'RESEARCH_ONLY'}`. The AI request contains short, relevant evidence IDs and measured current-market data, not whole repositories or an unbounded search at each button press. A source from either GitHub account can become a feature candidate after deduplication, data/venue matching, license/provenance check and repeatable validation. Neither email account acts as an extra execution authority.

## DeepSeek configuration and security

- Preserve existing primary secret name `DEEPSEEK_API_KEY`; optional `DEEPSEEK_API_KEY_BACKUP` is a *Worker runtime secret*, not a browser/GitHub-only value.
- Both keys share ONE per-user/per-day call budget and spending stop. No failover on HTTP 429, quota exhaustion, insufficient balance, or a budget stop. Backup is for invalid/revoked primary or transport failure only if provider terms and account quotas permit. Never rotate keys to bypass rate limits.
- Explicit activation flag default OFF; require verified authenticated surface, configured spend limit, tested mock upstream and credential binding. API keys can be injected from Cloudflare secrets without printing their values. Redact provider errors and truncate response bodies before logs.
- Bound input bytes, output tokens, concurrent requests and timeout. Set `response_format: {type:'json_object'}` and validate the returned content; JSON mode alone does not enforce correctness. Provider text is untrusted data.
- The live prices WebSocket continues independently when DeepSeek is slow or unavailable. Each button returns an explicit `AI_UNAVAILABLE`/`NO_SIGNAL`, never a guessed result.

## Mobile interface

Connection and History controls on the left; large Signal and Đánh giá controls in the center. Signal shows scan progress and up to two *research* cards; zero valid cards is an expected result. Đánh giá is disabled until a valid scan exists and clearly shows the model status, freshness and reason for rejection. History records method version and model usage. Loading, stale, disconnected, quota, budget and provider errors are distinct states. No trade action control.

## Acceptance gates

1. Baseline WS A/B telemetry at least 30 minutes per state for all 28 pairs; demonstrate price flow unaffected by button/AI latency or failure. Report source cadence, age, p50/p95/p99, gaps, disconnects and quotas per pair.
2. Shadow/paper strategy tests with closed candles, market costs, untouched validation periods and reproducible fixtures; 0/28 is a valid outcome.
3. Mock E2E: Signal and Đánh giá each trigger exactly one bounded model request when enabled and budgeted; no provider call on stale data, authentication failure, duplicate click or budget exhaustion; no 429 key rotation; model hallucination rejected.
4. Run exact-main CI/deploy gates and verify Bybit regression plus Exness read-only routes before any production deployment. Confirm actual Worker secret names by presence only, not secret values.

Primary references: Exness ticks `https://www.exness-api.com/reference/get-ws-ticks`; limits `https://www.exness-api.com/documentation/api-configuration-and-limits`; DeepSeek pricing `https://api-docs.deepseek.com/quick_start/pricing/`; JSON output `https://api-docs.deepseek.com/guides/json_mode/`; Cloudflare Worker limits `https://developers.cloudflare.com/workers/platform/limits/`.
