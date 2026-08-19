# CLAUDE RESUME HANDOFF — 2026-08-19

## User directive
Claude API usage is PAUSED. Do not call Anthropic/Claude API until the user explicitly re-enables it. ChatGPT remains the physical GitHub implementer. Claude should resume later as optimizer/auditor/patch designer from fresh GitHub HEAD, not by relying on stale chat context.

## New production changes while Claude is unavailable

### V78-014 — RESOLVED / IMPLEMENTED
Final migration commit: `0c3dc007433c3e9afae1990d07d23c149742500a`
Validation: `docs/ai-coengineer/V78-014_VALIDATION.txt` = PASS.

Scope:
- new `cloudflare-worker/providers/decision-evidence.js`;
- Signal `runGroup()` adds isolated DecisionEvidence shadow writes only after existing books + shadow persistence;
- Hyro `done()` adds isolated DecisionEvidence shadow writes only after existing runtime KV persistence;
- additive read-only `/evidence/signal` endpoint;
- no gate/threshold/risk/execution-authority/output-shape change intended.

### Claude/Anthropic API pause — ACTIVE
Commit: `c61987415a3e53832a444466406df9ffe25951f9`

`providers/anthropic-client.js` now fail-closes before network fetch unless:
`CLAUDE_API_ENABLED=true`

Default is disabled. `isClaudeApiEnabled(env)` is exported for observability. This was an explicit user instruction to prevent further Claude API/token usage for now.

### V78-015 — HUB EVIDENCE/RUNTIME STATUS — IMPLEMENTED
Source commit: `db2b48f5b96d36e411fbd2f93c0cc73e354fe213`
Validation: `docs/ai-coengineer/V78-015_VALIDATION.txt` = PASS.

Visible Telegram Hub changes:
- `••• Thêm` now includes `📋 Evidence V78`;
- new callback `evidence` is read-only;
- screen reads only V78-014 DecisionEvidence;
- shows Signal evidence sample count, LIVE/STALE/UNKNOWN distribution, gate-block count, latest Signal outcome, latest Hyro outcome, Hub/evidence revision;
- visibly shows Claude API `PAUSED`/`ENABLED` from `isClaudeApiEnabled(env)`;
- no trading decisions or KV writes from the Hub view;
- `verifyTelegram` remains untouched.

## Safety invariants that remain mandatory
- Never reset `TRADING_STATE`.
- Never delete/reset `v775:books`.
- Never weaken hard risk, provider freshness, structural SL, or hard-news safeguards.
- Never restore legacy Futures Signal or Hyro TK2.
- Binance20 remains NON_PRODUCTION / QUARANTINED.
- Signal remains advisory-only; Hyro remains the current safety-gated real-capital execution authority.
- No fabricated market/provider/test evidence and no secrets in source.

## Next optimization target when Claude returns
Do NOT spend the next round on another generic transport cleanup. The user now wants visible trading-quality progress.

Recommended next batch: `V78 ENTRY INTELLIGENCE FOUNDATION` — optimization/design first, ChatGPT implementation second.

Claude should fresh-read at minimum:
- `cloudflare-worker/engine-v77168.js`
- `cloudflare-worker/hyro-scanner.js`
- `cloudflare-worker/hyro-market-context.js`
- `cloudflare-worker/hyro-portfolio-guard.js`
- `cloudflare-worker/providers/decision-evidence.js`
- `cloudflare-worker/hub-v77171.js`
- `docs/ai-coengineer/V78_DECISION_EVIDENCE_SCHEMA.md`
- `docs/ai-coengineer/V78_BASELINE_VALIDATION_MATRIX.md`

Design a batch that improves entry reasoning without weakening filters merely to create more trades. Required market-specific separation:

### Forex
- session-aware London/New York/overlap logic;
- currency-strength and cross-pair confirmation;
- HTF structure + location + M5 trigger;
- explicit fresh analysis quote;
- event/news sensitivity;
- RR feasibility and chase-distance normalization.

### Crypto
- trend/range/volatility regime;
- spot/perpetual identity integrity;
- funding, OI, long/short, orderbook/spread context when actually available;
- BTC/market context without forcing correlation;
- structural SL + execution feasibility.

### Metals
- session/liquidity regime;
- USD/rates context only when real evidence exists;
- volatility-normalized location/trigger/RR;
- XAU/XAG separation where behavior differs.

### Index Cash
- preserve cash-index identity (`NAS100`, `US30`, `US500`, `DEX`, `JP225`);
- session routing;
- cross-index relative strength/SMT-style confirmation when evidence supports it;
- no Futures resurrection.

Required DecisionEvidence questions for every actionable candidate:
- WHY NOW?
- WHY THIS PRICE?
- WHY THIS SL?
- WHY THIS TP/RR?
- WHAT INVALIDATES?
- WHICH DATA SUPPORTS IT?
- WHICH DATA IS MISSING/STALE/DEGRADED?

Output classes remain explicit:
`MARKET`, `LIMIT`, `WATCH`, `NO_TRADE`, `DATA_BLOCK` (and existing advisory MARKET_SIGNAL semantics where applicable).

## Preferred implementation structure
Claude should propose small pure evaluators first, not a monolithic engine rewrite, for example:
- market/instrument classifier;
- regime evaluator;
- location evaluator;
- trigger evaluator;
- evidence assembler/ranker;
- market-specific policy adapters.

Keep existing production outputs compatible initially; shadow-compare new reasoning against current outputs before authority changes.

## Hub follow-up
After entry-intelligence shadow comparison is stable, extend the Evidence screen to show compact `WHY NOW / BLOCK REASON / FRESHNESS / RR` for the latest top setups. Keep it read-only until the new reasoning is verified.

## Resume instruction
When Claude has tokens again: refresh `main`, verify V78-014 and V78-015, confirm Claude API remains paused, then produce one transfer-safe implementation bundle for the entry-intelligence foundation. Do not call Anthropic from the production runtime during that work unless the user explicitly re-enables `CLAUDE_API_ENABLED=true`.
