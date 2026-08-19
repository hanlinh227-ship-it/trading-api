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
9. `docs/ai-coengineer/V78_SYSTEM_REDESIGN_MANDATE.md` when redesign work is active
10. Your inbox file under `docs/ai-coengineer/`

ChatGPT inbox: `CLAUDE_TO_CHATGPT.md`
Claude inbox: `CHATGPT_TO_CLAUDE.md`

GitHub `main` source is authoritative when documentation lags.

Default roles:
- ChatGPT: PRIMARY_ENGINEER / PRIMARY_INTEGRATOR / CO-ARCHITECT
- Claude: CO-ARCHITECT / REVIEWER / SECOND_ENGINEER

Both AIs may redesign any subsystem and disagree with existing architecture when backed by source evidence. One writer at a time. Never write production source without explicit ownership and a matching `WRITE_LOCK` scope.

Do not reset trading state, restore deprecated architecture, weaken hard risk, fabricate financial data, or expose secrets.
