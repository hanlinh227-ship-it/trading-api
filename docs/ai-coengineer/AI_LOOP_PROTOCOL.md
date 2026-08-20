# AI LOOP PROTOCOL — GPT + CLAUDE + DEEPSEEK

Status: STAGED
Architecture: web/cloud-first
Repository: `hanlinh227-ship-it/trading-api`

## Roles

- GPT/Codex = ORCHESTRATOR + ARCHITECT + FINAL REVIEWER.
- Claude.ai = OPTIMIZER + SECOND REVIEWER for difficult logic; no production Anthropic API.
- DeepSeek API = PRIMARY IMPLEMENTER running from GitHub Actions cloud.
- GitHub = source of truth, task bus, state, CI and audit trail.
- Cloudflare = production Signal runtime and deployment target.

## State machine

`DISCOVER -> SPEC -> CLAUDE_OPTIMIZE(optional) -> DEEPSEEK_IMPLEMENT -> CI -> GPT_REVIEW -> FIX_REQUIRED | ACCEPTED -> DEPLOY -> LIVE_VERIFY -> DONE`

Maximum implementation/review rounds per task: 4. If no material progress after the limit, set `BLOCKED` and require human review.

Each round must add at least one of: source diff, validation evidence, new diagnosis, deployment evidence, live evidence, or explicit architectural decision.

## Write serialization

`docs/ai-coengineer/WRITE_LOCK.md` remains mandatory.

- DeepSeek may edit only when lock owner is `DEEPSEEK` and scope matches the task.
- GPT/Codex may review while DeepSeek owns the lock but must not modify overlapping source.
- Claude is review/optimization-only unless the user explicitly changes this architecture.
- Every writer must stale-check HEAD immediately before write.

## Task contract

Every implementation task must provide:

- task ID
- base SHA
- objective
- allowed paths
- forbidden paths
- acceptance criteria
- validation commands
- deployment requirement
- live-verification requirement
- max rounds

DeepSeek must not expand scope.

## Protected invariants

The following are protected and may not be weakened merely to make a task pass:

- `TRADING_STATE`
- `v775:books`
- quote freshness
- structural SL
- RR safeguards
- hard-news safeguards
- execution authority
- production credentials/secrets
- Signal-only architecture

Absolute prohibitions remain:

- no Hyro auto-trade restoration
- no real-capital execution path
- no Futures Signal restoration
- no TK2 restoration
- no Futures substitution for Index Cash
- no Binance20 production activation
- no production Claude/Anthropic API
- no fabricated provider/test/deployment/live evidence

## DeepSeek API secret

Expected GitHub Actions secret: `DEEPSEEK_API_KEY`.

The secret must never be written to repository files, logs, prompts committed to Git, issues, PR comments, or validation evidence.

## Execution status vocabulary

Use these terms strictly:

- DESIGNED = architecture/spec exists only
- STAGED = workflow/code exists but has not been executed
- RUNNING = a real cloud job is currently/has actually executed
- DEPLOYED = Cloudflare accepted a real deployment
- LIVE_VERIFIED = production verification actually passed
- RESOLVED = acceptance criteria and required live verification passed

Never promote a state without evidence.

## Current bootstrap status

AI-INFRA-001 is infrastructure-only. No Trading Signal/runtime logic is in scope. The DeepSeek workflow is intentionally staged without execution at the user's request.
