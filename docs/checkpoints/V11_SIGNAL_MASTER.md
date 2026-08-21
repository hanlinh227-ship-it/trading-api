# SIGNAL V11 — MASTER CHECKPOINT

STATUS: DESIGN BASELINE
BRANCH: signal-v11
BASE_MAIN_COMMIT: 2a5f02d6e364fb814325525cb9dba2fbd0110ebb
CREATED: 2026-08-21

## 1. Purpose

V11 is the next Signal-only architecture. V10 on main is the rollback/reference baseline. V11 must not silently reactivate V77/V78 decision authority. Legacy engine code may temporarily remain as a data/scanner compatibility layer only until explicitly replaced.

Primary goal: produce a healthy daily flow of high-quality scalp opportunities across Crypto, Forex, Metal and Index without quotas forcing bad trades. Zero signals is allowed when market conditions genuinely fail hard safety gates; V11 optimizes opportunity discovery and market-specific methods rather than weakening data integrity.

## 2. Platform responsibilities

### Cloudflare — runtime/orchestration authority
- Single production scheduler authority.
- Telegram Unified Signal Hub.
- Data cache and deduplication.
- Per-market scan orchestration.
- Candidate queues/state, lifecycle, history, statistics and learning state.
- Provider health, retry/backoff, circuit breakers and quota budgeting.
- AI review gateway when API-accessible providers are available.
- Fail closed on unverifiable price/data.
- Prefer Queues/Workflows/Durable state where available instead of one oversized cron invocation.

### Twelve Data — structured market-data backbone
- Primary structured candles/context for Forex, Metal and Index where entitlement/provider identity is valid.
- Shared candle cache by symbol/timeframe; do not redownload unchanged closed candles every scan.
- Batch same-endpoint/same-parameter requests where useful; batching reduces HTTP overhead but does not pretend to reduce per-symbol credits.
- `/api_usage`/credit telemetry drives budget admission and reserve.
- Crypto venue-native quotes remain preferred for execution/freshness; Twelve Data may provide context when economical.

### GitHub — source-of-truth/control plane
- Source, checkpoint, validation, Actions, deployment, rollback and audit trail.
- V11 changes develop on `signal-v11`; main remains V10 baseline until V11 validation and controlled promotion.
- CI guards single scheduler authority, market-specific policies, data freshness, lifecycle idempotency, AI review completeness and Signal/Binance separation.

### DeepSeek API — always-on API critic
- API-native reviewer suitable for Cloudflare gateway.
- Challenge edge, liquidity, chase risk, invalidation and missing evidence.
- Must never invent unavailable market data.

### Claude AI Max — context/research/design reviewer
- Human-in-the-loop/manual reviewer for regime/context, architecture review and difficult candidates while Max access is not an API entitlement.
- Must not be treated as an unattended production API merely because a Max web subscription exists.
- If a supported Claude API is later provisioned, it can join the Cloudflare AI gateway under the same review schema.

### ChatGPT Plus — logic/design/operations reviewer
- Human-in-the-loop/manual reviewer for logic, mathematics, consistency, code audit, strategy research and checkpoint governance while Plus access is not an API entitlement.
- Must not be treated as an unattended OpenAI API key merely because Plus exists.
- If a supported OpenAI API is later provisioned, it can join the Cloudflare AI gateway under the same review schema.

## 3. Common V11 pipeline

DATA HUB
→ market-specific context builder
→ market-specific scanner
→ verified-fresh quote
→ market-specific Entry Intelligence
→ hard safety gate
→ soft opportunity score
→ AI review policy
→ official Signal
→ Telegram
→ lifecycle TP/SL/expiry
→ immutable History
→ market/symbol/regime statistics
→ bounded continuous learning

Hard safety gates are never relaxed to hit a daily signal quota: verified price, sane instrument identity, valid Entry/SL/TP geometry, minimum liquidity/execution sanity, no duplicate active signal, lifecycle idempotency.

Soft opportunity thresholds may be market/regime specific and learned only inside bounded ranges.

## 4. Market-specific strategy families

### CRYPTO SCALP
Characteristics: 24/7, fast volatility/liquidity rotation, venue-native microstructure more important than named sessions.
Data priority: Binance/Bybit/OKX venue quote and volume/liquidity → short candles → Twelve Data context only when useful → market/news context.
Entry families:
1. Momentum continuation after displacement + shallow pullback/retest.
2. Breakout + acceptance/retest; avoid blind chase.
3. Range liquidity sweep + reclaim when volatility is controlled.
4. Relative-strength rotation among liquid coins.
Primary timeframes: 1m/5m execution context, 15m regime, 1h directional context.
Signal horizon: short scalp; V10 2h TTL is an upper bound to revisit during validation.
Opportunity policy: broad discovery, liquid shortlist, then deep analysis. Do not require every timeframe/indicator or optional derivatives telemetry to agree.

### FOREX SCALP
Characteristics: session-dependent liquidity, macro calendar sensitivity, pair/currency relative strength.
Data priority: Twelve Data verified FX candles/quotes → session state → economic calendar/news context → cross-pair currency strength.
Entry families:
1. London/NY liquidity sweep + MSS/reclaim.
2. Trend pullback into structure during liquid session.
3. Post-news stabilization/retest; never blindly enter into high-impact release uncertainty.
4. Relative currency-strength continuation across majors.
Primary timeframes: 5m execution, 15m structure, 1h/4h bias.
Hard context: session liquidity and high-impact event clearance appropriate to the currencies in the pair.

### GOLD / METAL SCALP
Characteristics: USD/yields/macro sensitivity, strong London/NY behavior, violent event spikes.
Data priority: verified XAU/XAG data → USD/rates/macro context → session/liquidity → structure/volatility.
Entry families:
1. Liquidity sweep + reclaim around session extremes.
2. Trend continuation after impulse and controlled retracement.
3. Breakout/retest only with adequate room and event clearance.
Primary timeframes: 5m execution, 15m structure, 1h/4h macro technical context.
High-impact US events/Fed context must be treated more strictly than ordinary Crypto noise.

### INDEX SCALP
Characteristics: cash-session/opening behavior, index-specific drivers, cross-index relative strength.
Data priority: verified index identity and candles (Twelve Data/Massive where configured) → cash-session state → macro calendar → relative NQ/ES/Dow/DAX/Nikkei context when available.
Entry families:
1. Opening-range / initial-balance break and retest.
2. Liquidity sweep + VWAP/structure reclaim when data supports it.
3. Trend pullback during active cash session.
4. Relative-strength/SMT-style divergence only when both comparison legs are fresh and comparable.
Primary timeframes: 5m execution, 15m structure, 1h context.

## 5. Daily opportunity objective

V11 targets regular opportunity flow, not a forced trade count.
- Scan cadence may be frequent, but expensive/deep data refresh cadence is decoupled from scan cadence.
- Use two-stage discovery: cheap broad scan → small deep shortlist.
- Reuse closed candles until the next candle boundary.
- Refresh live quote immediately before admission and lifecycle decisions.
- Market-specific soft gates prevent a Crypto scalp from being judged like a Gold macro trade or a Forex session setup like a 24/7 coin.
- If no setup clears hard safety and market-specific opportunity gates, emit no official signal rather than fabricate one.

## 6. Data/quota architecture

- One shared data snapshot per symbol/timeframe/version, reused by Scanner, Entry Intelligence and AI evidence.
- Candle TTL aligns to timeframe boundary; live quote TTL is much shorter and market specific.
- Quota allocator reserves credits for lifecycle/verification before discovery/deep analysis.
- Batch calls reduce HTTP overhead but credit accounting remains per underlying symbol/request cost.
- Backoff on 429/provider degradation; never substitute stale data as live.
- Store provider/source/timestamp/freshness on every evidence object.

## 7. AI conflict architecture

V11 distinguishes production automation from subscription-assisted human review.
- DeepSeek API can be called unattended through Cloudflare.
- Claude Max and ChatGPT Plus are not assumed to provide unattended API execution.
- Canonical review schema: direction LONG/SHORT/WAIT, confidence, hardRisk[], evidence[], missingOptional[], provider/model, reviewedAt.
- No provider may invent missing data.
- Opposite direction requires positive supplied evidence; uncertainty is WAIT.
- Provider outage must not silently become approval.
- Until all desired providers are API-accessible, Cloudflare production must use an explicit degraded-mode policy rather than pretending three subscription products are autonomous APIs.

## 8. Separation

Signal V11 remains Signal-only.
Binance Auto is a separate execution project and receives no execution authority merely because a V11 signal exists. Any future bridge requires an explicit risk/execution contract.

## 9. Development phases

Phase A — V11 branch/checkpoint and invariant tests.
Phase B — shared Cloudflare data hub/cache/quota allocator.
Phase C — four independent market context + entry modules.
Phase D — AI gateway schema and degraded-mode policy; remove production dependency on local/VPS CLI.
Phase E — Telegram V11 UX and per-market funnel telemetry.
Phase F — lifecycle/history/learning idempotency audit.
Phase G — shadow validation against V10; measure candidate→gate→review→signal→outcome funnels separately by market/regime.
Phase H — controlled promotion only after CI/deployment/runtime evidence.

## 10. V11 invariants

- GitHub main V10 remains rollback baseline until promotion.
- One Cloudflare scheduler authority.
- No stale/unverified quote can create or close a signal.
- No candidate reject is displayed as an official BUY/SELL.
- Closed signals are immutable history, not deleted.
- Learning counts an outcome once.
- Each market has its own context/entry policy.
- No forced daily trades.
- No AI may fabricate absent data.
- Subscription web products are not mislabeled as unattended APIs.
- Signal and execution authority remain separate.
