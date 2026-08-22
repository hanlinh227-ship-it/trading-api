# AUTO-INTAKE V1 — GitHub Issue -> Pipeline Task

Status: IMPLEMENTED (STAGED_FOR_FIRST_REAL_TASK)
Source: `scripts/ai/auto_intake.py`
Self-tests: `scripts/ai/tests/test_auto_intake.py`

## Purpose

AUTO-INTAKE V1 safely converts GitHub issues explicitly marked as AI-loop tasks into canonical bounded pipeline tasks for the DeepSeek implementer. It is the entry point of the AI loop and enforces fail-closed validation before any implementation work begins.

It never merges, pushes, deploys, or executes issue-supplied shell.

## Discovery

- Only issues whose title contains `[AI-TASK]` are considered.
- Pull requests returned by the issues endpoint are filtered out.
- Batch discovery is **paginated** (`per_page=100`, up to `MAX_ISSUE_PAGES`). If the cap is reached the run fails closed rather than silently truncating.
- `--issue N` performs a **direct** `GET /repos/{repo}/issues/N` fetch. It never filters a listing page, so an issue beyond the first page is still reachable.
- The issue body must contain exactly one machine-readable block between `AI_TASK_JSON_BEGIN` and `AI_TASK_JSON_END`. Zero or multiple blocks are rejected.

## Validation (fail-closed)

All per-issue rejections raise `TaskError` and are contained to that issue.

- All required fields from the AI LOOP PROTOCOL task contract must be present.
- `allowed_paths` must be a non-empty list of strings, and **every entry** is checked against the hard-forbidden and broad-scope rules:
  - hard-forbidden: `.env`, `cloudflare-worker/.dev.vars`, `.git`, `.git/**`, anything under `.git/`;
  - repo-wide / broad: `.`, `./`, `*`, `**`, `./**`, `**/*`, `*/**`, `/`, empty, or any first path segment containing a glob character;
  - absolute paths (`/...`, `~...`) and `..` traversal segments;
  - for a `dir/**` scope the concrete prefix is checked with the same rules, so `.git/**` cannot slip past.
- `forbidden_paths` must be a list of non-empty strings.
- `acceptance_criteria` must be a non-empty list.
- `validation_commands` must satisfy the strict allowlist grammar below.
- `context_files` must be a list of non-empty strings.
- `requires_claude` and `auto_merge` must be real booleans; `auto_merge` must be `false`.
- `base_sha` must be a 40-character lowercase hex SHA **and must resolve** to a real commit (`git cat-file -e <sha>^{commit}` locally, falling back to `GET /repos/{repo}/commits/{sha}`). An unresolvable base SHA is a stale-base hard block.
- `task_id` must match `[A-Za-z0-9._-]{3,64}`.
- `max_rounds` and `max_output_tokens` are **type-checked before any bounds logic**: `bool`, `str`, `float`, `list`, `dict` and `None` are rejected outright. Only real integers are then clamped (`max_rounds` 1..4, `max_output_tokens` 512..8000).
- The entire task JSON is scanned for secret patterns and rejected if any are found.

## validation_commands grammar (strict allowlist)

Issue text is never treated as arbitrary shell. A command is accepted only if **all** of the following hold:

- length <= 500 and no shell metacharacter from ``; | & ` $ < > ( ) { } ! * ? [ ] ~ # \ " '`` , newline or tab — so no pipes, chaining, redirects, globbing, command substitution or subshells;
- it matches the bounded token grammar `^[A-Za-z0-9_./-]+(\s+[A-Za-z0-9_./=-]+)*$`;
- the head token is on the allowlist (`python`, `python3`, `pytest`, `ruff`, `flake8`, `mypy`, `git`, `echo`, `true`, `false`);
- `git` is restricted to read-only subcommands (`diff`, `status`, `log`, `show`, `rev-parse`, `ls-files`, `check-ignore`, `check-attr`); every git write subcommand is rejected;
- `python`/`python3` must run either an in-repo `*.py` file or `-m <module>` where the module is on `SAFE_PYTHON_MODULES`; `-c` is rejected;
- no token may be a shell keyword, shell interpreter, network client (`curl`, `wget`, `nc`, `ssh`, `scp`, `rsync`, ...), deploy tool (`wrangler`, `kubectl`, `terraform`, `docker`, `aws`, ...), package manager / arbitrary executor (`pip`, `npm`, `make`, `eval`, `exec`, `source`, `xargs`, `find`, `node`, ...), or a forbidden flag (`-c`, `-e`, `--eval`, `--exec`, `--command`, `-i`).

Anything not explicitly permitted is rejected.

## Durable idempotency

GitHub is the **source of truth**; local files are only a cache.

### Durable ledger (authoritative, O(1), history-independent)

Each processed `task_id` gets a permanent repository **label** — `ai-intake-done:<task_id>`, or `ai-intake-done:<truncated>~<sha256[:16]>` when the readable form would exceed GitHub's 50-character label limit. `receipt_label()` is a pure function, so the same `task_id` always maps to the same key on every runner, forever.

The duplicate check is a single `GET /repos/{repo}/labels/{name}`:

- `200` -> already processed -> `DUPLICATE_SKIPPED`
- `404` -> not processed -> proceed
- anything else (including a transport failure) -> **INDETERMINATE -> fail closed**, the issue is rejected with `TaskError` rather than risking a re-run

This is bounded to one request, deterministic, and — critically — **does not scan history at all**, so a previously processed task can never become eligible again because its receipt aged out of a window.

> Superseded design: an earlier revision scanned `GET /repos/{repo}/issues/comments` for up to 20 pages (2000 newest comments repo-wide). That was a real defect — once enough history accumulated, an old receipt fell outside the window and, on a fresh checkout with no local state, the task would have been reprocessed. The repo-wide scan has been removed entirely.

### Secondary audit checks

- `issue_receipt_task_ids(n)` reads only **that one issue's** comments (fully paginated, bounded by the issue itself, never repo-wide) for `AUTO_INTAKE_RECEIPT: <task_id>` markers.
- `.ai-intake/<task_id>.json` remains a local cache.
- An in-batch `seen` memo blocks a repeated `task_id` within a single run without extra API calls.

None of these is ever the sole mechanism; the label ledger is authoritative.

### Audit trail

A human-readable `AUTO_INTAKE_RECEIPT` comment is still posted on the issue with the task_id, issue number, base SHA and task file path, and the ledger label is also applied to the issue so the state is visible.

## Write-before-mark ordering

For each accepted task the order is strictly:

1. `write_task_file()` — the task file must be written and verified on disk;
2. `create_receipt_label()` — durable GitHub ledger entry (must succeed; a failed creation is re-probed and raises if the entry is genuinely absent);
3. `post_receipt()` — human-readable audit comment;
4. `mark_processed()` — local cache;
5. `READY` status.

If step 1 or step 2 fails, the later steps never run, the in-batch memo is not updated, and the task remains eligible for a later retry.

## Per-issue failure isolation

`run_intake()` processes each issue inside its own boundary. A malformed, unsafe or otherwise failing issue is recorded in `failures`, labelled `FAILED` on GitHub, and processing continues with the remaining issues. The process exits non-zero when any issue failed, so a bad task is still surfaced loudly without discarding valid work.

## GitHub status reporting (singular + durable)

Status is reported as an issue comment plus exactly one `ai-status:*` label:

- `RECEIVED` — task accepted and validated
- `READY` — task file written for the implementer
- `FAILED` — validation or processing failed
- `DUPLICATE_SKIPPED` — task already processed

`set_status_label()` reads the issue's current labels, deletes every other `ai-status:*` label, and adds the target only if it is not already present. Non-status labels are never touched. An unknown status is a hard block.

## Output

Validated tasks are written to `.ai-intake/tasks/<task_id>.json` (including `source_issue`) for the DeepSeek implementer to consume.

## Deterministic self-tests

`scripts/ai/tests/test_auto_intake.py` is hermetic — no network, no GitHub calls, no writes outside a temporary root. It runs under both:

```
python3 -m pytest scripts/ai/tests/test_auto_intake.py -v
python3 -m unittest discover -s scripts/ai/tests -p 'test_*.py'
```

Covered safety properties:

- hard forbidden scope (including `.git`, `.git/**`, `./.env`, traversal, absolute paths)
- broad scope rejection (`.`, `./`, `*`, `**`, `./**`, `**/*`, `*/**`, glob-rooted scopes)
- validation command allowlist (unsafe rejected, legitimate accepted)
- malformed issue isolation (batch continues, failures reported)
- direct issue fetch (`--issue N` hits `/issues/N`, rejects PRs and unmarked issues)
- pagination (issue discovery cap fails closed; receipt scan is bounded to a single issue; the repo-wide history scan is asserted absent)
- durable idempotency (O(1) label ledger; blocked with no local state, across a simulated fresh checkout, and with 10,000 comments of accumulated history; indeterminate lookup fails closed; ledger-write failure prevents marking)
- singular status transitions (previous `ai-status:*` labels removed)
- numeric type fail-closed (`bool`/`str`/`float`/`list`/`None` rejected before clamping)
- base_sha resolution failure
- write-before-mark ordering (write -> ledger -> receipt -> mark)
- no merge / deploy / PR endpoint is ever called
- downstream contract with `deepseek_implementer.DANGEROUS_VALIDATION` (no gap, no conflict, no weakening)

## Downstream contract: `deepseek_implementer.DANGEROUS_VALIDATION`

`scripts/ai/deepseek_implementer.py` keeps its own `DANGEROUS_VALIDATION` denylist regex and executes validation commands via `bash -lc`. It is **left unchanged**, and is classified as an **independent downstream defence-in-depth gate**, not a conflict, for three reasons:

1. **No gap.** Every command that denylist names (`rm -rf`, `git reset --hard`, `git clean`, `git push`, `git commit`, `wrangler deploy`, `curl -X POST|PUT|PATCH|DELETE`) is already rejected by AUTO-INTAKE's allowlist. AUTO-INTAKE is strictly the stricter layer.
2. **No conflict.** The denylist never matches anything AUTO-INTAKE accepts, so an accepted task cannot hard-block downstream and stall the loop.
3. **It guards a different entry point.** `deepseek_implementer.py` accepts an arbitrary `task_file` argument. A task file that never passed through AUTO-INTAKE — hand-authored, or produced by some future path — is gated *only* by that denylist. Removing or replacing it would weaken protection for exactly the case it exists to cover.

Scope note: `WRITE_LOCK.md` currently has `LOCKED: true`, `OWNER: DEEPSEEK` covering AI orchestration infrastructure. `deepseek_implementer.py` is DeepSeek's implementation surface; editing it here would be scope expansion under an active foreign lock. AUTO-INTAKE's own gate is tightened instead.

This contract is enforced by tests, not just prose: `TestDownstreamValidationContract` proves AUTO-INTAKE blocks the entire downstream denylist, that the denylist never rejects an intake-accepted command, that arbitrary shell slipping past the denylist is stopped upstream, that a written task file contains no shell metacharacters, and that the downstream pattern itself has not been weakened.

## Safety invariants

- No automatic merge or deployment.
- No trading execution or risk logic modification.
- No Cloudflare worker modification.
- No secret exposure.
- No arbitrary shell execution from issue text.
- Stale-base, WRITE_LOCK, write-lease and SHA-bound reviewer gates remain enforced downstream.
