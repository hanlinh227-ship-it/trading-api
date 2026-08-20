# AI LOOP PROTOCOL — CODEX + CLAUDE CODE + DEEPSEEK

Status: STAGED_FOR_FIRST_REAL_TASK
Architecture: web/cloud-first
Repository: `hanlinh227-ship-it/trading-api`

## Roles

- Codex = CONTROL PLANE: architect, task/spec creator, GitHub reviewer and final acceptance authority.
- Claude Code Web / Claude Max = DEEP OPTIMIZER + SECOND REVIEWER for difficult or protected Trading logic. Production Anthropic API remains OFF.
- DeepSeek API = PRIMARY AUTOMATED IMPLEMENTER/FIXER running in GitHub Actions.
- GitHub = source of truth, task bus, state, WRITE_LOCK, PR/CI evidence and audit trail.
- Cloudflare = production Signal runtime and deployment/live-verification target.

## Practical automation boundary

Codex GitHub review can be triggered from a PR using `@codex review` when the Codex GitHub integration is enabled for this repository.

DeepSeek is headless through GitHub Actions and can implement, validate, consume Codex findings and repair for bounded rounds.

Claude Max / Claude Code Web is subscription-based and is NOT represented as an Anthropic API credential. It can run remote web tasks after being started, but GitHub cannot reliably wake a Max web session headlessly. Therefore protected/high-complexity tasks may enter `CLAUDE_REVIEW_REQUIRED` and wait for the user to start one Claude Code Web review session. This is the only non-headless segment while production Anthropic API is prohibited.

Never claim FULLY_AUTONOMOUS_3_AI while this limitation exists.

## Normal state machine

`USER_PROMPT -> CODEX_DISCOVER -> CODEX_SPEC -> DEEPSEEK_IMPLEMENT -> DEEPSEEK_VALIDATE -> PR -> CODEX_REVIEW`

Then:

- Codex blockers -> `DEEPSEEK_FIX -> VALIDATE -> CODEX_REVIEW`.
- No blockers + Claude not required -> `ACCEPT -> MERGE/DEPLOY_GATE -> LIVE_VERIFY -> DONE`.
- No blockers + Claude required -> `CLAUDE_REVIEW_REQUIRED -> CLAUDE_VERDICT -> DEEPSEEK_FIX or ACCEPT`.
- `MAX_ROUNDS` exhausted -> `BLOCKED -> STOP`.

## Task creation contract

Codex creates a GitHub Issue whose title starts with `[AI-TASK]` and whose body contains exactly one machine-readable block:

`AI_TASK_JSON_BEGIN`

JSON object

`AI_TASK_JSON_END`

Required JSON fields:

- `task_id`
- `base_sha`
- `objective`
- `allowed_paths`
- `forbidden_paths`
- `acceptance_criteria`
- `validation_commands`
- `max_rounds`
- `max_output_tokens`
- `requires_claude`
- `auto_merge`
- `context_files`

The task `base_sha` must equal current main HEAD after DeepSeek WRITE_LOCK acquisition. A mismatch is a stale-write hard block.

## Bounded DeepSeek loop

DeepSeek is allowed at most 4 implementation/review rounds per task. The task should normally use 2 rounds and only use more for justified difficult work.

The worker:

1. reads only declared context files;
2. requests one scoped unified diff;
3. rejects out-of-scope paths and probable secrets;
4. applies the diff only after `git apply --check`;
5. runs declared deterministic validation;
6. if validation fails, feeds bounded failure evidence back to DeepSeek;
7. stops on PASS or `MAX_ROUNDS`.

DeepSeek does not commit, push, merge or deploy itself; GitHub Actions owns those lifecycle operations.

## Codex review loop

The issue-driven workflow opens a PR and posts `@codex review`.

The monitor runs every 15 minutes and checks AI-loop PRs. If Codex produces blocking review comments for the current head, those comments become bounded DeepSeek repair feedback. The repaired branch is pushed and Codex is requested to review the new head again.

Codex no-blocker evidence may advance the task to acceptance/deployment gating, but no status may be invented if the GitHub integration did not actually return evidence.

## Claude escalation

Use `requires_claude=true` when changes materially affect any of:

- MARKET/LIMIT/WATCH/BLOCK decision logic
- current-price geometry / anti-chase
- HTF/M15/M5 entry intelligence
- structural SL / target / RR
- hard-news admission
- quote freshness/admission
- market-specific confirmation
- cross-market ranking
- execution authority or protected state

Claude review is read/review-first. Claude must fresh-read current PR/main and WRITE_LOCK. Claude may propose a repair; DeepSeek remains the default implementer unless task ownership is explicitly transferred.

## WRITE_LOCK

`docs/ai-coengineer/WRITE_LOCK.md` remains mandatory.

- DeepSeek implementation task: `LOCKED=true`, `OWNER=DEEPSEEK`.
- Codex may review while DeepSeek owns the lock but must not modify overlapping source.
- Claude may review while DeepSeek owns the lock but must not modify overlapping source.
- Any writer must re-check current HEAD and lock before source writes.
- Lock is released only after task DONE/BLOCKED or a truthful handoff state where no writer remains active.

## Protected invariants

Never weaken merely to pass a test:

- `TRADING_STATE`
- `v775:books`
- quote freshness
- structural SL
- RR safeguards
- hard-news safeguards
- execution authority
- production credentials/secrets
- Signal-only architecture

Absolute prohibitions:

- no Hyro auto-trade restoration
- no real-capital execution path
- no Futures Signal restoration
- no TK2 restoration
- no Futures substitution for Index Cash
- no Binance20 production activation
- no production Claude/Anthropic API
- no fabricated provider/test/deployment/live evidence

## API/cost guards

Expected secret: `DEEPSEEK_API_KEY`.

Never print or commit the secret.

Each task must bound:

- context file list / context chars
- output tokens per DeepSeek call
- max implementation rounds
- deterministic validation timeout

Do not use DeepSeek to repeatedly reread the full repository when narrow source context is sufficient.

## Status vocabulary

- DESIGNED = architecture/spec only
- STAGED = code/workflow exists but not yet exercised
- RUNNING = real cloud loop evidence exists
- CODEX_REVIEW_REQUIRED = PR waiting for real Codex review
- CLAUDE_REVIEW_REQUIRED = protected task waiting for Claude Max web review
- BLOCKED = loop stopped without acceptance
- DEPLOYED = Cloudflare accepted a real deployment
- LIVE_VERIFIED = required production verification actually passed
- RESOLVED = acceptance criteria plus required live verification passed

## User experience target

The user should normally only need to give Codex a short goal such as `phát triển tư duy tìm entry`.

Codex then fresh-reads GitHub, converts that goal into one bounded task, acquires DeepSeek WRITE_LOCK, creates the issue contract, and lets the GitHub/DeepSeek/Codex loop run until PASS, BLOCKED, or Claude review is genuinely required.
