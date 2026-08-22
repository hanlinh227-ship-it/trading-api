# AI LOOP CONTRACT — V2

Repository: `hanlinh227-ship-it/trading-api`
Status: ACTIVE
Version: AI_LOOP_V2

This contract defines the canonical bounded three-AI engineering loop. It is fail-closed, SHA-bound, single-writer, and event-driven.

## 1. Canonical roles

### DEEPSEEK — PRIMARY_IMPLEMENTER / SOLE SOURCE WRITER

DeepSeek runs through the bounded GitHub Actions implementer (`scripts/ai/deepseek_implementer.py`).

Responsibilities:
- fresh-read the task contract and declared context files;
- edit only paths allowed by the task and current WRITE_LOCK;
- run bounded deterministic validation;
- produce the smallest coherent implementation diff;
- never deploy production and never merge.

DeepSeek may consume aggregated findings from Codex + Claude on a later repair round. DeepSeek must never provide an acceptance review for code it authored.

### CODEX — INDEPENDENT REVIEWER

Codex reviews the exact current implementation SHA through the GitHub Codex integration.

Responsibilities:
- compare intent, acceptance criteria, diff and validation evidence;
- report concrete blockers/non-blockers;
- never edit source while DeepSeek owns WRITE_LOCK;
- re-review only when the implementation SHA changes.

### CLAUDE — INDEPENDENT REVIEWER / ADVISER

Claude reviews the exact same implementation SHA independently through the configured Claude watcher/bridge.

Required machine-readable envelope:

```
CLAUDE_REVIEW_BEGIN
CLAUDE_REVIEW_HEAD: <40-hex sha>
CLAUDE_VERDICT: ACCEPT|REJECT|BLOCKED
CLAUDE_FINDINGS:
<concise findings or NONE>
CLAUDE_REVIEW_END
```

A missing, stale or malformed Claude verdict is not acceptance.

### CHATGPT — ORCHESTRATOR / CONTROL PLANE

ChatGPT may create bounded task contracts, maintain routing/lock metadata when explicitly authorized by the user, inspect GitHub evidence, aggregate reviewer findings, and report status. ChatGPT is not counted as one of the two independent implementation reviewers.

### GITHUB — STATE BUS

GitHub `main`, open task issues, implementation PRs, exact head SHA, checks and SHA-bound reviewer evidence are the source of shared runtime truth.

## 2. Single-writer rule

Exactly one actor may modify source for an active scope: the WRITE_LOCK owner.

Active writer entry points must all share:

```
concurrency.group = trading-ai-closed-loop
cancel-in-progress = false
```

A second open implementation PR for the same `task_id` is forbidden. Manual fallback workflows must reject duplicates rather than create parallel branches.

## 3. Canonical entry points

### Automatic

`.github/workflows/ai-loop.yml`

Trigger: new issue whose title starts with `[AI-TASK]`.

### Manual fallback

`.github/workflows/ai-loop-wake.yml`

Trigger: `workflow_dispatch` only with an explicit open issue number. It must not use metadata pushes to `main`, because those commits move `base_sha` and can race the canonical issue event.

### Legacy manual DeepSeek reviewer

`.github/workflows/ai-loop-deepseek-review.yml` is non-gating, manual-only, and must not automatically review DeepSeek-authored implementation PRs.

### Manual DeepSeek implementation

`.github/workflows/ai-task.yml` is a fallback writer entry point and therefore shares the global writer concurrency group and duplicate-PR protection.

## 4. Task contract

Every implementation task must contain exactly one JSON object between:

```
AI_TASK_JSON_BEGIN
{ ... }
AI_TASK_JSON_END
```

Minimum fields:
- `task_id`
- `base_sha`
- `objective`
- `allowed_paths`
- `forbidden_paths`
- `acceptance_criteria`

Recommended bounded fields:
- `context_files`
- `validation_commands`
- `max_rounds` (hard bounded)
- `max_output_tokens`
- `context_max_chars`
- `requires_claude: true`

A stale `base_sha` fails closed. The controller must not silently rewrite a stale task in a loop or create endless replacement issues.

## 5. Review and repair state machine

```
IDLE
  -> TASK_ACCEPTED
  -> DEEPSEEK_IMPLEMENTING
  -> VALIDATING
  -> AWAITING_CODEX_AND_CLAUDE
      -> READY_FOR_FINAL_ACCEPT      (both accept same SHA)
      -> REPAIR_REQUIRED             (one or both reject)
      -> BLOCKED                     (required reviewer unavailable/blocked)
REPAIR_REQUIRED
  -> DEEPSEEK_REPAIRING
  -> VALIDATING
  -> AWAITING_CODEX_AND_CLAUDE
```

The loop stops at `READY_FOR_FINAL_ACCEPT`, `BLOCKED`, or `MAX_ROUNDS_REACHED`.

Reviewer findings from Codex and Claude are aggregated into one bounded repair prompt. The system must not perform duplicate serial repairs for the same unchanged SHA.

## 6. Final acceptance gate

Final acceptance requires all of the following for the exact same current implementation SHA:

1. DeepSeek implementation exists and is inside task scope.
2. Deterministic validation commands pass.
3. Required GitHub checks for that head pass.
4. Codex returns no blocking findings for that head.
5. Claude returns `ACCEPT` for that head.
6. No reviewer evidence is stale.
7. No hard Trading safety invariant is weakened.

Missing Codex or Claude evidence is `PENDING/BLOCKED`, never implicit acceptance.

## 7. Reviewer caching and token discipline

- Review evidence is cached by implementation SHA.
- Do not re-call Codex or Claude when the SHA is unchanged and a valid verdict already exists.
- Give reviewers the task contract, relevant diff, exact SHA, validation evidence and only necessary context.
- Do not make every model repeatedly read the full repository.
- Aggregate reviewer findings before calling DeepSeek for repair.
- External calls are timeout-bounded and round-bounded.

## 8. Failure visibility

No AI workflow may fail silently.

Before an implementation PR exists, failure reporting should identify at least one classification such as:
- `STALE_BASE_SHA`
- `WRITE_LOCK_MISMATCH`
- `MISSING_DEEPSEEK_SECRET`
- `IMPLEMENTER_VALIDATION_FAILED`
- `DUPLICATE_IMPLEMENTATION_PR`

After a PR exists, reviewer state must expose CodeX and Claude separately.

## 9. Trading safety invariants

Never weaken these merely to increase signal count:
- SIGNAL_ONLY architecture;
- quote freshness;
- structural SL;
- RR / forward-liquidity quality;
- anti-chase / market-readiness geometry;
- hard-news safeguards;
- exact market identity;
- duplicate OPEN suppression and lifecycle safety;
- `TRADING_STATE` preservation;
- V73 historical-prior immutability;
- no restoration of Hyro/TK2/Futures/Binance real-capital execution authority;
- no secret/token/private-key disclosure.

## 10. Workflow self-modification rule

AI-authored changes to `.github/workflows/**` are infrastructure-sensitive. They may be proposed by the writer, but they must not self-certify merely because the modified workflow says it passed. Acceptance must rely on independent GitHub diff review plus a trusted baseline/human-authorized orchestrator decision.
