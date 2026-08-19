# V78 CLAUDE PHASE 2 BACKLOG

Status: PARTIAL INGEST — EXACT CLAUDE BODY NOT AVAILABLE IN CURRENT GITHUB BUS / ATTACHMENTS
Recorded by: ChatGPT
Date: 2026-08-19

## Integrity note
The user states Claude has produced a Phase 2 deliverable containing:
- a concrete target HUB menu;
- a shared `DecisionEvidence` schema;
- an ordered atomic backlog `V78-001` through `V78-091`.

The exact Claude Phase 2 text is not present in `CLAUDE_TO_CHATGPT.md`, `CHATGPT_TO_CLAUDE.md`, or the currently available uploaded Claude transcript. Therefore ChatGPT MUST NOT fabricate, reconstruct, renumber, or paraphrase the 91-item Claude backlog as if it were Claude-authored.

This file reserves the canonical path requested for Phase 2. The exact Claude deliverable must be appended/replaced from Claude chat verbatim or near-verbatim once supplied.

## Source-backed findings independently verified by ChatGPT during Phase 2 ingest

### Signal crypto execution authority
`cloudflare-worker/engine-v77168.js` uses public unsigned market-data helpers:
- `bybit(path, params)` builds a query string and calls `fetchTimeout(https://api.bybit.com...)` with no POST method/signature;
- `okx(path, params)` similarly uses public GET;
- observed crypto endpoints include `/v5/market/tickers`, `/v5/market/kline`, and `/api/v5/market/candles`;
- no `/v5/order/create` occurrence exists in `engine-v77168.js`.

Conclusion: current Signal crypto path is advisory/public-data analysis, not real-capital execution. Current real-capital execution authority is the Hyro stack. Orphaned Binance20 code remains NON_PRODUCTION per DECISION-005.

### V78-041 news/funding decision
`cloudflare-worker/hyro-scanner.js` implements `fundingView()` as a funding/carry risk gate. It can block adverse funding near settlement and apply an RR penalty. This is not a news/event-risk feed and cannot substitute for a hard-news/context gate.

Decision: Hyro executable auto-trade requires a distinct hard-news/context gate under the active mandate. Funding-rate checks remain as a separate microstructure/carry gate. Advisory WATCH may remain `NEWS_UNVERIFIED` when no authoritative news source exists; executable new orders must fail closed when required news evidence is unavailable.

See `DECISION-009 — V78-041 Hyro hard-news gate` in `DECISIONS.md`.

## Pending exact Claude Phase 2 sections

### Target HUB menu
PENDING EXACT CLAUDE TEXT — do not fabricate.

### Shared DecisionEvidence schema
PENDING EXACT CLAUDE TEXT — do not fabricate.

### Ordered atomic backlog V78-001..V78-091
PENDING EXACT CLAUDE TEXT — do not fabricate or renumber.

## Required ingest action
Claude must resend the full Phase 2 deliverable in chat because its GitHub MCP write remains blocked by 403. ChatGPT will then persist the exact target HUB menu, exact `DecisionEvidence` schema, and exact V78-001..V78-091 backlog into this file without changing numbering or attribution.
