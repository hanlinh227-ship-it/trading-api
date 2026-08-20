# AI LOOP CONTRACT — V1

Repository: `hanlinh227-ship-it/trading-api`
Status: ACTIVE
Version: AI_LOOP_V1
Owner of this document: CLAUDE_LOCAL under lock `AI-LOOP-INFRA-V1`

This contract defines a **bounded** multi-actor engineering loop. One human objective goes
in; the loop iterates until `READY_TO_MERGE`, `BLOCKED`, or `MAX_ROUNDS_REACHED`, and then
stops. It never merges, never deploys, and never runs unbounded.

---

## 1. Actors

### CLAUDE_LOCAL — `PRIMARY_IMPLEMENTER`

Runs locally through Claude Code (`claude -p`) on the user's subscription auth. Never uses
Anthropic API billing.

Responsibilities:
- fresh-read the current task and the exact current branch/PR head before acting;
- apply the requested fix, and **only** the requested fix;
- execute the deterministic test suite;
- produce structured completion evidence;
- respect `WRITE_LOCK.md` at all times.

Hard limits:
- never merges a PR;
- never deploys to production;
- never edits outside the acquired lock scope;
- never weakens a Trading safety invariant (see section 6);
- never runs with `--dangerously-skip-permissions`;
- does not own git write operations — the controller does (see section 5).

### DEEPSEEK — `ADVERSARIAL_REVIEWER`

Runs in GitHub Actions via `scripts/ai/deepseek_reviewer.py`.

Responsibilities:
- inspect the exact PR diff for the exact head SHA;
- inspect test/check evidence attached to that head;
- hunt for logic defects, regressions and safety violations;
- return a machine-readable `ACCEPT` / `REJECT` / `BLOCKED` verdict;
- post or update exactly one PR comment.

Hard limits:
- never authorizes deployment;
- never modifies source;
- never merges;
- its verdict is bound to a specific `HEAD_SHA` and is void for any other head.

### CODEX — `INDEPENDENT_REVIEWER`

The GitHub Codex integration already active in this repository.

Responsibilities:
- review the exact current PR head as an independent reviewer;
- assess intent versus diff, correctness, regression risk, test evidence and the task's
  acceptance criteria;
- return findings on GitHub.

Hard limits:
- must re-review after **every** materially changed PR head;
- a Codex review for an older SHA is stale and must not be counted.

### GITHUB — `STATE_BUS`

The single source of shared truth. Branch state, PR head SHA, check runs, DeepSeek review
comments and Codex reviews are the runtime state. The loop reads its state from GitHub on
every round, so **no browser conversation needs to stay open** for the loop to continue.

### CLOUDFLARE — `VALIDATION_TARGET`

Used for validation only (`wrangler deploy --dry-run`, canonical lock manifest). Production
deploy is gated behind repository variable `ENABLE_CLOUDFLARE_AUTO_DEPLOY == 'true'`, which
is deliberately unset. The loop never deploys.

### CHATGPT — `ORCHESTRATOR / USER-FACING CONTROL PLANE`

Sets objectives, arbitrates design decisions, records `DECISIONS.md`, and performs the
final human-authorized merge. ChatGPT is **not** required to be online for a loop run.

---

## 2. Loop state machine

States:

```
IDLE
TASK_ACCEPTED
IMPLEMENTING
TESTING
AWAITING_REVIEWS
FIX_REQUIRED
READY_TO_MERGE
BLOCKED
MAX_ROUNDS_REACHED
```

Transitions:

```
IDLE                -> TASK_ACCEPTED       valid objective accepted
TASK_ACCEPTED       -> IMPLEMENTING        controller dispatches CLAUDE_LOCAL
IMPLEMENTING        -> TESTING             implementation round returned
TESTING             -> FIX_REQUIRED        deterministic tests FAILED
TESTING             -> AWAITING_REVIEWS    tests PASSED, branch pushed, PR updated
AWAITING_REVIEWS    -> FIX_REQUIRED        DeepSeek REJECT or Codex blocking findings
AWAITING_REVIEWS    -> READY_TO_MERGE      see gate below
FIX_REQUIRED        -> IMPLEMENTING        round = round + 1, if round <= max_rounds
FIX_REQUIRED        -> MAX_ROUNDS_REACHED  round > max_rounds
any                 -> BLOCKED             hard blocker encountered
```

Terminal states: `READY_TO_MERGE`, `BLOCKED`, `MAX_ROUNDS_REACHED`. The loop STOPS at each.

### READY_TO_MERGE gate

`READY_TO_MERGE` requires **all** of the following, simultaneously, for the **same**
`head_sha`:

1. deterministic tests PASS locally;
2. required GitHub checks PASS for that head (see "Which checks gate" below);
3. `deepseek_verdict == ACCEPT` **and** `deepseek_review_sha == head_sha`;
4. `codex_verdict == ACCEPT` (or no blocking findings) **and** `codex_review_sha == head_sha`.

Any stale review SHA fails the gate and forces another round. A single `REJECT` from either
reviewer fails the gate.

`READY_TO_MERGE` means "a human may now merge". **The loop never merges.**

### Which checks gate

Only the checks named in the controller's `REQUIRED_CHECKS` list gate `READY_TO_MERGE`.
Each must be **present** for the head and its **latest attempt** must have concluded
`success`; absence, `neutral`, `skipped`, `stale` or a failure all fail the gate.

Attempt identity is `(check name, check suite)`, because two different workflows can
publish check runs under the same name — this repository has two named `validate`. Only
the newest attempt within each identity is authoritative, so a superseded or cancelled
earlier attempt neither fails the gate nor masks a later failure.

Checks **not** in the required list are reported but do not gate. Blocking on them would
let an unrelated provider-side check veto every PR in the repository indefinitely — the
Cloudflare Workers Build failure tracked in issue #62 is exactly that case. Their failures
are surfaced in the run summary so they stay visible rather than silently ignored.

### Bounds

- `MAX_ROUNDS = 5` (hard ceiling; the controller clamps any higher request down to 5).
- Every external call is timeout-bounded with at most 3 attempts and bounded exponential
  backoff.
- There is no unbounded loop anywhere in the implementation.

---

## 3. Hard blockers

The loop transitions to `BLOCKED` and stops immediately on any of:

- `WRITE_LOCK.md` is held by another owner, or the requested scope is outside the lock;
- the implementation branch resolves to `main`;
- GitHub authentication is missing or invalid;
- `DEEPSEEK_API_KEY` is absent, unauthorized, or out of credit (classified, not retried
  forever);
- a Trading safety invariant would have to be weakened to proceed;
- the objective is malformed or empty;
- a required tool (`git`, `gh`, `claude`, `node`) is missing.

---

## 4. Machine-readable review protocol

DeepSeek must emit exactly one block. The controller parses only this block:

```
DEEPSEEK_REVIEW_BEGIN
HEAD_SHA=<40-hex sha>
VERDICT=ACCEPT|REJECT|BLOCKED
BLOCKERS=<one per line, or NONE>
NON_BLOCKING=<one per line, or NONE>
DEEPSEEK_REVIEW_END
```

Rules:
- `HEAD_SHA` MUST equal the reviewed PR head. A mismatch makes the review stale and void.
- `VERDICT=ACCEPT` with a non-empty `BLOCKERS` list is contradictory and is downgraded to
  `REJECT` by the controller.
- Free-form prose outside the block is ignored by the controller. No free-form patches are
  accepted from DeepSeek in V1 — **DeepSeek is a reviewer, not an implementer.**

Codex is requested with an explicit comment naming the exact head, and its review is only
counted when GitHub reports `commit_id == head_sha`.

---

## 5. Permission and authority split

| Capability | CLAUDE_LOCAL | Controller | DEEPSEEK | CODEX |
|---|---|---|---|---|
| Read repo | yes | yes | yes (diff) | yes |
| Edit files in repo | yes (in scope) | no | no | no |
| Run tests | yes | yes | no | no |
| `git commit` | no | yes | no | no |
| `git push` (feature branch) | no | yes | no | no |
| `git push` to `main` | **never** | **never** | no | no |
| force push | **never** | **never** | no | no |
| Create/update PR | no | yes | no | no |
| Comment on PR | no | yes | yes | yes |
| Merge PR | **never** | **never** | **never** | **never** |
| Deploy Cloudflare production | **never** | **never** | **never** | **never** |
| Mutate GitHub secrets | **never** | **never** | **never** | **never** |
| Read secret values | **never** | **never** | key via env only | no |

The controller — not Claude — owns branch creation, commit, push and PR creation. This
keeps Claude's granted tool surface narrow: Claude gets file edits, read-only git
inspection, and the deterministic test commands.

`--dangerously-skip-permissions` is forbidden. The controller invokes Claude with an
explicit narrow `--allowedTools` list.

---

## 6. Trading safety invariants (never weakened by the loop)

- SIGNAL-ONLY architecture; `executionAuthority = SIGNAL_ONLY` / `NONE`.
- Quote freshness (stale or `fresh=false` quotes may never create a MARKET signal).
- Structural SL.
- RR quality gates.
- Anti-chase geometry.
- Hard-news safeguards.
- Exact market identity.
- `TRADING_STATE` and `v775:books` are never reset or deleted.
- V73 is a frozen historical prior.
- No real-capital execution; no Hyro auto-trade, TK2, Futures Signal or Binance20
  execution restoration.
- Production Anthropic API stays paused.
- No secret is ever printed or committed.

Any round that would violate one of these is a hard blocker, not a review finding.

---

## 7. Runtime state

The JSON contract lives in `docs/ai-coengineer/AI_LOOP_STATE.schema.json`. It is a
**contract only**. Live state is NOT continuously committed to `main`; it lives in the
GitHub PR (head SHA, checks, review comments) and in a local run file under the run
directory. This keeps `main` free of loop churn.

---

## 8. Entry point

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\ai\ai-loop.ps1 -Task "<objective>" -MaxRounds 5
```

Files:

| File | Role |
|---|---|
| `scripts/ai/ai-loop.ps1` | Windows loop controller (owns git writes, orchestration, stop conditions) |
| `scripts/ai/claude_loop_prompt.md` | The invariant prompt template given to `claude -p` |
| `scripts/ai/deepseek_reviewer.py` | Adversarial reviewer client and PR commenter |
| `.github/workflows/ai-loop-deepseek-review.yml` | Runs the DeepSeek reviewer on PR events |
| `scripts/ai/ai-loop-selftest.mjs` | Deterministic validation of the loop infrastructure |
| `docs/ai-coengineer/AI_LOOP_STATE.schema.json` | Runtime state contract |
