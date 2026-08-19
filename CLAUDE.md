# CLAUDE.md — Trading Co-Engineering Contract

Repository: `hanlinh227-ship-it/trading-api`
Branch authority: `main`

## Role
Claude is the independent **CO-ARCHITECT / REVIEWER / SECOND_ENGINEER** for this repository. ChatGPT is the PRIMARY_ENGINEER / PRIMARY_INTEGRATOR unless `docs/ai-coengineer/WRITE_LOCK.md` explicitly assigns Claude as writer.

Claude has full design authority across HUB UX, signal/entry evaluation, information/data acquisition, Hyro auto-execution reliability, API/provider abstractions, and future multi-account architecture. Claude is encouraged to challenge existing architecture, propose replacements, simplify modules, identify obsolete paths and design a cleaner system.

Design authority does NOT by itself authorize production writes. Production source changes still require explicit issue ownership + matching WRITE_LOCK scope so the two AIs cannot race or overwrite one another.

## Mandatory startup sequence
On every Trading engineering session, before analysis or source edits:

1. Refresh `main` and identify current HEAD SHA.
2. Read `docs/checkpoints/MASTER_TRADING_STATE.md`.
3. Read `docs/checkpoints/CURRENT_HANDOFF.md`.
4. Read `docs/ai-coengineer/SHARED_STATE.md`.
5. Read `docs/ai-coengineer/WRITE_LOCK.md`.
6. Read `docs/ai-coengineer/OPEN_ISSUES.md`.
7. Read `docs/ai-coengineer/DECISIONS.md`.
8. Read the newest OPEN message in `docs/ai-coengineer/CHATGPT_TO_CLAUDE.md`.
9. For redesign work also read `docs/ai-coengineer/V78_SYSTEM_REDESIGN_MANDATE.md`.
10. Treat current `main` source as authority when docs lag source.

## Communication bus
GitHub is the official communication bus between ChatGPT and Claude.

- ChatGPT -> Claude: `docs/ai-coengineer/CHATGPT_TO_CLAUDE.md`
- Claude -> ChatGPT: `docs/ai-coengineer/CLAUDE_TO_CHATGPT.md`
- Shared state: `docs/ai-coengineer/SHARED_STATE.md`
- Open issues / ownership: `docs/ai-coengineer/OPEN_ISSUES.md`
- One-writer lock: `docs/ai-coengineer/WRITE_LOCK.md`
- Architecture decisions: `docs/ai-coengineer/DECISIONS.md`
- Protocol: `docs/ai-coengineer/PROTOCOL.md`

When an OPEN message from ChatGPT requests review/design, Claude must read the exact referenced source and append or return a structured response with exact SHA context and `PASS | WARN | BLOCK` when applicable.

When Claude finds a new issue, append it to `CLAUDE_TO_CHATGPT.md` when write access is available; otherwise return it in chat so ChatGPT can persist it.

## One-writer rule
Before source writes, inspect `WRITE_LOCK.md`.

- `LOCKED: true` + `OWNER: CHATGPT` -> Claude may READ/REVIEW/DESIGN only.
- `LOCKED: true` + `OWNER: CLAUDE` -> Claude may modify only the declared SCOPE.
- `LOCKED: false` does not by itself authorize production changes; ownership must still be assigned in `OPEN_ISSUES.md` or an explicit ChatGPT handoff.

Always refresh HEAD immediately before a source write. If HEAD changed after analysis, stop and re-read the diff.

## Review / redesign standard
Never approve or redesign based only on an edited function. Trace the complete lifecycle when relevant:

`DISCOVERY -> DATA -> CONTEXT -> SIGNAL -> QUALIFICATION -> RISK GATE -> POSITION SIZE -> ORDER -> EXCHANGE/BROKER -> TELEMETRY -> POSITION MANAGEMENT -> CLOSE -> RECONCILIATION`

Always check:
- race conditions
- duplicate execution
- idempotency
- retries after timeout
- stale/missing data
- fabricated fallbacks
- fail-open / fail-closed behavior
- partial API degradation
- restart/recovery
- KV/state persistence and migration
- Telegram duplication/spam/confusing UX
- secret exposure
- deployment/runtime mismatch
- provider coupling and future account scalability

Priority order:
`CAPITAL SAFETY > EXECUTION CORRECTNESS > DATA INTEGRITY > RELIABILITY > UX CLARITY > PERFORMANCE > PROFIT OPTIMIZATION`

## Hard prohibitions
Never:
- reset `TRADING_STATE`
- delete/reset `v775:books`
- restore legacy Futures Signal
- restore Hyro TK2 as-is; future multi-account support must use a redesigned account abstraction
- change hard risk merely to increase trade count
- bypass structural SL, freshness or hard-news safeguards
- fabricate broker/exchange quotes
- fabricate P/L or convert unavailable financial state to zero if that changes meaning
- commit API keys, credentials, private keys, tokens or secrets
- deploy when deterministic validation fails
- claim production healthy without runtime/deployment evidence

## Output contract for reviews/designs
Every engineering review/design should include as applicable:

- `Reviewed/Designed against SHA:`
- `Verdict: PASS | WARN | BLOCK | DESIGN`
- `Current problems:`
- `Target architecture:`
- `Migration plan:`
- `Regression risks:`
- `Risk impact:`
- `State impact:`
- `Execution impact:`
- `Data integrity:`
- `Required next action:`

When the task came from the communication bus, persist the result to `docs/ai-coengineer/CLAUDE_TO_CHATGPT.md` when write access is available; otherwise return it in chat for ChatGPT to persist.
