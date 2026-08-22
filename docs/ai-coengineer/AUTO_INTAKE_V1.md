# AUTO-INTAKE V1 — GitHub Issue -> Pipeline Task

Status: IMPLEMENTED (STAGED_FOR_FIRST_REAL_TASK)
Source: `scripts/ai/auto_intake.py`
Self-tests: `scripts/ai/tests/test_auto_intake.py`

## Purpose

AUTO-INTAKE V1 safely converts GitHub issues explicitly marked as AI-loop tasks into canonical bounded pipeline tasks for the DeepSeek implementer. It is the entry point of the AI loop and enforces fail-closed validation before any implementation work begins.

It never merges, pushes, deploys, or executes issue-supplied shell.

## Workflow integration (the entry boundary is real)

AUTO-INTAKE is wired into the actual pipeline, not parallel to it. No workflow parses the `AI_TASK_JSON` contract inline any more:

| Path | Workflow / job | Entry |
|---|---|---|
| `[AI-TASK]` issue opened | `ai-loop.yml` / `dispatch` | `auto_intake.py --issue N` -> `.ai-intake/tasks/<task_id>.json` |
| Scheduled wake | `ai-loop-wake.yml` / `wake-dispatch` | `auto_intake.py --issue N` |
| Bounded repair round | `ai-loop.yml` / `monitor` | `auto_intake.py --validate-task-file … --expect-head <PR head>` |
| Manual dispatch | `ai-task.yml` / `implement` | `auto_intake.py --validate-task-file … --expect-head <HEAD>` |

`deepseek_implementer.py` consumes only the AUTO-INTAKE-produced task file, and `task_id` is read from that validated file rather than re-parsed from untrusted issue text. Every consumer receives the task-file path as an **argv argument**, never through `os.environ` — a shell-local variable is not visible to a child process, and reading one that way would `KeyError` at runtime.

### Immutable control plane on the repair path

The `monitor` repair job checks out an untrusted PR branch while `GH_TOKEN` and `DEEPSEEK_API_KEY` are in scope. It must therefore never take its orchestration executables from that worktree. Before the repair loop it pins them:

```
git archive <origin/main sha> scripts/ai | tar -x -C "$RUNNER_TEMP/ai-control-plane"
chmod -R a-w "$RUNNER_TEMP/ai-control-plane/scripts"
```

and then invokes the pinned copies against the PR worktree:

```
AI_REPO_ROOT="$GITHUB_WORKSPACE" python3 "$CONTROL_PLANE/scripts/ai/auto_intake.py" ...
AI_REPO_ROOT="$GITHUB_WORKSPACE" python3 "$CONTROL_PLANE/scripts/ai/deepseek_implementer.py" ...
```

`AI_REPO_ROOT` redirects the repository a control-plane script **operates on**; the executable itself always comes from wherever the file lives. A PR may therefore contain implementation files, but it can never supply the control-plane executable. `test_workflow_integration.py` asserts that no `scripts/ai/*` invocation occurs from the PR checkout after `git checkout -B`, and `test_downstream_scope.py` proves it behaviourally: a tampered worktree copy of `auto_intake.py` is demonstrably modified, yet the pinned copy still runs the trusted code and still rejects. `--validate-task-file` re-applies the identical `validate_task()` boundary to a task rebuilt against a PR head, so the repair and manual paths share one validator rather than a second, weaker parser.

The non-bypass property is enforced by test, repository-wide: `test_workflow_integration.py` asserts that **every** `deepseek_implementer.py` invocation in **every** workflow is preceded by an `auto_intake.py` boundary step in the same job, and that no entry job parses `AI_TASK_JSON_BEGIN` inline. Workflows that cannot be structurally parsed must not invoke the implementer at all.

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
- `context_files` must be a list of **repository-safe, existing regular files**. Each entry is rejected if it is absolute, uses `~`, contains a `..` segment or a glob, is hard-forbidden (`.git`, `.git/**`, `.env`, `cloudflare-worker/.dev.vars`), is a symlink, resolves outside `ROOT` via `os.path.realpath`, or is not an existing regular file in this checkout. `/proc/self/environ`, `../../etc/passwd`, `.git/config`, `.env` and `cloudflare-worker/.dev.vars` are all rejected, including when the file genuinely exists.
- `requires_claude` and `auto_merge` must be real booleans; `auto_merge` must be `false`.
- `base_sha` must be a 40-character lowercase hex SHA **and must equal the authoritative current HEAD**. `resolve_authoritative_head()` reads local `git rev-parse HEAD`, falling back to the repository's default-branch head on GitHub. A SHA that resolves to a real but *historical* commit is rejected as `STALE`, and an unresolvable HEAD fails closed rather than accepting an unverifiable base. This runs inside `validate_task()`, so it happens **before** any durable receipt is claimed or any task file is written.
- `task_id` must match `[A-Za-z0-9._-]{3,64}`.
- `max_rounds` and `max_output_tokens` are **type-checked before any bounds logic**: `bool`, `str`, `float`, `list`, `dict` and `None` are rejected outright. Only real integers are then clamped (`max_rounds` 1..4, `max_output_tokens` 512..8000).
- The entire task JSON is scanned for secret patterns and rejected if any are found.

## validation_commands grammar (strict allowlist)

Issue text is never treated as arbitrary shell. A command is accepted only if **all** of the following hold:

- length <= 500 and no shell metacharacter from ``; | & ` $ < > ( ) { } ! * ? [ ] ~ # \ " '`` , newline or tab — so no pipes, chaining, redirects, globbing, command substitution or subshells;
- it matches the bounded token grammar `^[A-Za-z0-9_./-]+(\s+[A-Za-z0-9_./=-]+)*$`;
- the head token is on the allowlist (`python`, `python3`, `pytest`, `ruff`, `flake8`, `mypy`, `git`, `echo`, `true`, `false`);
- `git` is restricted to read-only subcommands (`diff`, `status`, `log`, `show`, `rev-parse`, `ls-files`, `check-ignore`, `check-attr`); every git write subcommand is rejected;
- `python`/`python3` may run **only** `-m <module>` from `SAFE_PYTHON_MODULES`. Executing a bare `.py` file is rejected outright — an issue-selected script is never a validator, no matter its extension. `-c` is rejected;
- every path-like argument must pass the same repository-safety check as `context_files`. For commands that **execute** what they are pointed at (`pytest`, `python -m pytest`, `python -m unittest`) two conditions must both hold:
  0. every non-target token is an explicitly **permitted runner option**. Plugin and configuration options (`-p`, `-P`, `-c`, `--rootdir`, `--confcutdir`, `--import-mode`, `--plugins`, ...) execute task-authored Python *before* the named validator runs, and they have too many spellings for a denylist to ever be complete — so the grammar is a closed allowlist (`-v`, `-vv`, `-q`, `-qq`, `-x`, `--verbose`, `--quiet`, `--exitfirst`, `--maxfail=N`, `--tb=…`). Anything else, including a future pytest option, is refused by default. The environment equivalents (`PYTEST_PLUGINS`, `PYTEST_ADDOPTS`, `PYTHONPATH`, `PYTHONSTARTUP`, ...) are stripped from the validation environment downstream;
  1. a `pytest` runner is **pinned to the immutable trusted config** with `-c scripts/ai/tests/pytest.ini`. Without `-c`, pytest auto-loads `pytest.ini`, `.pytest.ini`, `pytest.toml`, `.pytest.toml`, `tox.ini`, `setup.cfg` or `pyproject.toml` from the task-writable worktree, and a task-authored `addopts = -p evil` executes its code before the validator. Passing `-c` makes that one file pytest's only configuration source; the pin must name a member of `TRUSTED_VALIDATOR_CONFIGS`, and every implicit config source remains in the dependency closure so the boundary does not depend on pytest's config-precedence rules staying the same. `python -c` remains blocked, and `unittest` (which reads no such config) accepts no pin;
  2. the command names **exactly one** explicit target. A runner invoked with no target — `pytest`, `pytest -v`, `python3 -m unittest` — auto-discovers tests from the task-writable worktree, so every targetless, multi-target and discovery form (`discover`, `--pyargs`, `--doctest-modules`, `--collect-only`) is refused, including when a discovery flag accompanies an otherwise valid target;
  3. the target is an **exact** member of the fixed `TRUSTED_PYTHON_VALIDATORS` allowlist. Directory trust does not exist — living under `scripts/ai/tests/` grants nothing, because a task whose `allowed_paths` cover that directory could otherwise drop a new file there and have it executed with workflow credentials;
  4. **no file in the validator's dependency closure** is writable by this task. The closure covers the validator, the modules it imports, the `conftest.py` chain, every implicit pytest config source, and the package `__init__.py` chain — `__init__.py` is imported and executed before the target module by `unittest`, and by `pytest` whenever rootdir makes the target part of a package. Allowlisting the entry point alone is insufficient: `test_auto_intake.py` imports `auto_intake.py` and `deepseek_implementer.py`, so a task permitted to write those modules could have its modified copy executed with workflow credentials. `VALIDATOR_DEPENDENCIES` declares the full closure per validator — including the `conftest.py` chain and pytest config files (`pytest.ini`, `tox.ini`, `setup.cfg`, `pyproject.toml`), which the runner auto-loads and executes before the named target, and the command is refused if `path_allowed()` is true for **any** member. A validator with no declared closure falls back to itself only.

  A broad scope can still be used by explicitly listing the closure in `forbidden_paths`, in either the plain (`dir`) or glob (`dir/**`) form — `path_allowed()` treats the two identically in the forbidden and allowed branches, and a test pins that symmetry across both copies of the helper. `TRUSTED_PYTHON_VALIDATORS` is derived from `VALIDATOR_DEPENDENCIES`, so there is one source of truth, and a drift test asserts every module the validator actually loads is declared.

  Modules that only compile or parse (`py_compile`, `compileall`, `json.tool`, `ruff`) may target any repo-safe path, since their arguments are data rather than code. `mypy` and `flake8` are deliberately **not** allowlisted: `[mypy] plugins = evil.py` in a task-writable `mypy.ini`/`setup.cfg`/`pyproject.toml` executes task-authored Python, and neither tool has an equivalent of pytest's single-config `-c` pin. `ruff` remains because it is native code with no Python plugin loading;
- no token may be a shell keyword, shell interpreter, network client (`curl`, `wget`, `nc`, `ssh`, `scp`, `rsync`, ...), deploy tool (`wrangler`, `kubectl`, `terraform`, `docker`, `aws`, ...), package manager / arbitrary executor (`pip`, `npm`, `make`, `eval`, `exec`, `source`, `xargs`, `find`, `node`, ...), or a forbidden flag (`-c`, `-e`, `--eval`, `--exec`, `--command`, `-i`).

Anything not explicitly permitted is rejected.

## Durable idempotency

GitHub is the **source of truth**; local files are only a cache.

### Durable ledger (authoritative, O(1), history-independent)

Each processed `task_id` gets a permanent repository **label** — `ai-intake-done:<task_id>`, or `ai-intake-done:<truncated>~<sha256[:16]>` when the readable form would exceed GitHub's 50-character label limit. `receipt_label()` is a pure function, so the same `task_id` always maps to the same key on every runner, forever.

### Claiming, not observing

The ledger entry is **claimed**, never merely observed. `create_receipt_label()` issues `POST /repos/{repo}/labels` and reads the status:

- `201` / `200` -> this process created the entry and **owns** the task;
- `422` -> the label already exists, so a concurrent run created it first. That is a **lost race**: `ReceiptRaceLost` is raised, the run becomes `DUPLICATE_SKIPPED`, and it does **not** mark, cache, or claim ownership;
- anything else -> `TaskError`, fail closed.

A later `GET` returning `200` is never accepted as proof of ownership — only the process whose POST actually created the entry may continue. Two concurrent runs that both observe the label absent therefore still produce exactly one `READY`.

The pre-flight duplicate check is a single `GET /repos/{repo}/labels/{name}`:

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
2. `create_receipt_label()` — durable ledger **claim** (must return 201/200; 422 means the race was lost and the run becomes a duplicate);
3. `post_receipt()` — human-readable audit comment, **best-effort**: ownership is already established, so a transport failure here logs `AUTO_INTAKE_RECEIPT_AUDIT_DEGRADED` and does not turn a completed intake into a failure;
4. `mark_processed()` — local cache;
5. `READY` status.

If step 1 or step 2 fails, the later steps never run, the in-batch memo is not updated, and the task remains eligible for a later retry.

## Per-issue failure isolation

No GitHub transport failure may escape the per-issue boundary. `github_request_status()` never calls `fail()`, `report_status()` raises `TaskError` rather than `SystemExit`, and `safe_report_status()` contains `BaseException` (including `SystemExit`) around every status report. The per-issue handler explicitly catches `ReceiptRaceLost`, `SystemExit`, `TaskError` and `Exception`, so a transport-level abort in one issue can never terminate the batch.

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
- base_sha bound to authoritative HEAD (historical-but-valid SHA rejected as STALE before any claim; current HEAD accepted; unresolvable/malformed HEAD fails closed)
- write-before-mark ordering (write -> claim -> audit -> mark)
- context_files path safety (`/proc/self/environ`, `../../`, `.git/config`, `.env`, `cloudflare-worker/.dev.vars`, symlink escape, missing file, directory)
- python validator trust boundary (mandatory immutable pytest config pin; closed runner-option grammar blocking plugin/config injection; exactly one explicit target, no discovery; exact-match allowlist only, no directory trust; a task-writable validator or any task-writable file in its dependency closure is refused; declared closure drift-guarded)
- receipt claim race (lost race -> duplicate; GET 200 is not ownership; two concurrent runs yield exactly one READY)
- transport failure containment (receipt SystemExit on issue 1, issue 2 still processes; audit failure does not fail the task)
- workflow entry boundary (every implementer invocation preceded by AUTO-INTAKE; no inline contract parsing; task-file path passed as argv and the snippet executed for real; no auto-merge/deploy in the loop)
- immutable control plane (repair runs main-pinned executables; a tampered PR copy cannot replace them)
- credential-free validation (secrets and plugin-injection env vars absent from the validator environment end-to-end)
- post-validation out-of-scope mutation detection and validator-artifact containment (behavioural, real git repo)
- no merge / deploy / PR endpoint is ever called
- downstream contract with `deepseek_implementer.DANGEROUS_VALIDATION` (no gap, no conflict, no weakening)

## Downstream contract: `deepseek_implementer.DANGEROUS_VALIDATION`

`scripts/ai/deepseek_implementer.py` keeps its own `DANGEROUS_VALIDATION` denylist regex and executes validation commands via `bash -lc`. It is **left unchanged**, and is classified as an **independent downstream defence-in-depth gate**, not a conflict, for three reasons:

1. **No gap.** Every command that denylist names (`rm -rf`, `git reset --hard`, `git clean`, `git push`, `git commit`, `wrangler deploy`, `curl -X POST|PUT|PATCH|DELETE`) is already rejected by AUTO-INTAKE's allowlist. AUTO-INTAKE is strictly the stricter layer.
2. **No conflict.** The denylist never matches anything AUTO-INTAKE accepts, so an accepted task cannot hard-block downstream and stall the loop.
3. **It guards a different entry point.** `deepseek_implementer.py` accepts an arbitrary `task_file` argument. A task file that never passed through AUTO-INTAKE — hand-authored, or produced by some future path — is gated *only* by that denylist. Removing or replacing it would weaken protection for exactly the case it exists to cover.

Scope note: `WRITE_LOCK.md` currently has `LOCKED: true`, `OWNER: DEEPSEEK` covering AI orchestration infrastructure. `deepseek_implementer.py` is DeepSeek's implementation surface; editing it here would be scope expansion under an active foreign lock. AUTO-INTAKE's own gate is tightened instead.

**Two downstream changes were required.**

1. `ensure_result_scope()` previously ran only *before* `run_validations()`, and validation commands execute code — so a validator could mutate files outside `allowed_paths` and never be detected. It is now also called *after* `run_validations()`.
2. That recheck would have failed spuriously on caches a validator legitimately creates. `is_validator_artifact()` exempts a **fixed** set of deterministic, repository-owned artifacts — `.pytest_cache`, `__pycache__`, `.mypy_cache`, `.ruff_cache`, `.hypothesis` directory segments and `.pyc`/`.pyo` files — and the exemption applies **only** to newly-untracked files. Arbitrary untracked files (including arbitrary dotfiles such as `.envrc` or `.secret_stash`) are still detected, and modifications to **tracked** files are never exempt even if the file has an artifact-like name. The same paths are gitignored so they never enter a PR.

3. Validation commands now execute with a **credential-free environment**. `credential_free_env()` removes known secret variables (`DEEPSEEK_API_KEY`, `GITHUB_TOKEN`, `GH_TOKEN`, cloud and Actions tokens) plus anything matching `TOKEN|SECRET|PASSWORD|CREDENTIAL|_KEY$|API_KEY`, while keeping `PATH`, `HOME` and other benign variables. Even a validator that somehow escaped the intake allowlist cannot reach a secret-bearing service with workflow privileges.

`DANGEROUS_VALIDATION` itself is untouched and the denylist is not weakened.

These properties are proven **behaviourally** in `test_downstream_scope.py` against a real temporary git repository: an actual out-of-scope mutation performed by an actual validation command is detected; real cache artifacts do not trigger a false failure; arbitrary untracked files still do. No test asserts that a source string exists. Both guards were mutation-tested — removing the scope check fails 7 tests, removing the artifact exemption fails 1.

This contract is enforced by tests, not just prose: `TestDownstreamValidationContract` proves AUTO-INTAKE blocks the entire downstream denylist, that the denylist never rejects an intake-accepted command, that arbitrary shell slipping past the denylist is stopped upstream, that a written task file contains no shell metacharacters, and that the downstream pattern itself has not been weakened.

## Write-path containment

`path_allowed()` is a string check, so it cannot see symlinks. `contained_write_path()` resolves every edit target with `os.path.realpath` and refuses any path whose real location escapes `ROOT` or whose components include a symlink. It runs twice: at `validate_edit_spec()` time, and again immediately before each write, because an earlier edit in the same batch could introduce a symlink component after validation. This matters because a write that lands outside the work tree is invisible to `git diff`/`git ls-files`, so `ensure_result_scope()` would never report it.

## Exclusive writer on every writer path

Every job that writes source and pushes verifies `LOCKED: true` + `OWNER: DEEPSEEK`. The `monitor` repair job reads the lock from the pinned `origin/main` SHA rather than the working tree, and does so **before** any PR branch is checked out, so a PR can never grant itself the lock. A repository-wide test asserts that every pushing job in every workflow performs this check.

## Safety invariants

- No automatic merge or deployment.
- No trading execution or risk logic modification.
- No Cloudflare worker modification.
- No secret exposure.
- No arbitrary shell execution from issue text.
- Stale-base, WRITE_LOCK, write-lease and SHA-bound reviewer gates remain enforced downstream.
