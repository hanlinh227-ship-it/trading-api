# Exness scalp signal research — candidate design

Status: DESIGN CANDIDATE. No live signal authority, no order route, no paid API call, no production deployment.
Owner: trading-api Exness read-only research surface. Runtime boundary: `cloudflare-worker/exness-*`; Bybit execution and Model Mesh authority remain unchanged.

## Purpose and constraints

- One private mobile viewer scans the 28 FX crosses made from USD, JPY, EUR, GBP, CHF, AUD, CAD and NZD.
- Target bot monitoring is 24/7 and must not depend on an open browser. The current Exness stream path is viewer-connected and the repo had an 8 h/day stream cap; changing that cap or claiming background continuity requires a quota-safe server-side collector design and soak evidence. The Cloudflare Free budget is shared with the existing Bybit Worker.
- The bot's market cycle continuously records fresh ticks, validates signal levels and updates paper outcomes without AI API calls. DeepSeek API is called only after the user presses `Signal` or `Đánh giá`; never once per tick or on a timer.
- Never pass Exness keys, account data, browser IP, Cloudflare secrets, or raw upstream frames to DeepSeek. No trading endpoint, order mutation, automatic order proposal, or automatic method promotion.
- Existing project policy `FREE_ONLY` and retired Forex method authority conflict with paid DeepSeek-backed live signals. Candidate remains gated until a separate approved policy/expense decision and a method validation release. The user's request for DeepSeek API is an intent to use that provider, not evidence that an account has available balance or that Worker secrets are bound.

### Owner clarification: signal-only automatic tracking

Correction: the user only consumes signals; the bot and AI record signal creation, evidence, assessments and outcomes automatically. No user entry/exit form or manual fill confirmation is required. Each generated signal is automatically added to an internal **paper/shadow tracker** using the Exness quote feed. History win/loss and TP/SL rates describe only simulated outcomes for generated signals, calculated from observed Exness quotes.

On `Signal`, the bot scans and preflights candidates, then DeepSeek reviews only the bounded candidate/context package; validated signals initialize paper entry at BUY Ask or SELL Bid. The bot tracks BUY at Bid and SELL at Ask and records every state transition. On `Đánh giá`, DeepSeek can re-review active signals and their accumulated cycle history. Price cycles continue independently; they never call the AI API.

## Proposed button flow

1. Private authenticated browser asks the Exness-specific research endpoint for a scan. The existing public `/exness/live` cannot safely expose a billable AI call. Use a separate access gate whose credential is never sent to DeepSeek, plus CSRF/origin and per-user request controls.
2. The DO returns one sanitized snapshot per pair: symbol, bid, ask, source time, receive time and freshness. Collect broker-matched CLOSED M1, M5 and H1 candles, preferably cached incrementally and with dynamic API limits. Never fetch 84 candle requests synchronously inside one Worker Free invocation. Fail closed when insufficient candles, quote freshness, spread history, limits or news-risk evidence are unavailable.
3. One deterministic method `FX_CONTEXT_STRUCTURE_TRIGGER_V1` produces evidence and NO_SIGNAL reasons. It has versioned input adapters and feature definitions, not a vote among separate strategies. Initially it is a research hypothesis, not a promoted method.
4. Rank valid candidates only, deduplicate correlated crosses/direction, pass at most a few concise candidates to DeepSeek model `deepseek-flash` (currently served by V4.1 Flash; verify at deployment). Request JSON with 0–2 reviewed candidates and evidence references. Validate JSON schema and match every symbol, direction, number and timestamp to the original snapshot. DeepSeek can veto or explain; it cannot invent a quote, set a price, restore a rejected setup, or revise strategy code.
5. Persist a bounded audit record with snapshot hash, source times, single method version and active feature versions, model name, cost usage, rejection reasons and expiry. Do not store raw secrets, hidden chain of thought, or sensitive account fields.
6. On `Đánh giá`, re-read market data and reject archived or invalid signal records before a NEW DeepSeek request. Show thesis status, invalidation or data gaps and exact evidence; no stale signal can silently appear current.

## 24/7 signal cycle and research learning

- Target: the bot monitors the 28-pair Exness feed continuously and records cycle snapshots, freshness, signal-state changes, TP/SL observations, reconnect gaps and method outcomes. It keeps the signal web's feed/ledger active when the browser is closed.
- AI API boundary: only explicit presses of `Signal` and `Đánh giá` call DeepSeek. The bot's automatic per-tick/per-cycle evaluator is deterministic and bounded; it refreshes market features and checks active signals without any model request.
- Learning loop: retain versioned paper outcomes and failure cases. When `Đánh giá` is pressed, provide DeepSeek a bounded, relevant summary of accumulated cycles and ask it to critique current signals and suggest research hypotheses. Suggestions are logged as candidates; they cannot edit live rules, prompts, TP/SL settings, or promote themselves. Compare candidate changes against untouched out-of-sample data before a human-reviewed release.
- Runtime gate: Cloudflare HTTP Workers can remain active while a client keeps a request/stream connected, but waitUntil only extends work briefly after disconnection; Cron/Alarm invocations have bounded runtimes. The present browser-connected socket does not prove a continuous server-side collector after tab close. Free-tier requests/CPU are shared with the Bybit Worker and the current 8 h/day stream cap. Until a server-side collector is implemented and a 24-hour soak plus shared-quota budget passes, display `THEO DÕI NỀN CHƯA ĐƯỢC XÁC MINH`; do not claim 24/7 operation.
- Do not create one scheduled DeepSeek call per cycle. If bot state reaches a reserved shared-quota or source limit, stop/degrade Exness collection in a visible way rather than consume the Bybit reserve or silently claim full coverage. A real 24/7 guarantee may require a different service/budget than current Free-only assumptions.

## One method: FX Context → Structure → Trigger → Cost

One method receives immutable, normalized FX observations and returns `{methodId, version, instrument, direction, evidence, closedCandleTimes, invalidation, reason}` or a typed rejection. It has **one decision path**:

1. **Currency context:** derive each currency's empirical behavior from the same Exness 28-pair universe: rolling volatility, spread by session, quote cadence, cross-pair strength and pair correlation. Normalize pair inversion/sign and avoid counting triangularly dependent crosses as independent votes. Update profiles from historical windows with versioned samples; never hard-code stereotypes such as “JPY always does X”. Match macro-event evidence from verifiable dated first-party central bank/public calendar sources, where available; otherwise `EVENT_RISK_UNKNOWN` and no event-dependent claim. No live web search on every button press.
2. **H1 regime/structure:** classify trend, range or indeterminate from completed bars and explicit swing definitions. Regime changes the *interpretation* of the same method; it is not an additional trading authority.
3. **M5 location:** require a relevant pullback, range edge or failed break at a measurable level, with closed-candle evidence. “Liquidity sweep”, FVG and indicator labels can describe an observation but never prove an entry on their own. Old V76 patterns are counterexamples and candidate features for testing, not preapproved setups.
4. **M1 trigger:** require a completed bar, directionally consistent break/reclaim/retest and current broker Bid/Ask. A currently forming bar stays `WAIT`. If M1 cannot be obtained and validated, no scalp candidate.
5. **Cost and invalidation:** use current spread and broker conditions to check plausible room after spread/slippage; structural invalidation and research risk/reward use the observed quote semantics. With unknown costs, session/event gap, stale tick or unsupported symbol, return `NO_SIGNAL`. Rank at most two independently useful candidates, accounting for shared-currency exposure; zero is acceptable.

This is one method with regime-aware logic and modular *evidence adapters*. It must be tested with market costs, news periods, correlated positions, look-ahead bias, out-of-sample stability and false alerts. Existing V76 R2 had 0/28 Forex methods promoted, so none is inherited as live signal authority.

### Single TP/SL placement for scalp signals

Each signal has exactly one fixed SL and one fixed TP; neither trails the current quote. Set SL beyond the method's structural invalidation point with a buffer derived from the pair/session's observed short-term volatility and spread/noise. Place the single TP at the nearest realistic opposing structure/liquidity objective, after spread/cost checks. Reject the candidate if the stop is inside ordinary observed noise, the target is blocked by structure, or net reward/risk fails the versioned validation threshold. Do not hard-code one pip distance for all 28 pairs. This can reduce avoidable stop-outs but cannot guarantee a stop will not be swept. Buffer and target rules remain research candidates until tested out-of-sample per pair/session.

## Economic and political evidence for the same method

Research may look across relevant financial information, including monetary-policy statements, scheduled economic releases, fiscal announcements, elections, sanctions and geopolitical disruptions. It is impossible to guarantee complete coverage of every event in real time. A bounded source registry, explicit coverage status and timestamps are required before any news-dependent signal is shown.

1. Maintain a currency-to-source registry: USD (Fed, BLS, BEA and Treasury), EUR (ECB and Eurostat), GBP (BoE and ONS), JPY (BoJ and official statistics), CHF (SNB and official statistics), AUD (RBA and ABS), CAD (BoC and Statistics Canada), NZD (RBNZ and Stats NZ). Verify each source's publication, usage terms and retrieval mechanism before integrating it. Start with official calendars/releases, such as Fed FOMC, BLS Employment Situation, ONS and BoJ schedules. For unplanned political events, official government/central-bank releases have priority; reputable reporting may flag a developing event, but independent corroboration is needed before treating its claims as established.
2. In a separate, rate-limited refresh task, collect scheduled events ahead of time and poll permitted sources at appropriate intervals; deduplicate updates and cache only a bounded window. Do not perform an unbounded internet search, scraping or a per-tick news fetch on every button press. If a source is unavailable, mark its coverage `UNKNOWN` and show this limitation; a cached headline must not masquerade as live news.
3. Normalize each item as `{evidenceId, source, url, sourceType, publishedAt, scheduledAt, observedAt, revisedAt, expiryAt, currencies, claim, verificationStatus, impactHypothesis}` with UTC times and immutable original/revision references. Distinguish event time, source publication time and system observation time. Map both currencies in each pair and shared-currency exposure across the 28 crosses; geopolitical effects beyond the named country require a separately evidenced hypothesis.
4. Feed concise, attributed event facts into `FX_CONTEXT_STRUCTURE_TRIGGER_V1`. Scheduled high-impact windows, verified surprise releases and credible disruptive events can impose `WAIT`, tighten freshness requirements or reduce research confidence according to tested rules. Unverified/conflicting reports become `UNVERIFIED_EVENT`; missing coverage becomes `EVENT_RISK_UNKNOWN`. Neither a headline nor AI sentiment by itself yields BUY/SELL. Price structure, closed candles, current Bid/Ask and transaction costs still need independent validation.
5. Pass only a bounded set of relevant evidence IDs, dates and short source-grounded summaries to DeepSeek for factual challenge and explanation. Treat retrieved text and model output as untrusted data: ignore instructions embedded in pages, reject invented event details or unsupported currency links, and never allow them to change method thresholds, credentials or call budget. In the UI, show source, publication/observation time, affected currencies and verification status alongside each relevant caution.
6. For historical evaluation, replay only information demonstrably available as of the decision time, including revisions and observed-at delays. Compare news-aware versus price-only false alerts and missed opportunities across out-of-sample event windows. Promote no new risk gate or directional feature without measured benefit and human review.

Example first-party calendars: Fed `https://www.federalreserve.gov/monetarypolicy/fomccalendars.htm`; BLS `https://www.bls.gov/schedule/news_release/empsit.htm`; ONS `https://www.ons.gov.uk/releasecalendar`; BoJ `https://www.boj.or.jp/en/about/calendar/`. These verify source availability, not a guaranteed free machine-readable live-news feed. Provider access and licensing for each automated adapter must be checked separately.

The single-method registry holds feature/adaptor metadata, tests and immutable versions. A proposed input source or feature is added in a separate pull request with fixtures and out-of-sample evidence; it does not create another primary method. There is no runtime self-modifying code or model-written prompt/rule promotion. The learning loop logs outcomes in paper research, aggregates false-positive and failure-mode metrics, tests new versions on untouched periods and requires human-reviewed release gates. A model's self-assessment is not performance evidence.

## Existing GPT and GitHub skill coverage

- GPT `trading-research` is the research and backtest discipline; `market-candle-reader` verifies OHLC and candle-close status; `market-candle-analysis` supplies bounded price-action context. These are *design/reference skills* in this ChatGPT session, not files automatically available to Cloudflare or imported executable functions.
- GitHub `AI_SKILL_LIBRARY/skills/trading/market_analysis.md`, `quant_backtesting.md`, `risk_execution.md`, and `multi_market_analysis.md` provide source/freshness, costs, out-of-sample and evidence-normalization rules. Reuse their concepts through a small, explicit contract; do not create another router or automatically invoke the whole Brain on each tick.
- GPT `volume-profile-footprint` is excluded for the current Exness tick/candle feed: neither executed bid/ask volume by price nor consolidated FX order flow was verified. Do not fabricate delta/POC/footprint evidence.
- Optional `research-search` can source dated first-party economic releases ahead of time. Keep source URL, event timestamp, currency scope, observation time, entitlement and expiry. News text is untrusted and cannot change method rules.

## Knowledge harmonization for skills and prior analysis repositories

Every relevant previously used analysis skill/repository is admitted through a source manifest before it can influence the one FX method. This fulfills reuse without blindly mixing incompatible rules or sending entire repositories to DeepSeek.

- Keep one row per source with `sourceId`, canonical name, repository/path or skill ID, exact revision/version, timeframe/venue coverage, data period, license/provenance, intended role, evidence accepted, conflicts, and status: `INCLUDED`, `REFERENCE_ONLY`, `EXCLUDED`, or `PENDING_REVIEW`.
- Deduplicate equivalent concepts across GPT skills, GitHub analysis files, and prior work. A repeated rule is one feature with multiple provenance links, not multiple votes.
- Map relevant capabilities into the method: `trading-research` for research/backtest discipline; `market-candle-reader` to verify OHLC integrity and candle closure; `market-candle-analysis` for bounded structure context; `research-search` for dated first-party event evidence; GitHub `market_analysis.md`, `quant_backtesting.md`, `risk_execution.md`, and `multi_market_analysis.md` for source quality, costs, out-of-sample and evidence normalization. Their concepts must be translated into reviewed, testable rules; ChatGPT session skills are not automatically installed in the Worker.
- Preserve conflicts instead of averaging them. Current project authority, exact live data and tested method contract outrank historical or imported advice. Forex methods remain research-only until a new untouched out-of-sample validation and release gate passes; no prior skill or repo can promote itself.
- The prompt builder sends a bounded, versioned context packet: applicable method contract; currency profiles for the eight currencies; pair-specific spread/cadence/correlation; closed H1/M5/M1 evidence; current Bid/Ask freshness; relevant verified event evidence; and references to the exact source rows. Include only applicable skill/repo evidence IDs plus concise validated rule summaries. Do not send API keys, account data, whole repos, unrelated chat history, or hidden chain-of-thought.
- Store the packet version/hash and source IDs with each scan/review so History can show which method and knowledge release informed the result. A source update creates a candidate release and must pass deduplication, conflict, provenance/license and repeatable validation before use.

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

## Optional GPT Plus usage fallback (eligibility gated)

The user wants an explicit `Dùng GPT Plus` action when DeepSeek is unavailable or its quota is exhausted. Do not silently switch providers. This is possible only through an approved Sign in with ChatGPT plan-usage integration; ChatGPT Plus does not give this app a conventional API key or access to the user's ChatGPT chats.

- Eligibility blocker: the current product is a private, remotely hosted Cloudflare Worker app. OpenAI's current Sign in with ChatGPT documentation describes plan usage for open-source/locally hosted apps and says a remotely hosted app needs the commercial-partner interest/approval path. Do not expose a live GPT fallback until the app is accepted and receives supported client registration. Approval is not established by this design.
- After eligibility, require the user to select `Kết nối ChatGPT Plus`, sign in via OpenAI OAuth, grant plan usage, and explicitly turn on the fallback. Never ask for or store a ChatGPT password or reuse browser cookies. Store only necessary OAuth credentials encrypted; support revocation and refresh.
- Show `Dùng GPT Plus` only after connection and consent. On click, send the same validated, sanitized market snapshot and method evidence used for the DeepSeek review to the public Responses API with the authorized OAuth bearer token. Use an account-available model from `GET /v1/models`; refresh the account-specific model list. Set `store:false` and `stream:true`; include all request context each time and do not use ChatGPT `backend-api` or assume persistent ChatGPT conversation state. Parse output through the same strict schema/evidence validator before updating a signal assessment.
- ChatGPT-plan requests count against the user's included ChatGPT usage and still have plan and per-app limits; they are not unlimited. Add a visible provider/usage label and let the user set the app limit in ChatGPT Settings > Usage. Disable any credit use or paid API fallback; on exhaustion return `GPT_PLAN_LIMIT` and keep existing signal state unchanged. Never switch back to DeepSeek automatically from a GPT response failure.
- On the current ineligible deployment, present `ChatGPT Plus chưa được phép kết nối cho ứng dụng này`; keep the live AI fallback unavailable. A temporary manual handoff may generate/copy a complete prompt, open ChatGPT for the user to submit, then let them paste the structured answer back for validation. This path is not automatic and cannot claim the app sent or received the ChatGPT conversation.
- Regardless of provider, an AI review only classifies thesis conditions and evidence; it does not decide or send a live close/order action.

Official references: OpenAI Help Center `https://help.openai.com/en/articles/20001542-using-your-chatgpt-plan-in-other-apps-and-sites`; developer overview `https://developers.openai.com/siwc/token-sharing-open-source`; model/inference `https://developers.openai.com/siwc/token-sharing-open-source/models-and-inference`; preview limitations `https://developers.openai.com/siwc/token-sharing-open-source/preview-limitations`; remotely hosted partner onboarding `https://developers.openai.com/siwc/request-client-id`.

## Mobile interface

Connection and History controls stay in the left rail/drawer; large `Signal` and `Đánh giá` buttons remain central and thumb-accessible. Signal returns up to two cards with exactly one TP and one SL and automatically starts paper tracking; zero valid candidates is normal. The user does not enter prices or outcomes. The bot records cycles and TP/SL observations; DeepSeek API runs only on button presses. History is labeled as simulated outcomes from the Exness feed. Loading, stale feed, disconnect, 24/7 collector status, model quota and provider errors have distinct states.

### Two active signal slots

There are exactly two active signal slots. A successful `Signal` scan fills only empty slots; with one occupied slot it can add at most one new candidate. It never replaces an existing card. Identical pair/direction/setup snapshots are deduplicated; a later materially changed setup may be recorded under a new ID. When both slots are occupied, `Signal` is disabled; `Đánh giá` remains available.

When an AI light turns red, show two actions on that card: **Giữ** and **Xóa**. `Giữ` retains the signal and its slot, keeps the red reason visible, and allows the user to evaluate it again later. `Xóa` removes it from Active and moves it to History as `USER_ARCHIVED_RED`; it is not physically deleted and remains in research statistics as an invalidated signal, not a TP/SL win/loss. The freed slot can be filled by a later Signal scan. No red signal is auto-archived.

Repeated `Signal` scans and `Đánh giá` calls are allowed within provider/request budgets. Each completed AI review appends a timestamped assessment; it never overwrites prior assessments. Idempotency keys, per-signal review IDs and a final active-slot check prevent duplicate cards or stale responses. Reconnect and page reload restore the same active IDs and slot count.

Acceptance fixtures: 0/2 → scan may add 0–2; 1/2 → at most one; 2/2 → no candle/AI call and direct request returns 409; red + `Giữ` → still occupies slot; red + `Xóa` → archived in History and slot released; repeated scan/review → no duplicate IDs or lost assessment history.

### Automatic signal tracking, AI review and History

A signal becomes a paper-tracked record as soon as the validated scan publishes it; no manual entry or exit forms are shown. Store the signal snapshot, method/knowledge version, candidate direction, executable-side reference entry, fixed SL/TP, and source timestamps. Entry convention: BUY uses Ask at signal time; SELL uses Bid. Mark-to-market and level checks use BUY Bid and SELL Ask.

The bot evaluates each fresh quote against fixed levels and appends idempotent observations. If a tick first reaches/crosses TP or SL, archive as `PAPER_TP_OBSERVED` or `PAPER_SL_OBSERVED`; calculate paper pips/R from the first observed executable closing-side quote, not an assumed exact fill at the level. If reconnect gaps over a level, record the first recovered quote and gap interval; do not invent an intermediate price. The record is a simulated outcome for the generated signal.

The `Đánh giá` action asks AI to review active signals against current price, original entry/SL/TP, method evidence and freshness. AI records `CÒN ĐIỀU KIỆN`, `LUẬN ĐIỂM BỊ VÔ HIỆU`, or `CHƯA ĐỦ DỮ LIỆU` with timestamp, reason and evidence IDs. A red verdict sets `THESIS_INVALIDATED`; show **Giữ** and **Xóa**. Keep retains the slot; Xóa archives the signal to History and frees the slot, without classifying it as a TP/SL loss. Tick updates move the gauge and evaluate fixed paper levels only; they never call AI.

Active paper signals have no clock-based expiry. Their lifecycle ends at an observed TP/SL or a fresh AI invalidation. An assessment expires independently and returns to unknown; it does not erase History. Archived rows retain the full audit trail; corrections create a new event instead of overwriting evidence.

Acceptance: paper entry is created once from the exact signal quote; BUY/SELL uses executable-side conventions; TP/SL and AI invalidation each archive once; stale ticks do not advance outcomes; gaps are labeled; no user input is required; no paper outcome is presented as actual account performance.

### History statistics and outcomes

History begins with totals for **Buy / Sell**, **thắng / thua / hòa**, **TP / SL**, and separate **luận điểm bị vô hiệu / chưa kết thúc** counts. Provide filters for date range, pair, direction and outcome. Each row shows signal direction, pair, paper reference entry, SL/TP, first observed exit quote, outcome, paper pips/R, signal/exit timestamps, data freshness, method and knowledge version.

- Calculate simulated win rate only over completed paper TP/SL outcomes: `TP outcomes / (TP + SL outcomes)`. Show sample size explicitly and report breakeven separately if a tested exit rule supports it. Invalidated, unresolved, stale and rejected signals are separate counts, never silently treated as wins/losses.
- Show Buy and Sell sample counts and paper TP/SL outcomes separately. Quote gaps use the first recovered executable-side quote for paper pips/R and carry a gap flag.
- Label the section `Kết quả mô phỏng theo feed Exness`. Add a persistent note: `Đây là kết quả mô phỏng tín hiệu theo feed giá, không phải hiệu suất giao dịch cá nhân.` Do not imply the statistics predict future results.
- Every total must reconcile to visible filtered records; preserve all event/source timestamps and method/knowledge versions for audit.

Acceptance fixtures cover Buy/Sell TP, Buy/Sell SL, breakeven if supported, AI invalidation, unresolved, stale/gap crossing, and reconnect. Validate the denominator, sample-size display, filters and totals.

### Live signal gauge (automatic paper tracking)

For each active signal, show pair/direction, paper reference entry, fixed SL/TP, current executable-side quote, signed simulated pips/R, and a compact horizontal gauge. A fixed center line is 0; red grows toward SL and green toward TP. Do not add text under the colored bar. The gauge describes progress of the **paper signal tracker** and is not a user's live account P/L. Show a concise `PAPER` label and stream freshness (`LIVE`, `GIÁ CŨ`, `MẤT KẾT NỐI`).

BUY paper reference entry is signal Ask and live mark is Bid; SELL reference entry is signal Bid and live mark is Ask. Signed pips use the matching instrument pip size. Normalize each half independently to its fixed stop/target distance. Invalid or missing entry/SL/TP disables the gauge instead of inventing zero. At TP/SL crossing, archive once and show the first observed executable-side quote plus `MỨC GIÁ ĐƯỢC QUAN SÁT`; a gap can skip the level, so never draw a fabricated path.

Update only from validated ticks in the existing 28-pair browser feed; do not add a WebSocket, poll REST or call AI per tick. Render quote, source timestamp, pips/R and gauge atomically from one tick. On stale/disconnect freeze the marker, dim the gauge and display elapsed time; after reconnect jump to the first newer valid tick and flag the gap. Do not interpolate unseen prices.

Mobile acceptance fixtures validate BUY/SELL spread sides, fixed levels, sign/color transitions, stale freeze, atomic reconnect jump, TP/SL one-time archiving and that no broker P&L is claimed.

### Preflight, continuous monitoring and reconnect reconciliation

**Before publishing a signal**, the server must revalidate the latest Exness quote and source time, allowed instrument, positive/crossed Bid/Ask, spread and session/event gates, closed-candle evidence, and fixed Entry/SL/TP geometry using the correct executable side. BUY reference entry is Ask and its tracked closing quote is Bid; SELL reference entry is Bid and its tracked closing quote is Ask. Reject the candidate with a visible reason if any input is stale, incomplete, unsupported or inconsistent. Persist the exact quote/candle timestamps, checks, levels, method/knowledge version and snapshot hash so History explains why it was emitted.

**While connected**, process each valid in-order tick for active signals against their unchanged SL/TP, update the paper gauge from that same tick, and append idempotent state events. Store last source time, last receive time, last executable quote, connection state, and whether TP/SL has been observed. The monitor is bot-driven; price ticks do not invoke AI.

**On disconnect or stale data**, freeze the last known gauge, show `MẤT KẾT NỐI` / `GIÁ CŨ`, the last-good timestamp and `ĐANG ĐỐI SOÁT`. Do not extrapolate or claim the signal is still safely inside its levels. The signal remains unresolved; no outcome is invented.

**After reconnect**, wait for a valid newer quote for each signal's own pair; fetch bounded missing candle/history data only if supported and within current Exness limits. Immediately show the new quote's present location relative to entry/SL/TP and the unobserved interval. If a continuous, ordered tick history bridges the gap, replay it once in source-time order and reconcile TP/SL deterministically. If the gap cannot be reconstructed from reliable executable-side ticks, label `TP/SL CÓ THỂ ĐÃ BỊ CHẠM TRONG KHOẢNG MẤT KẾT NỐI`; show whether the recovered quote is currently beyond a level, but do not declare which level triggered first, do not count a win/loss, and do not close the paper record as a confirmed TP/SL outcome. If the history shows both levels may have been reached in an ambiguous order, mark `OUTCOME_UNKNOWN_AFTER_GAP` and keep it out of the win-rate denominator. Continue monitoring from the recovered quote only after reconciliation status is visible.

The tracker reconciles **the generated signal only**. All lifecycle and History states refer to the web's paper signal records.

Acceptance fixtures: reject stale preflight; BUY/SELL price-side correctness; valid in-order replay across a short gap; no-history gap freezes outcome; recovered price beyond TP or SL shows current location and possible-crossing warning without fabricated result; both levels touched in ambiguous order stays unknown; duplicate replay is idempotent; monitor resumes only after a new valid quote.

### Per-signal AI assessment lights

At the top-right of each signal card, show ONLY three small circles in green / amber / red order, exactly one illuminated after an assessment; no text beneath or beside the light cluster. Before assessment show three dim outlines. Put readable status, reason and assessment time in a separate row below the gauge; provide the same status to screen readers. Per-card `Đánh giá tín hiệu` reviews one signal; main `Đánh giá` reviews all active signals in one bounded request. No AI call occurs on each tick.

| Light | Meaning |
| --- | --- |
| Green | Fresh evidence still supports the research thesis; not a profit prediction. |
| Amber | Insufficient, uncertain or stale evidence; no direction implied. |
| Red | Fresh evidence invalidates the research thesis; show the reason and the user-controlled **Giữ** / **Xóa** actions. Keep preserves the active slot; Xóa archives it to History and frees the slot. |

Verdicts are bound to signal ID, snapshot hash, method/knowledge version, assessment time, expiry, source timestamp, reason code and evidence IDs. Expired verdicts revert to unknown. The gauge's red/green price progress is separate from AI assessment. Signal cycle/History updates are automatic and idempotent; DeepSeek API is called only when the user presses Signal or Đánh giá, never per tick or timer. A red verdict never auto-removes a card; the user chooses Giữ or Xóa.

## Acceptance gates

1. Verify the background collector can operate independently of the browser without consuming the Bybit reserve; prove with a 24-hour soak, disconnect/reconnect injection, per-pair tick freshness, gaps and shared-account quota dashboard evidence. Until then, 24/7 remains a target, not a verified capability.
2. Baseline WS telemetry for all 28 pairs; report source cadence, age, p50/p95/p99, gaps, disconnects and quota consumption while confirming Bybit regression stays within its reserve.
3. Shadow/paper tests use closed candles, spread/cost model, versioned one-SL/one-TP rules, untouched validation periods and reproducible fixtures; 0/28 remains an acceptable no-signal/no-promotion result.
4. Mock E2E verifies the bot's cycle never calls DeepSeek; only Signal/Đánh giá buttons make bounded model calls. Stale data, full slots, repeated presses, quota/budget exhaustion and provider errors fail closed. Red/Giữ/Xóa and repeated assessments preserve audit/history.
5. Exact-main CI/deploy gate, secrets-presence verification without reading values, and Bybit regression must pass before any production deployment.

Primary references: Exness ticks `https://www.exness-api.com/reference/get-ws-ticks`; limits `https://www.exness-api.com/documentation/api-configuration-and-limits`; DeepSeek pricing `https://api-docs.deepseek.com/quick_start/pricing/`; JSON output `https://api-docs.deepseek.com/guides/json_mode/`; Cloudflare Worker limits `https://developers.cloudflare.com/workers/platform/limits/`.
