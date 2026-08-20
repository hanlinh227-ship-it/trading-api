# AI LOOP PROTOCOL — CODEX + CLAUDE CODE + DEEPSEEK

Status: STAGED_FOR_FIRST_REAL_TASK
Architecture: web/cloud-first
Repository: `hanlinh227-ship-it/trading-api`

## Roles

- Codex = CONTROL PLANE: architect, task/spec creator, independent reviewer and final acceptance authority.
- Claude Max / Claude Code / Scheduled Watcher = independent deep optimizer/reviewer for protected Trading logic. Production Anthropic API remains OFF.
- DeepSeek API = PRIMARY AUTOMATED IMPLEMENTER/FIXER in GitHub Actions.
- GitHub = source of truth, task bus, state, WRITE_LOCK, PR/CI evidence and audit trail.
- Cloudflare = production Signal runtime and deployment/live-verification target.

## Review model

Protected Trading tasks use PARALLEL DUAL REVIEW.

DeepSeek implements and validates one PR head. Codex and Claude review the SAME implementation SHA independently. DeepSeek must not repair a `requires_claude=true` task until both required verdicts exist for that exact head.

Review state for a protected task:

- `review_required.codex=true`
- `review_required.claude=true`
- `review_status.codex=PENDING|ACCEPT|REJECT`
- `review_status.claude=PENDING|ACCEPT|REJECT|BLOCKED`
- `review_consensus=WAITING|REPAIR_REQUIRED|ACCEPT|BLOCKED`

Claude Scheduled Watcher is a watchdog/fallback wake mechanism. It is not Anthropic API automation and may introduce schedule latency. Never claim instantaneous or fully autonomous Claude review without real evidence.

## Normal state machine

`USER_PROMPT -> CODEX_DISCOVER -> CODEX_SPEC -> DEEPSEEK_IMPLEMENT -> DEEPSEEK_VALIDATE -> PR -> PARALLEL_REVIEW`

Then:

- required reviewer missing -> `WAITING_FOR_REVIEW`
- either reviewer REJECT -> aggregate both available findings -> `DEEPSEEK_FIX -> VALIDATE -> PARALLEL_REVIEW`
- Claude BLOCKED -> `BLOCKED -> STOP`
- all required reviewers ACCEPT -> `READY_FOR_FINAL_ACCEPT`
- final acceptance -> `MERGE/DEPLOY_GATE -> LIVE_VERIFY -> DONE`
- `MAX_ROUNDS` exhausted -> `BLOCKED -> STOP`

Non-protected tasks may use Codex-only review when `requires_claude=false`.

## Task contract

Codex creates a GitHub Issue titled with `[AI-TASK]` and exactly one machine-readable block between `AI_TASK_JSON_BEGIN` and `AI_TASK_JSON_END`.

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

`base_sha` must equal current main HEAD after DeepSeek WRITE_LOCK acquisition. A mismatch is a stale-write hard block.

## DeepSeek bounded loop

Default max rounds: 2. Hard cap: 4.

The worker reads only declared context, requests a scoped unified diff, rejects out-of-scope/secret-bearing patches, applies only after `git apply --check`, runs deterministic validation, and uses real failure evidence for bounded repair. It must never weaken safeguards to make tests pass.

DeepSeek does not merge or deploy by itself.

## Codex verdict

Workflow requests `@codex review` on each current PR head. Blocking inline findings tied to that head mean REJECT. A real Codex no-blocker signal is required for ACCEPT. Missing evidence remains PENDING.

## Claude verdict envelope

For `requires_claude=true`, Claude reviews the exact current head and posts a PR conversation comment using:

`CLAUDE_REVIEW_BEGIN`

`CLAUDE_REVIEW_HEAD: <sha>`

`CLAUDE_VERDICT: ACCEPT|REJECT|BLOCKED`

`CLAUDE_FINDINGS:`

`<findings or NONE>`

`CLAUDE_REVIEW_END`

A verdict for an older SHA is stale and must not satisfy the gate.

## Review aggregation

DeepSeek repair begins only after all required reviewer verdicts for the current head are available. Codex and Claude findings are combined into one bounded repair prompt so DeepSeek performs one coherent repair round rather than reacting serially to reviewers.

After each repair, prior verdicts are stale. Both required reviewers must review the new head again.

## Protected Trading tasks requiring Claude

Set `requires_claude=true` for material changes to:

- MARKET / LIMIT / WATCH / BLOCK decision logic
- current-price geometry / anti-chase
- HTF / M15 / M5 entry intelligence
- structural SL / target / RR
- hard-news admission
- quote freshness/admission
- market-specific confirmation
- cross-market ranking
- execution authority or protected state

## WRITE_LOCK

`docs/ai-coengineer/WRITE_LOCK.md` is mandatory.

- DeepSeek source implementation: `LOCKED=true`, `OWNER=DEEPSEEK`.
- Codex and Claude may review while DeepSeek owns the lock but must not modify overlapping source.
- Any writer must stale-check HEAD and lock immediately before writing.
- GitHub orchestration metadata may be updated only within the declared task protocol and must not bypass source ownership.

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
- SIGNAL-ONLY architecture

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

Expected GitHub secret: `DEEPSEEK_API_KEY`.

Each task bounds context, output tokens, implementation rounds and validation timeout. Do not repeatedly reread the full repository when narrow context is sufficient.

## Status vocabulary

- STAGED = workflow exists but has not completed a real end-to-end task
- RUNNING = real cloud loop evidence exists
- PARALLEL_DUAL_REVIEW_REQUIRED = protected PR requires both reviewers
- WAITING_FOR_REVIEW = one or more required verdicts missing
- REPAIR_REQUIRED = required review consensus found blocking issues
- READY_FOR_FINAL_ACCEPT = all required reviewers ACCEPT
- BLOCKED = stopped without acceptance
- DEPLOYED = Cloudflare accepted a real deployment
- LIVE_VERIFIED = production verification actually passed
- RESOLVED = acceptance criteria and required live verification passed

## User experience target

The user normally gives Codex/ChatGPT one short goal. Codex fresh-reads GitHub, creates one bounded task, assigns DeepSeek implementation, requests independent Codex + Claude review where protected, aggregates review evidence, and stops only at ACCEPT, BLOCKED, or the task round cap.
