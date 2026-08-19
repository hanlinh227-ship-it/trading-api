# ChatGPT ↔ Claude GitHub Co-Engineering Protocol

GitHub is the durable communication and coordination layer between ChatGPT and Claude.ai for `hanlinh227-ship-it/trading-api`.

## Roles
- ChatGPT = PRIMARY_ENGINEER by default.
- Claude = REVIEWER / SECOND_ENGINEER by default.
- Either AI may become writer only when ownership and scope are explicitly assigned.

## Durable channels
- `docs/ai-coengineer/CHATGPT_TO_CLAUDE.md` — requests, questions and commit handoffs from ChatGPT.
- `docs/ai-coengineer/CLAUDE_TO_CHATGPT.md` — Claude reviews, objections, findings and replies.
- `docs/ai-coengineer/SHARED_STATE.md` — concise canonical engineering state.
- `docs/ai-coengineer/OPEN_ISSUES.md` — issue status, severity, owner and reviewer.
- `docs/ai-coengineer/WRITE_LOCK.md` — one-writer serialization lock.
- `docs/ai-coengineer/DECISIONS.md` — durable architecture decisions.

## Mandatory startup for both AIs
1. Refresh `main` and capture HEAD SHA.
2. Read `docs/checkpoints/MASTER_TRADING_STATE.md`.
3. Read `docs/checkpoints/CURRENT_HANDOFF.md`.
4. Read `docs/ai-coengineer/SHARED_STATE.md`.
5. Read `docs/ai-coengineer/WRITE_LOCK.md`.
6. Read `docs/ai-coengineer/OPEN_ISSUES.md`.
7. Read `docs/ai-coengineer/DECISIONS.md`.
8. Read the newest OPEN message addressed to that AI.
9. Treat current `main` source as authority when docs lag source.

## Standard loop
1. Writer refreshes HEAD.
2. Writer acquires `WRITE_LOCK` for exact scope.
3. Writer applies the smallest justified patch.
4. Writer commits source.
5. Writer releases lock.
6. Writer appends an OPEN review request with exact commit SHA.
7. Reviewer refreshes HEAD and reviews exact commit plus surrounding callers/callees.
8. Reviewer appends `PASS | WARN | BLOCK` with exact reviewed SHA.
9. Primary engineer verifies reviewer findings.
10. Issue becomes RESOLVED only after review; production is verified only after deployment/runtime evidence.

## Message format
Every message must include:
- timestamp
- FROM
- TO
- STATUS: OPEN | RESOLVED | SUPERSEDED
- referenced commit SHA when applicable
- scope
- request or verdict

## Conflict handling
If the AIs disagree:
- do not overwrite each other;
- record `DISAGREE` with source evidence;
- prefer deterministic tests/runtime evidence over model opinion;
- if evidence is insufficient, keep the issue OPEN.

## Stale-context protection
Before every source write, compare current HEAD against the SHA used during analysis. If HEAD changed, re-read affected source and diff before writing.

## One-writer rule
- `LOCKED: true` + `OWNER: CHATGPT` → Claude READ/REVIEW only.
- `LOCKED: true` + `OWNER: CLAUDE` → ChatGPT READ/REVIEW only for declared scope.
- `LOCKED: false` does not itself grant write authority; issue ownership or explicit handoff is still required.

## Review standard
For execution changes, trace:
`SIGNAL -> QUALIFICATION -> RISK GATE -> POSITION SIZE -> ORDER -> EXCHANGE/BROKER -> TELEMETRY -> POSITION MANAGEMENT -> CLOSE -> RECONCILIATION`

Always check:
- race conditions
- duplicate execution
- idempotency
- timeout/retry behavior
- stale/missing data
- fabricated fallbacks
- fail-open/fail-closed behavior
- partial API degradation
- restart/recovery
- KV/state persistence
- Telegram duplication/spam
- secrets exposure
- deployment/runtime mismatch

Priority:
`CAPITAL SAFETY > EXECUTION CORRECTNESS > DATA INTEGRITY > RELIABILITY > PERFORMANCE > PROFIT OPTIMIZATION`

## Hard prohibitions
Never:
- reset `TRADING_STATE`;
- delete/reset `v775:books`;
- restore legacy Futures Signal;
- restore Hyro TK2/multi-account logic;
- weaken hard risk to increase trade count;
- bypass structural SL/freshness/hard-news safeguards;
- fabricate broker/exchange quotes;
- fabricate P/L or convert unavailable financial state to zero if meaning changes;
- commit secrets/tokens/private keys;
- deploy when deterministic validation fails;
- claim production healthy without deployment/runtime evidence.

## Claude.ai limitation
Claude.ai cannot wake itself when GitHub changes. Therefore this protocol provides durable continuity, but each Claude.ai run must be started by the user with a short `continue co-engineering` instruction. Once started, Claude must read this protocol and continue from GitHub without asking the user to paste state manually.
