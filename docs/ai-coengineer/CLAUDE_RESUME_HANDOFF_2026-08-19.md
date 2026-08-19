# CLAUDE.AI WEB RESUME HANDOFF — 2026-08-19

## User directive — distinguish Claude API from Claude.ai Web
The integrated Claude/Anthropic API inside the production Cloudflare trading runtime is PAUSED. Do not call it unless the user explicitly re-enables `CLAUDE_API_ENABLED=true`.

This does NOT restrict Claude.ai Web. Claude.ai Web remains a FULL CO-ENGINEER with authority to read, audit, optimize, design patches, validate and (if GitHub write permission is later available) write within a free WRITE_LOCK. If the connector is still 403/read-only, return transfer-safe patches for ChatGPT to implement immediately.

ChatGPT remains the physical GitHub writer / primary implementer while Claude.ai Web write access is unavailable.

## Source progress to verify from fresh HEAD

### V78-013 — shared Anthropic transport
Final source migration: `fed3556b5a01504107f84da3fd43fad5f52db0e9`.
Validation: `docs/ai-coengineer/V78-013_VALIDATION.txt`.
DECISION-004 separation retained.

### Integrated Claude API pause
Commit: `c61987415a3e53832a444466406df9ffe25951f9`.
`providers/anthropic-client.js` fail-closes before network fetch unless `CLAUDE_API_ENABLED=true`.
Do not remove this guard without explicit user instruction.

### V78-014 — DecisionEvidence shadow
Final migration: `0c3dc007433c3e9afae1990d07d23c149742500a`.
Validation: `docs/ai-coengineer/V78-014_VALIDATION.txt`.
Signal `runGroup()` and Hyro `done()` append isolated V78-002 DecisionEvidence after existing authoritative persistence; `/evidence/signal` is read-only.

### V78-015 — visible Hub Evidence status
Source: `db2b48f5b96d36e411fbd2f93c0cc73e354fe213`.
Validation: `docs/ai-coengineer/V78-015_VALIDATION.txt`.
Telegram `••• Thêm` includes `📋 Evidence V78`; screen is read-only and exposes freshness/block/runtime state.

### V78-016 — Entry Intelligence Foundation SHADOW
Source commit: `892f7fa8a77c75346c1d522ef93bf9fdf749dc7c`.
New file: `cloudflare-worker/providers/entry-intelligence.js`.
New isolated KV: `v78016:entry_intelligence:signal`.
New read-only endpoint: `/evidence/entry-intelligence`.
`runGroup()` appends market-specific reasoning only after existing books/shadow/DecisionEvidence persistence.
Hub now includes `🧭 Entry Intel` and renders current symbol/market/existing status, quote freshness/source, core and market-specific evidence completeness, WHY NOW, WHY PRICE, WHY SL, WHY TP/RR, INVALIDATION, and existing block reasons.
No ranking or execution authority changed.

### V78-017 — manual analysis shadow coverage
Source commit: `c6edbaba4ad393af79dbaabed05a2d26195d3c1d`.
Validation: `docs/ai-coengineer/V78-017_VALIDATION.txt`.
Manual `/analyze` and Telegram single-symbol analysis now also append DecisionEvidence + Entry Intelligence after `runSymbol()` returns. Returned decision objects remain unchanged.
Hub UI revision now visibly reports `HUB-R11-ENTRY-INTEL-SHADOW`.

## Safety invariants
- Never reset `TRADING_STATE`.
- Never delete/reset `v775:books`.
- Never weaken hard risk, provider freshness, structural SL, or hard-news safeguards.
- Never restore legacy Futures Signal or Hyro TK2.
- Binance20 remains NON_PRODUCTION / QUARANTINED.
- Signal remains advisory-only; Hyro remains current safety-gated real-capital execution authority.
- No fabricated market/provider/test evidence and no secrets in source.
- Integrated Claude API stays paused unless explicitly re-enabled by the user.

## What Claude.ai Web should do when tokens reset
Do NOT spend the first round on transport cleanup. Fresh-read current `main` and independently verify V78-014 through V78-017, then optimize the ENTRY INTELLIGENCE layer against real current code.

Read at minimum:
- `cloudflare-worker/engine-v77168.js`
- `cloudflare-worker/providers/entry-intelligence.js`
- `cloudflare-worker/providers/decision-evidence.js`
- `cloudflare-worker/hub-v77171.js`
- `cloudflare-worker/hyro-scanner.js`
- `cloudflare-worker/hyro-market-context.js`
- `cloudflare-worker/hyro-portfolio-guard.js`
- `docs/ai-coengineer/V78_DECISION_EVIDENCE_SCHEMA.md`
- `docs/ai-coengineer/V78_BASELINE_VALIDATION_MATRIX.md`
- `docs/ai-coengineer/OPEN_ISSUES.md`
- `docs/ai-coengineer/WRITE_LOCK.md`

### Required optimization pass
1. Shadow-compare V78-016 fields against current real Signal outcomes by market. Identify fields that are truly present but mapped incorrectly, and evidence that is genuinely missing.
2. Do not invent new evidence from unavailable providers. UNKNOWN/MISSING must remain explicit.
3. Produce market-specific policy improvements separately for Forex / Crypto / Metals / Index Cash.
4. Improve quality, not trade frequency. Never loosen hard news/freshness/structural-SL just to create entries.
5. Determine which future evaluators can be pure functions first: regime, location, trigger, session, RR feasibility, relative/cross-market context.
6. Only after shadow evidence is validated, propose ranking-authority changes in a separate issue.

### Market-specific goals
Forex: London/New York/overlap, currency-strength/cross-pair context when actually available, HTF structure + M15 location + M5 trigger, fresh analysis quote, event sensitivity, RR feasibility/chase normalization.

Crypto: trend/range/volatility regime, strict spot/perpetual identity, funding/OI/long-short/orderbook/spread only when available, BTC/market context without forced correlation, structural SL and execution feasibility.

Metals: session/liquidity regime, USD/rates only when evidence exists, volatility-normalized location/trigger/RR, XAU/XAG differences preserved.

Index Cash: preserve NAS100/US30/US500/DEX/JP225 cash-index identity, session routing, cross-index relative confirmation when real evidence exists, no Futures resurrection.

Required questions for actionable reasoning:
WHY NOW? WHY THIS PRICE? WHY THIS SL? WHY THIS TP/RR? WHAT INVALIDATES? WHICH DATA SUPPORTS IT? WHICH DATA IS MISSING/STALE/DEGRADED?

## Preferred output when Claude.ai Web returns
Return one compact audit plus ONE transfer-safe implementation bundle for the highest-value next improvement. If direct GitHub write is available, acquire WRITE_LOCK and implement; otherwise provide pre-patch blob guards + exact old/new blocks or complete post-patch files. Finish with exactly one NEXT_AI_PROMPT for ChatGPT.
