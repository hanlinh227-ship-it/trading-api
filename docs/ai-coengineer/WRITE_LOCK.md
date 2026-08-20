# AI WRITE LOCK

LOCKED: true
OWNER: CLAUDE_LOCAL
SCOPE: AI-LOOP-INFRA-V1
ACQUIRED: 2026-08-20
BASE_SHA: 40f020ccc91ff31d061ae22795242da792e01b7b

## Previous scope released

V78-032 PR #60 follow-up is COMPLETE and its lock is RELEASED.
Final PR #60 head: `93424ed`. PR #60 is NOT merged and must be merged manually by ChatGPT.
Separated findings: issue #61 (hub global-scan true positive), issue #62 (Cloudflare
Workers Build provider-side failure). Details in `CLAUDE_TO_CHATGPT.md`.

## Allowed scope for AI-LOOP-INFRA-V1

Only these paths may be written under this lock:

- `docs/ai-coengineer/AI_LOOP_CONTRACT.md`
- `docs/ai-coengineer/AI_LOOP_STATE.schema.json`
- `scripts/ai/ai-loop.ps1`
- `scripts/ai/deepseek_reviewer.py`
- `scripts/ai/claude_loop_prompt.md`
- `scripts/ai/ai-loop-selftest.mjs`
- `.github/workflows/ai-loop-deepseek-review.yml`
- `docs/ai-coengineer/WRITE_LOCK.md` (this file)
- `docs/ai-coengineer/CLAUDE_TO_CHATGPT.md` (bus append only)
- `.gitignore` (scope amendment, 2026-08-20: the loop's own test path runs
  `python -m py_compile`, which generates `scripts/ai/__pycache__/`. Without an ignore
  entry that bytecode is offered for commit on every round. Raised as a P1 lock-scope
  violation by Codex on PR #63 and legalised here explicitly rather than silently.)

No Trading business source may be modified under this lock. In particular
`cloudflare-worker/**`, `data/**` and all existing trading workflows are OUT OF SCOPE.

## Protocol

- Refresh `origin/main` and the working branch HEAD immediately before any write.
- One writer at a time.
- Loop infrastructure is REVIEW/ORCHESTRATION only. It may never merge, deploy, or
  mutate GitHub secrets.
- MAX_ROUNDS is hard-bounded at 5. No unbounded loop may be created.
- Preserve TRADING_STATE and v775:books.
- Preserve SIGNAL-ONLY architecture and executionAuthority=SIGNAL_ONLY/NONE.
- Do not weaken quote freshness, structural SL, RR, hard-news, anti-chase, or market
  identity protections.
- Do not restore Hyro auto-trade, Futures Signal, TK2, Binance20 production execution, or
  any real-capital execution path.
- V73 historical data and `symbol_knowledge_registry.json` remain read-only.
- Production Claude/Anthropic API remains paused. The local loop uses Claude Code
  subscription auth via `claude -p`, never Anthropic API billing.
- Cloudflare production deploy remains OFF: `deploy-cloudflare` requires repository
  variable `ENABLE_CLOUDFLARE_AUTO_DEPLOY == 'true'`, which is not set.
- No secret may be committed or printed. Secret existence may only be checked by name
  via `gh secret list`.
- `--dangerously-skip-permissions` is forbidden. The loop uses narrow `--allowedTools`.
