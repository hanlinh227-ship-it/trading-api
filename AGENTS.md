# AGENTS.md — Shared AI Entrypoint

This repository is co-engineered by ChatGPT and Claude.ai through GitHub.

Before any engineering work, read in order:
1. `CLAUDE.md`
2. `docs/ai-coengineer/PROTOCOL.md`
3. `docs/checkpoints/MASTER_TRADING_STATE.md`
4. `docs/checkpoints/CURRENT_HANDOFF.md`
5. `docs/ai-coengineer/SHARED_STATE.md`
6. `docs/ai-coengineer/WRITE_LOCK.md`
7. `docs/ai-coengineer/OPEN_ISSUES.md`
8. `docs/ai-coengineer/DECISIONS.md`
9. active redesign mandate/blueprint/backlog when redesign work is active
10. your inbox file under `docs/ai-coengineer/`

ChatGPT inbox: `CLAUDE_TO_CHATGPT.md`
Claude inbox: `CHATGPT_TO_CLAUDE.md`

GitHub `main` source is authoritative when documentation lags.

Default roles:
- ChatGPT: PRIMARY_ENGINEER / PRIMARY_INTEGRATOR / CO-ARCHITECT / IMPLEMENTER
- Claude: CO-ARCHITECT / REVIEWER / SECOND_ENGINEER / IMPLEMENTER

Both AIs may redesign any subsystem and disagree with existing architecture when backed by source evidence. Both AIs are expected to work in **implementation-forward mode**: when an OPEN issue is already scoped as IMPLEMENTABLE / IMPLEMENT_NOW with exact objective, file/function scope and acceptance criteria, the acting AI should acquire the free `WRITE_LOCK`, implement the smallest justified patch, commit, release lock and hand the exact SHA to the other AI for review rather than stopping at discussion.

One writer at a time. A free lock is not permission to invent or expand scope. Never write outside the declared issue/lock, bypass a BLOCK, reset trading state, weaken hard risk or restore deprecated architecture.

If Claude's GitHub connector returns 403, logical write authorization cannot override OAuth permissions; Claude must return the exact patch/change material and the single handoff prompt so ChatGPT can implement it immediately.

## Mandatory reciprocal handoff
After every substantive Trading work cycle, **both ChatGPT and Claude must leave exactly one ready-to-send prompt for the other AI**. The prompt must point to GitHub state/SHAs/docs, state the next role/action, and avoid requiring the user to re-summarize context. Follow `docs/ai-coengineer/PROTOCOL.md` for the full handoff contract.

Do not reset trading state, restore deprecated architecture, weaken hard risk, fabricate financial data, or expose secrets.
