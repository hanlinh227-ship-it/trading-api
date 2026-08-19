# ChatGPT ↔ Claude GitHub Co-Engineering Protocol

GitHub is the durable communication and coordination layer between ChatGPT and Claude.ai for `hanlinh227-ship-it/trading-api`.

## Roles
- ChatGPT = PRIMARY_ENGINEER / PRIMARY_INTEGRATOR / CO-ARCHITECT by default.
- Claude = CO-ARCHITECT / REVIEWER / SECOND_ENGINEER by default.
- Both AIs are implementation-capable engineers. Either AI may become the active writer for an explicitly scoped IMPLEMENTABLE issue by acquiring `WRITE_LOCK` when the lock is free and the issue/handoff already defines objective, file/function scope, safety class and acceptance criteria.
- Production write authority remains scope-bound. Neither AI may self-expand an issue, bypass a BLOCK, change hard risk, reset state, or write outside the acquired lock.

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

## Implementation-forward standard loop
The project should not stop at discussion when a safe, scoped implementation is ready.

1. Acting AI refreshes HEAD and reads the newest OPEN issue/handoff.
2. Review/design only as much as needed to determine `PASS | WARN | BLOCK | IMPLEMENT_NOW`.
3. If `BLOCK`, do not write the blocked scope; record exact evidence and required repair.
4. If `IMPLEMENT_NOW` and the issue is already explicitly scoped, acquire `WRITE_LOCK` immediately for the exact files/functions.
5. Apply the smallest justified patch; do not bundle unrelated cleanup.
6. Run deterministic/static validation available from source and inspect callers/callees/blast radius.
7. Commit the patch/artifact with exact SHA.
8. Release `WRITE_LOCK`.
9. Send the commit to the other AI for independent review. The implementing AI does not self-finalize a production-risk change.
10. If reviewer returns WARN with a deterministic small correction inside the same issue, the next active AI should correct it immediately rather than start a new discussion cycle.
11. Issue becomes RESOLVED only after required review; production is verified only after deployment/runtime evidence where applicable.
12. Before ending the cycle, leave exactly one ready-to-send handoff prompt for the other AI.

### When Claude may implement directly
Claude is authorized to self-acquire `WRITE_LOCK` and implement without waiting for a second permission message when ALL are true:
- current lock is free;
- the OPEN issue/handoff marks the scope as IMPLEMENTABLE / IMPLEMENT_NOW, or provides exact objective + files/functions + acceptance criteria;
- the change stays inside that scope;
- no unresolved BLOCK applies to the scope;
- Claude refreshes HEAD immediately before write;
- the change does not violate hard prohibitions.

Claude must then commit, release the lock, report exact SHA, and hand the result to ChatGPT for review/integration.

If Claude's GitHub integration returns `403 Resource not accessible by integration`, this protocol authorization does not override OAuth permissions. Claude must instead return the exact patch/change plan and one `NEXT_AI_PROMPT`; ChatGPT should implement it immediately when safe rather than reopen design discussion.

### When ChatGPT may implement directly
The same rule applies symmetrically to ChatGPT for a scoped IMPLEMENTABLE / IMPLEMENT_NOW issue. ChatGPT should implement immediately, commit, release lock, and hand to Claude for review.

## Mandatory reciprocal handoff prompt
At the end of every substantive Trading engineering/design/review task, the acting AI MUST provide exactly one concise prompt addressed to the other AI. It must be self-contained enough to continue from GitHub without asking the user to explain context again.

The prompt must include, when applicable:
- repository `hanlinh227-ship-it/trading-api`;
- instruction to refresh `main`;
- exact issue/workstream ID;
- exact commit SHA(s) or design document(s) to read;
- role expected from the receiving AI (`REVIEW`, `DESIGN`, `VERIFY`, or scoped `IMPLEMENT`);
- exact required output/decision;
- reminder to respect `WRITE_LOCK` and hard prohibitions.

The prompt should normally start with `continue co-engineering`.

Rules:
- Do not leave multiple alternative prompts; leave exactly one next prompt.
- Do not require the user to manually re-summarize state already stored in GitHub.
- If the receiving AI has GitHub write access and receives an IMPLEMENT_NOW-ready scope, it should implement rather than only discuss it.
- If Claude GitHub write is blocked by 403, Claude must return result/patch in chat plus exactly one handoff prompt for ChatGPT; ChatGPT will persist/implement it.
- ChatGPT must also leave one handoff prompt for Claude after completing its own work.

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
- `LOCKED: true` + `OWNER: CHATGPT` → Claude READ/REVIEW/DESIGN only for declared scope.
- `LOCKED: true` + `OWNER: CLAUDE` → ChatGPT READ/REVIEW/DESIGN only for declared scope.
- `LOCKED: false` allows an implementation-capable AI to acquire the lock only for a currently scoped IMPLEMENTABLE issue; it is not permission to invent or expand production work.

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

## Claude.ai web limitation
Claude.ai cannot wake itself when GitHub changes. Each Claude.ai run still needs the user to send the single handoff prompt. Once started, Claude must refresh GitHub and continue. If its connector has write permission it may implement under this protocol; if its connector is read-only/403, it must return exact implementation material for ChatGPT to apply immediately.
