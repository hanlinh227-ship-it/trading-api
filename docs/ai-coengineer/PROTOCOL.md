# ChatGPT ↔ Claude GitHub Co-Engineering Protocol

GitHub is the durable communication and coordination layer between ChatGPT and Claude.ai for `hanlinh227-ship-it/trading-api`.

## Roles
- ChatGPT = PRIMARY_ENGINEER / PRIMARY_INTEGRATOR / CO-ARCHITECT by default.
- Claude = CO-ARCHITECT / REVIEWER / SECOND_ENGINEER by default.
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
9. Read the active redesign mandate/blueprint when AI-003/V78 work is active.
10. Treat current `main` source as authority when docs lag source.

## Standard loop
1. Writer/architect refreshes HEAD.
2. If source writing is required, acquire `WRITE_LOCK` for exact scope.
3. Apply the smallest justified patch or produce the scoped design/review.
4. Commit durable artifacts/source when authorized.
5. Release lock after source commit.
6. Append an OPEN review/design request with exact commit SHA/context.
7. Reviewer/other architect refreshes HEAD and reviews exact artifacts plus surrounding callers/callees where relevant.
8. Reviewer returns `PASS | WARN | BLOCK | DESIGN` with exact SHA context.
9. Primary integrator verifies findings.
10. Issue becomes RESOLVED only after required review; production is verified only after deployment/runtime evidence.
11. **Before ending the work cycle, the AI MUST leave exactly one ready-to-send handoff prompt for the other AI.**

## Mandatory reciprocal handoff prompt
This applies equally to ChatGPT and Claude.

At the end of every substantive Trading engineering/design/review task, the acting AI MUST provide exactly one concise prompt addressed to the other AI. The prompt must be self-contained enough to continue from GitHub without asking the user to explain context again.

The handoff prompt must include, when applicable:
- repository `hanlinh227-ship-it/trading-api`;
- instruction to refresh `main`;
- exact issue/workstream ID;
- exact commit SHA(s) or design document(s) to read;
- role expected from the receiving AI (`REVIEW`, `DESIGN`, `VERIFY`, or scoped `IMPLEMENT`);
- exact required output/decision;
- reminder to respect `WRITE_LOCK` and hard prohibitions.

The prompt should normally start with:
`continue co-engineering`

Rules:
- Do not leave multiple alternative prompts; leave exactly one next prompt.
- Do not require the user to manually re-summarize state already stored in GitHub.
- If the receiving AI has GitHub write access, it should persist its substantive result to its outbox.
- If Claude GitHub write is blocked (for example 403), Claude must return the result in chat and still leave one handoff prompt for ChatGPT; ChatGPT will persist the result.
- ChatGPT must also leave one handoff prompt for Claude after completing its own work, even when GitHub messages have already been written.

## Message format
Every durable bus message must include:
- timestamp
- FROM
- TO
- STATUS: OPEN | RESOLVED | SUPERSEDED
- referenced commit SHA when applicable
- scope
- request or verdict
- `NEXT_AI_PROMPT:` containing the single handoff prompt when the message completes a work cycle

## Conflict handling
If the AIs disagree:
- do not overwrite each other;
- record `DISAGREE` with source evidence;
- prefer deterministic tests/runtime evidence over model opinion;
- if evidence is insufficient, keep the issue OPEN.

## Stale-context protection
Before every source write, compare current HEAD against the SHA used during analysis. If HEAD changed, re-read affected source and diff before writing.

## One-writer rule
- `LOCKED: true` + `OWNER: CHATGPT` → Claude READ/REVIEW/DESIGN only.
- `LOCKED: true` + `OWNER: CLAUDE` → ChatGPT READ/REVIEW/DESIGN only for declared scope.
- `LOCKED: false` does not itself grant production write authority; issue ownership or explicit handoff is still required.

## Review standard
For execution changes, trace:
`DISCOVERY -> DATA -> CONTEXT -> SIGNAL -> QUALIFICATION -> RISK GATE -> POSITION SIZE -> ORDER -> EXCHANGE/BROKER -> TELEMETRY -> POSITION MANAGEMENT -> CLOSE -> RECONCILIATION`

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
- KV/state persistence/migration
- Telegram duplication/spam/confusing UX
- secrets exposure
- deployment/runtime mismatch
- provider/account coupling and scalability

Priority:
`CAPITAL SAFETY > EXECUTION CORRECTNESS > DATA INTEGRITY > RELIABILITY > UX CLARITY > PERFORMANCE > PROFIT OPTIMIZATION`

## Hard prohibitions
Never:
- reset `TRADING_STATE`;
- delete/reset `v775:books`;
- restore legacy Futures Signal;
- restore Hyro TK2/multi-account logic as-is;
- weaken hard risk to increase trade count;
- bypass structural SL/freshness/hard-news safeguards;
- fabricate broker/exchange quotes;
- fabricate P/L or convert unavailable financial state to zero if meaning changes;
- commit secrets/tokens/private keys;
- deploy when deterministic validation fails;
- claim production healthy without deployment/runtime evidence.

## Claude.ai limitation
Claude.ai cannot wake itself when GitHub changes. Therefore this protocol provides durable continuity, but each Claude.ai run must be started by the user with the single handoff prompt left by ChatGPT (usually beginning `continue co-engineering`). Once started, Claude must read this protocol and continue from GitHub without asking the user to paste state manually.
