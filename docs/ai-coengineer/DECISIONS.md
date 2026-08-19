# AI ENGINEERING DECISIONS

## DECISION-001 — GitHub communication bus
Decision:
ChatGPT and Claude coordinate through `docs/ai-coengineer/` on GitHub.

Rules:
- One writer at a time.
- Source `main` outranks stale checkpoint text.
- Review messages do not authorize production writes by themselves.
- Claude may BLOCK a change; ChatGPT must verify the finding before acting.

## DECISION-002 — Signal market architecture
Decision:
Legacy Futures Signal remains removed. Canonical Signal markets are Forex, Crypto, Metal and Index Cash.

Do not restore:
- Futures Signal proxy logic.
- Global legacy scan/live callbacks.

## DECISION-003 — State safety
Decision:
Releases must preserve `TRADING_STATE` and `v775:books`; no release-driven forced position closure.
