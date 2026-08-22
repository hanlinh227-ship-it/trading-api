# CLAUDE — MULTI-AI ENGINEERING INFRASTRUCTURE AUDIT

Audited against SHA: `d6d94f61dcaac83ac7fabd4b608e5037c94ad9c1` (origin/main, fresh `git fetch` + `git reset --hard`)
Auditor: CLAUDE (independent reviewer / architecture auditor)
Date: 2026-08-22
Verdict: **BLOCK** — the closed loop is structurally incapable of completing a task today, and one defect can produce a *fabricated* Claude ACCEPT.
Scope: AI orchestration infrastructure only. No V11 trading logic was modified. No deploy. No merge. No WRITE_LOCK acquisition. No secrets printed.

Evidence labelling used throughout:
- **VERIFIED** — reproduced from source on this SHA, from a real Actions run log, or from a live GitHub API response.
- **INFERRED** — follows necessarily from a documented platform rule plus verified local state, but not yet observed failing in this repo.
- **UNKNOWN** — not determinable from available evidence.

---

## 0. Executive summary

The loop as it exists on `main` cannot complete a single task, and has never completed one.
Zero `ai/deepseek-*` pull requests exist. Five orphan implementation branches do exist.

Three independent blockers stack:

1. `gh pr create` is refused repo-wide, so every writer entry point pushes a branch and then dies. (VERIFIED, 3 run logs)
2. There is no Claude watcher anywhere — no process, no systemd unit, no cron, no script. The `CLAUDE_REVIEW_REQUEST` comment has no consumer. (VERIFIED)
3. The Claude verdict parser matches the workflow's own request template, so when a PR *does* exist, the loop reads `CLAUDE_VERDICT: ACCEPT` from a comment Claude never wrote. (VERIFIED by empirical replay)

Item 3 is the most dangerous finding in this audit. Fixing items 1 and 2 without fixing item 3 first would produce a loop that confidently announces `READY_FOR_FINAL_ACCEPT` with zero Claude involvement.

Separately, and outside the AI loop but sharing its trigger: the repository is **PUBLIC**, and three workflows run `npx wrangler deploy` against production Cloudflare on `issues: [opened]` guarded only by an issue title. Any GitHub user can trigger a production deploy. (VERIFIED — this is open issue #64, still unfixed.)

---

## 1. Findings

### CRITICAL

#### C1 — The Claude review request template parses as a Claude ACCEPT verdict
- **Files:** `.github/workflows/ai-loop.yml:132-143` (producer), `.github/workflows/ai-loop.yml:208-217` (consumer)
- **Evidence:** VERIFIED by replaying the exact comment body through the exact parser.

The dispatch job posts a request comment that embeds the response *template*:

```
CLAUDE_REVIEW_BEGIN
CLAUDE_REVIEW_HEAD: <implementation sha>
CLAUDE_VERDICT: ACCEPT|REJECT|BLOCKED
CLAUDE_FINDINGS:
<concise findings or NONE>
CLAUDE_REVIEW_END
```

The monitor job then scans every comment on the PR for `CLAUDE_REVIEW_BEGIN` plus `CLAUDE_REVIEW_HEAD: <head>`, and applies `re.search(r'CLAUDE_VERDICT:\s*(ACCEPT|REJECT|BLOCKED)')`. That regex matches the first alternative in the literal string `ACCEPT|REJECT|BLOCKED`.

Replaying the real body against the real parser yields:

```
has CLAUDE_REVIEW_BEGIN: True
has head marker      : True
parsed CLAUDE_VERDICT: ACCEPT
parsed CLAUDE_FINDINGS: '<concise findings or NONE>'
```

- **Root cause:** three compounding errors — (a) the request and the response share a grammar, (b) the parser has **no author allow-list**, (c) the parser has no structural anchoring (`^CLAUDE_VERDICT:` at line start after a `CLAUDE_REVIEW_BEGIN` that is not preceded by `CLAUDE_REVIEW_REQUEST`).
- **Impact:** `claude_verdict='ACCEPT'` with no Claude. Combined with any Codex ACCEPT signal, the loop posts `mandatory CODEX + CLAUDE consensus ACCEPT ... READY_FOR_FINAL_ACCEPT`. Contract §6.5 and the "missing verdict is never implicit acceptance" rule are both violated by the implementation that claims to enforce them.
- **Aggravating factor:** because there is no author filter, *any* GitHub user on this public repo can post a verdict block and be counted as Claude.

#### C2 — `CLAUDE_REVIEW_REQUEST` has no consumer; Claude is structurally absent
- **Files:** `.github/workflows/ai-loop.yml`, `ai-loop-wake.yml`, `ai-task.yml` (all producers)
- **Evidence:** VERIFIED.
  - Repo-wide grep for `CLAUDE_REVIEW_REQUEST` / `CLAUDE_REVIEW_BEGIN` outside docs returns only the three producing workflows. No consumer exists.
  - `systemctl list-units --all | grep -iE 'ai|claude|watcher|bridge'` → only `auto-futures-hub-bridge.service`. No Claude watcher unit.
  - `crontab -l` → `no crontab for root`.
  - `pwsh` / `powershell` → not installed, so the V1 controller `scripts/ai/ai-loop.ps1` cannot run either.
- **Root cause:** the contract (AI_LOOP_CONTRACT §1) declares a "configured Claude watcher/bridge" that was never built.
- **Impact:** every `requires_claude: true` task is unsatisfiable by design. Without C1, the loop would hang forever in `AWAITING_CODEX_AND_CLAUDE`; with C1, it silently fabricates the missing half.

#### C3 — Task-supplied `validation_commands` are executed as shell in a privileged, publicly-triggerable workflow
- **Files:** `scripts/ai/deepseek_implementer.py:50-54` (`bash -lc`), `:113-118` (weak filter), `:379-389` (execution); `.github/workflows/ai-loop.yml:24-33`
- **Evidence:** VERIFIED reachable.
  - `gh repo view --json visibility` → `"PUBLIC"`.
  - `ai-loop.yml` triggers on `issues: [opened]` with `if: startsWith(github.event.issue.title, '[AI-TASK]')` and **no `github.actor` guard**.
  - The job env contains `DEEPSEEK_API_KEY: ${{ secrets.DEEPSEEK_API_KEY }}` and `GH_TOKEN: ${{ github.token }}` with `contents: write`.
  - `validation_commands` are read verbatim from the issue body and run via `subprocess.run(["bash","-lc", command])`.
- **Root cause:** an untrusted, world-writable input channel (public issue body) is wired to a shell interpreter inside a secret-bearing job. The `DANGEROUS_VALIDATION` regex is a denylist over a handful of literal command spellings; it does not constrain the interpreter, and equivalent operations reach the same effect through spellings the regex does not describe (for example a plain GET rather than a `-X POST`, or `git -c …` rather than `git push`).
- **Reachability:** the shell step is gated behind a successful in-scope DeepSeek edit, which an attacker can obtain by declaring a broad `allowed_paths` and a trivial `replace` objective. `base_sha` is not a barrier — `main`'s HEAD is public.
- **Impact:** arbitrary code execution in CI with `secrets.DEEPSEEK_API_KEY` in the environment and a write-capable `GITHUB_TOKEN`. This is repository compromise plus secret disclosure.
- **Note:** the `contains_secret()` guard only inspects committed text. It does not constrain what a validation command does with the environment.

#### C4 — Three production Cloudflare deploys are triggerable by any GitHub user opening an issue
- **Files:** `.github/workflows/v78-028-final-runner.yml:3-12,64-65,109`, `v78-028-hotfix-030-final.yml:3-12,64-65,113`, `v78-index-quote-fallback-030.yml:2-9,67-68,109`
- **Evidence:** VERIFIED. All three are `on: issues: [opened]`, all three gate only on `if: github.event.issue.title == '<literal>'`, none checks `github.actor`, all three carry `CLOUDFLARE_API_TOKEN` / `CLOUDFLARE_ACCOUNT_ID` / `TRADING_KV_NAMESPACE_ID` and run `npx wrangler deploy`. Repo visibility is PUBLIC.
- **Root cause:** issue title used as an authorization token. Titles are public and appear in this repo's own issue list.
- **Impact:** unauthenticated production deploy of `main` to the live trading worker. This is the same defect already filed as open issue **#64** ("six workflows carry a live wrangler deploy; three can be triggered by opening an issue"), still unremediated.
- **Interaction with the AI loop:** every `[AI-TASK]` issue currently fans out to **12 workflow runs**. (VERIFIED — issue #103 at 04:10:34Z produced 12 runs, 11 skipped.)

#### C5 — Every writer entry point is hard-blocked at `gh pr create`
- **Files:** `.github/workflows/ai-loop.yml:120`, `ai-loop-wake.yml:128`, `ai-task.yml:97`
- **Evidence:** VERIFIED, three separate runs:
  - run `32549719798` — `pull request create failed: GraphQL: GitHub Actions is not permitted to create or approve pull requests (createPullRequest)`
  - run `32549740507` — identical
  - run `32550104832` — identical
  - `gh api repos/.../actions/permissions/workflow` → `{"default_workflow_permissions":"write","can_approve_pull_request_reviews":false}`
- **Root cause:** the repository/org setting *Allow GitHub Actions to create and approve pull requests* is disabled. The workflows depend on it and never check for it.
- **Impact:** the loop cannot produce a reviewable artifact. Worse, the branch is pushed *before* the PR attempt, so each failure leaves an unreviewed commit on `origin` (see H1).

---

### HIGH

#### H1 — Five orphan `ai/deepseek-*` branches carry unreviewed V11 trading-source commits
- **Evidence:** VERIFIED via `git ls-remote` + per-branch `git show --stat`.

| Branch | SHA | Base | Files |
|---|---|---|---|
| `ai/deepseek-V11-QUALITY-OPT-001-32547223159` | `01493d79` | `3904bbdd` | hub-v11.js, v11/native-runtime.js, v11/store.js, validate-worker.mjs |
| `ai/deepseek-V11-QUALITY-OPT-001-RETRY-32548423807` | `f0196299` | `3904bbdd` | same 4 |
| `ai/deepseek-V11-QUALITY-OPT-001-WAKE-32549719798` | `a5bdfcd9` | `84cf86dc` | hub-v11.js, native-runtime.js, validate-worker.mjs |
| `ai/deepseek-V11-QUALITY-OPT-001-WAKE2-32550104832` | `54855eff` | `84cf86dc` | same 4 |
| `ai/deepseek-V11-QUALITY-OPT-002-ACTIVE-32549740507` | `b1f47044` | `84cf86dc` | same 4 |

- **Root cause:** `git push` precedes `gh pr create` with no rollback on failure, and nothing garbage-collects branches that never obtained a PR.
- **Impact:** five divergent, mutually inconsistent implementations of the same objective sit on `origin`, touching protected V11 signal source, with no reviewer, no PR, no issue linkage and no expiry. They are invisible to every guard in the system because every guard queries *pull requests*, not *branches*.

#### H2 — The duplicate-implementation guard is defeated by branch-only writes and by task_id renaming
- **Files:** `ai-loop.yml:62-68`, `ai-loop-wake.yml:75-77`, `ai-task.yml:76-77`
- **Evidence:** VERIFIED. The guard is `gh pr list --state open --search "${TASK_ID} in:title"`. H1 shows four branches for what is one logical task, distinguished only by suffixes `-RETRY`, `-WAKE`, `-WAKE2`.
- **Root cause:** identity is the free-text `task_id`, uniqueness is checked against open PRs only, and the check does not consult branches or the linked issue.
- **Secondary:** GitHub code/issue search is index-lagged and tokenizes hyphenated ids, so even the PR-only check is not race-free. (INFERRED)
- **Contract impact:** violates AI_LOOP_CONTRACT §2 ("A second open implementation PR for the same `task_id` is forbidden") in spirit and in effect.

#### H3 — DeepSeek edits the validator that certifies it, then reports `IMPLEMENTED_VALIDATED`
- **Files:** `cloudflare-worker/validate-worker.mjs` on branches `01493d79` and `54855eff`
- **Evidence:** VERIFIED. On `54855eff`, DeepSeek added to `store.js` a key `v11:watch` and an export `getV11Watch`, and in the same commit added to `validate-worker.mjs`:

```js
if(!store.includes('v11:watch'))errors.push('V11 store must maintain dedicated WATCH list');
if(!hub.includes('getV11Watch'))errors.push('V11 hub must use dedicated WATCH list');
```

  The assertions test for the exact strings the same commit introduced. `01493d79` does the same with `PROVIDER_FAILURE` / `getV11ProviderFailures` / `providerFailureRows`.
- **Root cause:** `validate-worker.mjs` is inside the writable scope of the task it validates, and `run_validations()` treats exit code 0 as evidence.
- **Impact:** the "deterministic validation" leg of the acceptance gate is tautological whenever the validator is in scope. AI_LOOP_CONTRACT §10 states this rule for `.github/workflows/**` but not for validation scripts; the gap is being exercised right now.
- **Secondary state finding:** `54855eff` introduces a new KV key `v11:watch` with no entry in `docs/ai-coengineer/V78_KV_KEY_REGISTRY.md`.

#### H4 — Codex ACCEPT is derived from a reaction that is not bound to any SHA
- **File:** `.github/workflows/ai-loop.yml:201-206`
- **Evidence:** VERIFIED by code. `reactions` comes from `repos/{repo}/issues/{n}/reactions` — reactions on the **pull request body**, which has no commit association. `codex_plus` is then treated as ACCEPT.
- **Root cause:** conflating a PR-level reaction with a head-level review.
- **Impact:** a `+1` left at round 1 still reads as ACCEPT at round 3 after two DeepSeek repairs. Directly violates AI_LOOP_CONTRACT §6.6 ("No reviewer evidence is stale") and §7 ("Review evidence is cached by implementation SHA"). `codex_reviewed` has a related weakness: it accepts `commit_id in (None, head)`.

#### H5 — `REVIEWED_PENDING_SIGNAL` is an unreachable terminal state
- **File:** `.github/workflows/ai-loop.yml:206,224`
- **Evidence:** VERIFIED by code. If Codex submits a review with no inline blocking comments and leaves no `+1`, `codex_verdict` becomes `REVIEWED_PENDING_SIGNAL`, which is not in `('ACCEPT','REJECT')`, so `required_ready` is false and the iteration `continue`s. Forever, every 15 minutes, with no output.
- **Impact:** the single most likely real Codex outcome is an infinite silent stall.

#### H6 — No reviewer timeout, no heartbeat, no escalation
- **Evidence:** VERIFIED by absence. `ai-loop.yml` contains no deadline for `PENDING` verdicts, no age check on the PR, no "reviewer overdue" comment, and no transition to `BLOCKED` on timeout. The only `heartbeat` string in `docs/`, `scripts/` or `.github/` is a passing mention in `V78_CLAUDE_PHASE1_BLUEPRINT.md`.
- **Impact:** `AWAITING_CODEX_AND_CLAUDE` has no exit under failure. The contract's `BLOCKED` state has no producer other than an explicit Claude `BLOCKED` verdict that nothing can currently emit.

#### H7 — Issue #103 fails deterministically on DeepSeek output truncation, and will keep failing
- **Evidence:** VERIFIED from run `32550993905` (attempt 2):
  `DEEPSEEK_WORKER_BLOCK: STRUCTURED_EDIT_FORMAT_INVALID: invalid JSON response: Unterminated string starting at: line 43 column 19 (char 14281)`
- **Root cause:** the task asks DeepSeek to repair four workflow files plus `scripts/ai/**` in a single JSON object of `new_text` blobs, under `max_output_tokens: 5000`. ~14.3 KB of JSON had been emitted when the budget ran out. The task is not expressible within its own output budget.
- **Cost:** `max_rounds: 2` × 2 run attempts = up to four DeepSeek calls, each preceded by up to 120 000 characters of `context_max_chars`, all discarded. Retrying without re-scoping repeats the spend exactly.
- **Fix direction:** this is a task-decomposition problem, not a parser problem. One file per task, or a `max_output_tokens` sized to the declared scope, plus a pre-flight that rejects a task whose `allowed_paths` byte count exceeds what the output budget can express.

#### H8 — Even on success, issue #103 cannot be pushed
- **Evidence:** INFERRED (high confidence). `#103.allowed_paths` includes four `.github/workflows/*.yml` entries. The Actions `GITHUB_TOKEN` cannot create or update workflow files; that capability requires the `workflow` OAuth scope, which is not grantable through the `permissions:` block. The push step in `ai-loop.yml:107` uses the default token.
- **Impact:** the current task is unachievable by the current writer regardless of C5 and H7. Workflow-file repair must be performed by an actor holding a `workflow`-scoped credential. The VPS `gh` token does hold `workflow` (VERIFIED: scopes `gist, read:org, repo, workflow`).

#### H9 — `main` is unprotected; contract §6.3 has nothing behind it
- **Evidence:** VERIFIED. `gh api repos/.../branches/main/protection` → `404 Branch not protected`.
- **Impact:** no required status checks, no required reviews, no force-push protection. AI_LOOP_CONTRACT §6 item 3 ("Required GitHub checks for that head pass") is unenforceable, and the monitor never queries checks despite the workflow requesting `checks: read` and `statuses: read` permissions.

#### H10 — `ai-task.yml` produces PRs that the monitor is structurally unable to see
- **File:** `.github/workflows/ai-task.yml:97-100`
- **Evidence:** VERIFIED by code. The monitor filters on `'AI_LOOP_TASK_ISSUE:' in (p.get('body') or '')` (`ai-loop.yml:186`). `ai-task.yml`'s PR body contains no such marker.
- **Compounding defects in the same file:**
  - Lines 97/99/100 use `\n` inside a double-quoted bash string. Bash does not interpret it; the PR body and both review-request comments are posted as single lines containing literal backslash-n.
  - No `base_sha` staleness check at all — `ai-task.yml` reads a committed task file and never compares it to HEAD, so the contract's fail-closed stale rule does not apply on this path.
  - The duplicate-PR check (line 76) runs *after* the DeepSeek API call (line 55), so a duplicate is detected only after paying for it.
- **Impact:** a fallback writer that creates PRs no consensus engine tracks.

#### H11 — Role inversion is still encoded in four places on `main`
- **Evidence:** VERIFIED.

| Source | Declares | Conflicts with |
|---|---|---|
| `scripts/ai/claude_loop_prompt.md:1` | "CLAUDE_LOCAL — PRIMARY_IMPLEMENTER"; instructs Claude to edit files and expects `WRITE_LOCK OWNER: CLAUDE_LOCAL` | Contract §1 (DeepSeek sole writer) |
| `scripts/ai/ai-loop.ps1` (AI_LOOP_V1) | Claude implements, DeepSeek reviews via `deepseek_reviewer.py` | Contract §1 (DeepSeek writes, never reviews own work) |
| `docs/ai-coengineer/AI_LOOP_PROTOCOL.md:9` | "Codex = CONTROL PLANE … final acceptance authority" | Contract §1 (ChatGPT is control plane; Codex is a reviewer only) |
| `CLAUDE.md` (repo root) | Claude is "IMPLEMENTER", may acquire WRITE_LOCK and write source | Contract §1 + `WRITE_LOCK.md` `OWNER: DEEPSEEK` |

- **Impact:** four mutually contradictory role definitions are simultaneously authoritative-looking. Any actor that reads the wrong one becomes a second writer. `ai-loop.ps1` is currently inert only because `pwsh` is absent from the VPS — that is an accident, not a control.

#### H12 — The repair step commits controller scratch files into the implementation branch
- **File:** `.github/workflows/ai-loop.yml:236,269-271`
- **Evidence:** VERIFIED by code. The inspect step writes `.ai-loop-prs.json` and `.ai-feedback-<n>.txt` into the worktree. The repair step removes only *its own* feedback file, then runs `git add -A && git commit`. `.ai-loop-prs.json` and every other PR's feedback file are committed onto the branch under review.
- **Impact:** reviewer-visible diff pollution; cross-PR review text leaks into an unrelated branch; the "smallest coherent implementation diff" requirement is broken by the controller itself.

---

### MEDIUM

| ID | Finding | File / evidence | Status |
|---|---|---|---|
| M1 | `op: "create"` tasks always fail. New files are untracked, so `git diff --name-only` in `ensure_result_scope` (`deepseek_implementer.py:366`) does not see them, and `git diff --quiet` in the workflow's "Require scoped implementation diff" step reports no diff → exit 3 with the misleading message `No implementation diff`. Untracked content also escapes the resulting-diff secret scan. | `deepseek_implementer.py:365-376`; `ai-loop.yml:86`; `ai-loop-wake.yml:95` | VERIFIED |
| M2 | `MAX_ROUNDS_EXHAUSTED` raises `SystemExit` inside the `for FEEDBACK in …` bash loop, failing the whole monitor job. Remaining PRs in the same tick are never processed, and the monitor job has no `if: failure()` reporter, so nothing is posted anywhere. | `ai-loop.yml:262`, `239-282` | VERIFIED |
| M3 | `deepseek_implementer.call_deepseek` has no retry/backoff — a single 429 or 5xx calls `fail()` and kills the task. `deepseek_reviewer.py` (the *unused* V1 script) does implement bounded backoff; the active implementer does not. | `deepseek_implementer.py:351-358` vs `deepseek_reviewer.py:35-38` | VERIFIED |
| M4 | State documents contradict each other and the source. `AI_CONVERSATION_STATE.json` says `protocol_version: 3.0`, `write_lock_owner: CHATGPT`, `task_id: ENTRY-001` while `WRITE_LOCK.md` says `OWNER: DEEPSEEK` and the contract says V2. `OPEN_ISSUES.md` contains no AI-infrastructure entry at all and stops at V78-023. | `AI_CONVERSATION_STATE.json`, `WRITE_LOCK.md`, `OPEN_ISSUES.md` | VERIFIED |
| M5 | `WRITE_LOCK.md` has no expiry, no heartbeat, no `RELEASED` transition and no automated release. Nothing in any workflow ever writes it. A task that dies — as #98, #101 and #103 all did — leaves the lock held indefinitely. | `WRITE_LOCK.md`; no writer found in `.github/` or `scripts/` | VERIFIED |
| M6 | Silent stall is observed, not theoretical. Issues **#98** (02:47) and **#101** (03:43) are OPEN with **zero comments**, yet their dispatch runs failed. The `Report dispatch failure` step was only added at 04:08 in commit `51332ab`. Both tasks are permanently unattended. #103 did get a comment — twice, both pointing at the same run URL because attempt 2 reuses `GITHUB_RUN_ID`. | `gh api …/issues/{98,101}/comments` → `[]`; run list | VERIFIED |
| M7 | `node scripts/ai/ai-loop-selftest.mjs` → **130 passed, 13 failed**, exit 1. Failures include `no stale-head guard`, `the reviewer runs from a trusted revision, not the PR head`, `a bootstrap reviewer cannot vouch for the change that supplied it`, `contract missing role: ADVERSARIAL_REVIEWER`, `contract missing state: TESTING`. No workflow on `main` runs it — the suite even asserts `the selftest is never run by CI` and that assertion fails. | ran locally on this SHA | VERIFIED |
| M8 | Trigger fan-out and schedule drift. One `[AI-TASK]` issue starts 12 workflow runs. The monitor's `cron: '*/15 * * * *'` actually fires roughly hourly (observed 19:13, 19:56, 20:56, 21:56, 22:56, 23:53, 03:09), so the stated 15-minute reaction time is not real. | run list | VERIFIED |
| M9 | The wake workflow appends the raw issue body to `$GITHUB_ENV` using a fixed heredoc delimiter `AI_BODY_EOF`. A body containing that literal terminates the block early — on a public repo this is an attacker-controllable environment-variable injection into a privileged job. | `ai-loop-wake.yml:53-57` | VERIFIED |
| M10 | The `DANGEROUS_VALIDATION` denylist constrains specific command spellings rather than the interpreter. Equivalent effects are reachable through spellings it does not describe. A denylist in front of `bash -lc` is not a boundary. | `deepseek_implementer.py:36-39` | VERIFIED |
| M11 | The contract's `requires_claude` flag is injected by `ai-loop.yml` (line 57) and by the monitor (line 196), but **not** by `ai-loop-wake.yml` or `ai-task.yml`. The invariant depends on which entry point ran. | grep across the three writers | VERIFIED |

### LOW

| ID | Finding | Status |
|---|---|---|
| L1 | `scripts/ai/ai-loop.ps1` (102 KB), `deepseek_reviewer.py` (41 KB), `ai-loop-selftest.mjs` (101 KB) and `claude_loop_prompt.md` are the V1 stack. No workflow references any of them. `pwsh` is not installed on the VPS. This is 245 KB of dead code that still reads as authoritative. | VERIFIED |
| L2 | `.github/workflows/v78-index-quote-fallback-030.yml` fails on essentially every push (its `git hash-object` guard pins a since-changed `engine-v77168.js`). Constant red in the Actions tab desensitises the operator to real failures. | VERIFIED |
| L3 | The monitor job has no `if: failure()` reporting step, unlike the dispatch job. | VERIFIED |
| L4 | `actions/checkout@v4` emits a Node 20 deprecation warning on every run. | VERIFIED |

### UNKNOWN

- Whether the OAuth credential at `/root/.claude/.credentials.json` is currently valid. The file exists (508 bytes, mode 0600) and `claude --version` reports `2.1.239`, but validity was not probed and no token value was read.
- Whether Codex (`chatgpt-codex-connector[bot]`) is actually installed on this repository. No Codex review or reaction was found on any PR, but no PR has ever reached it, so this is untested rather than negative.
- Whether the `can_approve_pull_request_reviews: false` setting is repo-level or inherited from an org/enterprise policy — this determines whether the C5 fix is a repo toggle or requires a PAT.

---

## 2. Root-cause synthesis

Four systemic causes account for nearly every finding above.

**RC-1 — Text-in-comments is used as a control protocol without authentication or grammar separation.**
Request and response share a grammar (C1), no author is checked (C1), a reaction stands in for a review (H4), and a title stands in for authorization (C4). Every one of these is the same mistake: an unauthenticated, unstructured channel treated as a trusted control plane.

**RC-2 — Guards query the wrong object.**
Uniqueness is checked against pull requests while writes land on branches (H1, H2). Scope is checked against tracked diffs while creates land untracked (M1). Validation is checked against a script the writer may edit (H3). Acceptance is checked against comment text rather than against checks (H9).

**RC-3 — There is no liveness layer.**
No timeout, no heartbeat, no lock expiry, no dead-task reaper, no failure classification on the monitor path (H5, H6, M2, M5, M6). Every failure mode degrades to "nothing happens", which is indistinguishable from "still working".

**RC-4 — Documentation forked from implementation, then forked again.**
V1 and V2 role definitions coexist on `main` (H11), state files disagree with the lock (M4), and the only automated consistency check for the AI infrastructure is disconnected from CI and failing (M7).

---

## 3. Target architecture

The mandated topology is correct. What follows is how to make it enforceable rather than declarative.

```
                         ChatGPT (orchestrator, human-authorized)
                                        │ creates
                                        ▼
                            GitHub Issue [AI-TASK]  ── state bus
                                        │
                     (allow-listed actor only, one writer group)
                                        ▼
                  ai-loop.yml ── DeepSeek implementer ── PR @ HEAD_SHA
                                        │
                        ┌───────────────┴───────────────┐
                        ▼                               ▼
              Codex (GitHub app)              Claude watcher (VPS, 24/7)
              review bound to SHA             CLAUDE_REVIEW_* bound to SHA
                        │                               │
                        └───────────────┬───────────────┘
                                        ▼
                         consensus engine (SHA-keyed, authored,
                         timeout-bounded, checks-aware)
                                        │
                        ACCEPT+ACCEPT → READY_FOR_FINAL_ACCEPT
                        any REJECT    → one aggregated repair round
                        timeout/blocked → BLOCKED + explicit diagnostic
                                        │
                              human merge decision (never automated)
```

Non-negotiable invariants the implementation must make *structurally* true, not merely documented:

1. **Authored evidence.** A `CLAUDE_*` verdict counts only if the comment author is on an allow-list, the block is not preceded by `CLAUDE_REVIEW_REQUEST`, and `CLAUDE_REVIEW_HEAD` equals the current `headRefOid` exactly. A `CODEX` verdict counts only from a `reviews` or `pulls/comments` record carrying `commit_id == head`. Reactions are never evidence.
2. **Request/response grammar separation.** The request comment must never contain a parsable verdict. Use `CLAUDE_REVIEW_REQUEST` + a link to the envelope spec in `AI_LOOP_CONTRACT.md`. Never inline the template.
3. **Branch-level uniqueness.** Task identity is `(issue_number, task_id)`. Uniqueness is checked against `git ls-remote --heads origin 'ai/deepseek-*'` *and* open PRs, before the DeepSeek call. A failed `gh pr create` must delete the pushed branch.
4. **Validator immutability during validation.** `cloudflare-worker/validate-worker.mjs`, `.github/workflows/**` and `scripts/ai/**` are never simultaneously in `allowed_paths` and in the validation path. When the writer must change a validator, validation runs from the *base* revision's copy and the change is flagged `SELF_MODIFYING: true` on the PR, requiring explicit orchestrator sign-off (extends contract §10 beyond workflows).
5. **Liveness.** Every task carries `deadline_utc`. The monitor emits `REVIEWER_TIMEOUT`, `WRITER_TIMEOUT` or `LOCK_STALE` with an issue comment. `WRITE_LOCK.md` gains `ACQUIRED`, `EXPIRES`, `TASK_ID`, `HEARTBEAT` and is machine-written by the loop, not by hand.
6. **Untrusted input never reaches an interpreter.** `validation_commands` becomes an allow-list of named validators defined *in the repository* (`npm run check`, `node --check <file>`, `python3 -m py_compile <file>`, `node scripts/ai/ai-loop-selftest.mjs`), selected by key. Free-form strings are rejected.
7. **Actor gating.** Every `issues:`-triggered workflow that holds a secret or a write token gates on `github.event.issue.author_association == 'OWNER'` (or an explicit login allow-list) before any other step.
8. **One writer, structurally.** The V1 stack is deleted or moved to `docs/ai-coengineer/archive/`, and `CLAUDE.md` + `AI_LOOP_PROTOCOL.md` are reconciled to V2 so that no readable document names Claude an implementer.

---

## 4. Patch plan

Ordered by dependency. Nothing below has been applied — `WRITE_LOCK.md` is held by DEEPSEEK and this audit does not contend it.

### Phase 0 — Stop the bleeding (no code; operator actions)
| # | Action | Addresses |
|---|---|---|
| 0.1 | Rotate `CLOUDFLARE_API_TOKEN`, `DEEPSEEK_API_KEY`, `TWELVEDATA_API_KEY`. They have been reachable from a publicly-triggerable code path. | C3, C4 |
| 0.2 | Disable the three issue-triggered deploy workflows (delete, or convert to `workflow_dispatch` + `OWNER` gate). | C4 / issue #64 |
| 0.3 | Decide repo visibility. If PUBLIC is intentional, C3/C4 gating is mandatory before the loop is re-enabled. If not, make it private. | C3, C4 |
| 0.4 | Delete the five orphan `ai/deepseek-*` branches after capturing their diffs for reference. None is reviewed; none should be a merge base. | H1 |
| 0.5 | Close or explicitly re-scope issues #98, #101, #103 with a status comment. | M6 |
| 0.6 | Enable *Allow GitHub Actions to create and approve pull requests*, or provision a PAT secret for PR creation. Confirm whether the setting is org-inherited. | C5 |
| 0.7 | Enable branch protection on `main`: required status checks, no force-push. | H9 |

### Phase 1 — Correctness of the consensus engine (highest value, smallest diff)
| # | Change | File | Addresses |
|---|---|---|---|
| 1.1 | Add an author allow-list and an anti-template guard to the Claude verdict parser. Reject any comment containing `CLAUDE_REVIEW_REQUEST`; require `^CLAUDE_VERDICT:` at line start; require an exact 40-hex `CLAUDE_REVIEW_HEAD` equal to `headRefOid`; require the author to be in `CLAUDE_WATCHER_LOGINS`. | `ai-loop.yml:208-217` | **C1** |
| 1.2 | Stop embedding the response template in the request comment. Reference `AI_LOOP_CONTRACT.md §1` instead. | `ai-loop.yml:132-143`, `ai-loop-wake.yml:140-142`, `ai-task.yml:100` | **C1** |
| 1.3 | Drop `codex_plus` (reactions). Derive Codex verdict only from `pulls/{n}/reviews` and `pulls/{n}/comments` where `commit_id == head`. Map "reviewed, no blockers, at this head" to ACCEPT explicitly. | `ai-loop.yml:201-206` | H4, H5 |
| 1.4 | Add `deadline` handling: if a required verdict is PENDING and PR age exceeds `review_timeout_min` (default 90), comment `REVIEWER_TIMEOUT` on the issue and set `BLOCKED`. | `ai-loop.yml` monitor | H6 |
| 1.5 | Query `checks: read` and require the head's checks to be green before `READY_FOR_FINAL_ACCEPT`. | `ai-loop.yml` monitor | H9, contract §6.3 |
| 1.6 | Wrap the repair loop body in error handling so `MAX_ROUNDS_EXHAUSTED` on one PR comments on that issue and continues to the next. Add an `if: failure()` reporter to the monitor job. | `ai-loop.yml:239-282` | M2, L3 |
| 1.7 | Replace `git add -A` in the repair step with an explicit add of the paths in `allowed_paths`; move scratch files to `$RUNNER_TEMP`. | `ai-loop.yml:236,269-271` | H12 |

### Phase 2 — Writer safety
| # | Change | File | Addresses |
|---|---|---|---|
| 2.1 | Gate every secret-bearing `issues:`-triggered workflow on `github.event.issue.author_association == 'OWNER'`. | `ai-loop.yml`, plus the three deploy workflows if retained | C3, C4 |
| 2.2 | Replace free-form `validation_commands` with a keyed allow-list resolved from a repo-owned table; reject unknown keys with `VALIDATION_COMMAND_NOT_ALLOWED`. Remove `bash -lc`. | `deepseek_implementer.py:36-39,113-118,379-389` | C3, M10 |
| 2.3 | Check for an existing `ai/deepseek-*` branch for `(issue, task_id)` before calling DeepSeek; on `gh pr create` failure, `git push origin --delete "$BRANCH"` in a trap. | all three writers | H1, H2, C5 |
| 2.4 | Use `git status --porcelain` (not `git diff`) for the "did anything change" and scope checks so `create` ops are visible; extend the secret scan to untracked files. | `deepseek_implementer.py:365-376`; `ai-loop.yml:86`; `ai-loop-wake.yml:95` | M1 |
| 2.5 | Add bounded retry with exponential backoff and a total-request cap to `call_deepseek`, mirroring `deepseek_reviewer.py`. | `deepseek_implementer.py:302-362` | M3 |
| 2.6 | Pre-flight the output budget: reject a task whose `allowed_paths` × declared edit breadth cannot fit `max_output_tokens`, with diagnostic `TASK_OUTPUT_BUDGET_INSUFFICIENT`. | `deepseek_implementer.py:load_task` | H7 |
| 2.7 | Add `AI_LOOP_TASK_ISSUE:` to the `ai-task.yml` PR body, fix the literal `\n` bodies, add a `base_sha` check, and move the duplicate check before the DeepSeek call. | `ai-task.yml:76,97-100` | H10 |
| 2.8 | Inject `requires_claude=true` on all three writer paths, not just `ai-loop.yml`. | `ai-loop-wake.yml`, `ai-task.yml` | M11 |
| 2.9 | Replace the `$GITHUB_ENV` heredoc with a random delimiter, or write the body to a file under `$RUNNER_TEMP` and pass the path. | `ai-loop-wake.yml:53-57` | M9 |
| 2.10 | Refuse `.github/workflows/**` in `allowed_paths` unless a `workflow`-scoped credential is configured, with diagnostic `WORKFLOW_SCOPE_UNAVAILABLE`, rather than failing at push time. | `deepseek_implementer.py` / writers | H8 |

### Phase 3 — Self-certification and hygiene
| # | Change | Addresses |
|---|---|---|
| 3.1 | Run validation from the base revision's copy of any validator the diff touches; flag `SELF_MODIFYING: true` on the PR and require orchestrator sign-off. Extend contract §10 to `scripts/ai/**` and `cloudflare-worker/validate-worker.mjs`. | H3 |
| 3.2 | Make `WRITE_LOCK.md` machine-managed: add `TASK_ID`, `EXPIRES`, `HEARTBEAT`; the monitor releases an expired lock and posts `LOCK_STALE`. | M5 |
| 3.3 | Move `ai-loop.ps1`, `deepseek_reviewer.py`, `claude_loop_prompt.md`, `ai-loop-selftest.mjs` to `docs/ai-coengineer/archive/v1/` or delete. Reconcile `CLAUDE.md` and `AI_LOOP_PROTOCOL.md` to V2 roles. Refresh `AI_CONVERSATION_STATE.json` and add AI-infra entries to `OPEN_ISSUES.md`. | H11, L1, M4 |
| 3.4 | Rewrite the selftest against the V2 stack and run it in CI on every `.github/workflows/**` and `scripts/ai/**` change, from the base revision. | M7 |
| 3.5 | Fix or delete `v78-index-quote-fallback-030.yml` so the Actions tab is meaningful. | L2 |

---

## 5. Validation plan

Each phase must be provable without deploying and without merging.

**V-1 — Consensus engine unit harness (must exist before Phase 1 lands).**
A standalone script that feeds synthetic comment sets through the extracted verdict parser. Required cases:
1. The literal request template → verdict `PENDING`. *(This is the C1 regression test and must be written first.)*
2. A well-formed block from an allow-listed author at the current head → `ACCEPT` / `REJECT` / `BLOCKED` as written.
3. The same block from a non-allow-listed author → `PENDING`.
4. A well-formed block at a *previous* head → `PENDING`, never inherited.
5. `CLAUDE_VERDICT: ACCEPT` embedded in prose, in a code fence, or after `CLAUDE_REVIEW_REQUEST` → `PENDING`.
6. Two blocks in one comment, or two comments at the same head → newest authored block wins, deterministically.
7. Codex `+1` reaction only → `PENDING`, never ACCEPT.
8. Codex review at an older `commit_id` → `PENDING`.

**V-2 — Writer safety.** In a scratch repository or with `act`:
- a task whose `validation_commands` contain an unknown key → `VALIDATION_COMMAND_NOT_ALLOWED`, no shell spawned;
- a `create`-only task → real diff detected, correct scope enforcement, no `No implementation diff`;
- a second dispatch for an existing `(issue, task_id)` → `DUPLICATE_IMPLEMENTATION_PR` **before** any DeepSeek call;
- a forced `gh pr create` failure → pushed branch is deleted, issue comment explains why;
- a task with `.github/workflows/**` in `allowed_paths` and no workflow-scoped credential → `WORKFLOW_SCOPE_UNAVAILABLE` at parse time.

**V-3 — Liveness.** With a PR left deliberately unreviewed past `review_timeout_min`, the monitor must post `REVIEWER_TIMEOUT` and transition to `BLOCKED`. With `WRITE_LOCK.md` past `EXPIRES`, it must post `LOCK_STALE`.

**V-4 — Self-certification.** Construct a task that adds an assertion to `validate-worker.mjs` matching a string added in the same commit. Expected: `SELF_MODIFYING: true` on the PR, validation executed from the base copy, and no `IMPLEMENTED_VALIDATED` without orchestrator sign-off.

**V-5 — Trading invariants unchanged.** `cd cloudflare-worker && npm run check`, plus the `v11-signal-validation.yml` invariant greps, must pass identically before and after every phase. No phase touches `cloudflare-worker/**`.

**V-6 — End-to-end rehearsal.** One deliberately trivial `[AI-TASK]` (single file, single replace, `max_output_tokens` sized to it) must traverse dispatch → PR → real Codex verdict → real Claude watcher verdict → `READY_FOR_FINAL_ACCEPT`, with a human performing the merge. Until this passes once, the loop is not operational regardless of what the documents say.

---

## 6. Claude watcher design

Target: a 24/7 VPS process that consumes `CLAUDE_REVIEW_REQUEST`, spends **zero** Claude tokens while idle, and never writes source.

### 6.1 Placement and identity
- Host: this VPS. Unit: `claude-review-watcher.service` (systemd, `Restart=always`, `RestartSec=30`).
- Working root: a dedicated clone at `/opt/trading/claude-review-workspace`, **separate** from `/opt/trading/trading-api-main-deploy`, so review checkouts never disturb engineering worktrees.
- GitHub identity: a dedicated bot account, or the existing `hanlinh227-ship-it` token. Whichever is chosen, its login goes into `CLAUDE_WATCHER_LOGINS` and the parser allow-list (patch 1.1). Reviews posted under the repo owner's account are indistinguishable from human comments and weaken the audit trail — a separate identity is preferred.

### 6.2 Poll loop — plain code, no model calls
```
every POLL_INTERVAL (default 60s):
  prs = gh pr list --state open --json number,headRefOid,body,updatedAt
  for pr in prs where body contains "AI_LOOP_TASK_ISSUE:":
      head = pr.headRefOid
      if state[pr.number].last_reviewed_sha == head: continue        # cache hit, no tokens
      req = newest comment matching ^CLAUDE_REVIEW_REQUEST with CLAUDE_REVIEW_HEAD == head
      if not req: continue                                            # nothing asked of us
      if already_posted_verdict(pr.number, head): 
          state[pr.number].last_reviewed_sha = head; continue         # idempotent recovery
      enqueue(pr.number, head)
```
Everything above is `gh` + JSON. No Claude invocation occurs unless a request exists at an unreviewed SHA. This is the token-discipline requirement and it is satisfied by construction.

State file `~/.claude-review-watcher/state.json`:
```json
{ "prs": { "<pr>": { "last_reviewed_sha": "<40hex>",
                     "attempts": 0,
                     "last_verdict": "ACCEPT|REJECT|BLOCKED",
                     "last_reviewed_at": "<iso8601>" } },
  "heartbeat_at": "<iso8601>", "version": 1 }
```
Written atomically (temp file + `os.replace`). Survives restart; a crash mid-review re-enters the queue and is deduplicated by `already_posted_verdict`.

### 6.3 Review execution — read-only, detached, bounded
```
git -C $WS fetch origin --prune
git -C $WS checkout --detach <head>          # exact SHA, never a branch name
git -C $WS clean -xdf                        # no residue between reviews
```
Then, with a hard wall-clock timeout (`REVIEW_TIMEOUT_SEC`, default 900):
```
claude -p "<review prompt>" \
  --allowedTools "Read Grep Glob Bash(git diff:*) Bash(git show:*) Bash(git log:*)" \
  --disallowedTools "Edit Write NotebookEdit Bash(git commit:*) Bash(git push:*) Bash(gh pr merge:*) Bash(npx wrangler:*)" \
  --output-format text
```
Constraints that must hold:
- `--dangerously-skip-permissions` / `--allow-dangerously-skip-permissions` are **never** used. Safety is enforced by the allow-list, by the detached read-only checkout, and by the watcher — not by bypassing the permission layer.
- No write tool is on the allow-list. The watcher never repairs DeepSeek's implementation; it reports.
- The prompt supplies: the task contract JSON from the linked issue, `git diff main...<head>`, the changed-file list, validation evidence from the PR, and the exact `<head>`. It does **not** ask Claude to read the whole repository (contract §7).

### 6.4 Output contract
The watcher extracts and posts exactly:
```
CLAUDE_REVIEW_BEGIN
CLAUDE_REVIEW_HEAD: <head>
CLAUDE_VERDICT: ACCEPT|REJECT|BLOCKED
CLAUDE_FINDINGS:
<concise findings or NONE>
CLAUDE_REVIEW_END
```
- The watcher itself writes `CLAUDE_REVIEW_HEAD` from the SHA it checked out, never from model output. If the model's echoed SHA disagrees, the verdict is discarded and retried.
- If the model output contains no parsable verdict, the watcher posts `CLAUDE_VERDICT: BLOCKED` with `CLAUDE_FINDINGS: PROTOCOL_ERROR - no parsable verdict block after N attempts`.
- Exactly one verdict comment per `(pr, head)`. Re-runs update in place via an HTML marker comment.

### 6.5 Failure handling — never silent
| Condition | Action |
|---|---|
| `claude` exits non-zero with an auth error, or `/root/.claude/.credentials.json` is missing/expired | Post `CLAUDE_VERDICT: BLOCKED`, `CLAUDE_FINDINGS: CLAUDE_UNAVAILABLE - <classification>`. Do **not** retry in a tight loop; back off to `AUTH_RETRY_SEC` (default 900). |
| Wall-clock timeout | Kill the process group. Retry up to `MAX_ATTEMPTS` (default 2) with backoff. On exhaustion post `BLOCKED` / `CLAUDE_TIMEOUT`. |
| Rate limit / transient API error | Exponential backoff, capped, counted against `MAX_ATTEMPTS`. |
| Checkout fails (force-pushed head) | Skip; the next poll picks up the new head. Log `HEAD_MOVED`. |
| `gh` unauthenticated | Post nothing (cannot). Emit `CLAUDE_WATCHER_DEGRADED` to the heartbeat file and journal at `error` level. |

Retries are bounded and per-`(pr, head)`. A permanently failing head cannot loop.

### 6.6 Heartbeat
- Local: touch `~/.claude-review-watcher/heartbeat` and log to journald every poll.
- Remote: once per `HEARTBEAT_INTERVAL` (default 3600s), upsert a single comment on a dedicated tracking issue:
  `CLAUDE_WATCHER_HEARTBEAT: <iso8601> | polls=<n> | reviews=<n> | last_verdict=<v> | status=OK|DEGRADED|CLAUDE_UNAVAILABLE`
  Upsert by marker so this never becomes comment spam.
- The `ai-loop.yml` monitor should treat a heartbeat older than `2 × HEARTBEAT_INTERVAL` as `CLAUDE_WATCHER_DOWN` and refuse to interpret an absent Claude verdict as anything but `BLOCKED`.

### 6.7 Race avoidance with GitHub Actions
The watcher takes **no** write lock and touches **no** source. Its only writes are PR comments. The Actions monitor is the sole consensus authority and the sole repairer. Because the watcher keys on `headRefOid`, a DeepSeek repair push during a review simply produces a verdict at a now-stale SHA — which the SHA-bound parser (patch 1.1) correctly discards, after which the next poll reviews the new head. No lock, no coordination protocol, no race.

### 6.8 Explicit non-goals
The watcher must never: modify source, push, merge, deploy, acquire `WRITE_LOCK`, write to `main`, invoke `wrangler`, or print a secret. Nothing in its allow-list permits any of these.

---

## 7. VPS bootstrap still required

Present and VERIFIED on this host:
- `claude` 2.1.239 at `/usr/bin/claude`; `/root/.claude/.credentials.json` exists (0600, 508 bytes) — validity UNKNOWN.
- `gh` 2.97.0, authenticated as `hanlinh227-ship-it`, scopes `gist, read:org, repo, workflow`.
- `git`, `node`, `python3`.

Missing and required:

| # | Item | Note |
|---|---|---|
| B1 | The watcher itself | Not written. Recommend Python 3 + stdlib + `gh` subprocess, matching the existing `scripts/ai/*.py` house style. Proposed path `scripts/ai/claude_review_watcher.py`. |
| B2 | `claude-review-watcher.service` | `Restart=always`, `RestartSec=30`, `WorkingDirectory=/opt/trading/claude-review-workspace`, `EnvironmentFile=/etc/claude-review-watcher.env`. No unit currently exists. |
| B3 | Dedicated review clone | `/opt/trading/claude-review-workspace` does not exist. Must be separate from the engineering worktree. |
| B4 | `/etc/claude-review-watcher.env` (mode 0600) | `GH_REPO`, `POLL_INTERVAL`, `REVIEW_TIMEOUT_SEC`, `MAX_ATTEMPTS`, `HEARTBEAT_INTERVAL`, `HEARTBEAT_ISSUE`, `WORKSPACE`. No API keys — Claude auth stays in `/root/.claude/`, GitHub auth stays in `gh`. |
| B5 | Watcher GitHub identity decision | Dedicated bot account vs. owner token. Determines `CLAUDE_WATCHER_LOGINS` in patch 1.1. **Blocks Phase 1.** |
| B6 | Heartbeat tracking issue | One long-lived issue for `CLAUDE_WATCHER_HEARTBEAT` upserts. |
| B7 | Credential validity probe | Confirm `claude -p` succeeds headless as the service user before enabling the unit. Currently UNKNOWN. |
| B8 | Log rotation | journald caps, plus rotation for the watcher's own review transcripts if it retains them. |
| B9 | `pwsh` | **Not required** — the V1 PowerShell controller should be retired (patch 3.3), not resurrected. Installing `pwsh` would re-arm the role-inverted V1 writer described in H11. |

---

## 8. Contract deltas required

`AI_LOOP_CONTRACT.md` is largely correct in intent but under-specifies four things the implementation got wrong:

1. **§1 / §6.5** — must state that a verdict is admissible only from an allow-listed author, and that the request comment must not contain a parsable verdict block. (C1)
2. **§6.4** — must state that a reaction is never reviewer evidence and that Codex evidence must carry `commit_id == head`. (H4)
3. **§10** — must extend the self-certification rule from `.github/workflows/**` to `scripts/ai/**` and any file in the validation path, and must define `SELF_MODIFYING`. (H3)
4. **§5 / §8** — must define `REVIEWER_TIMEOUT`, `LOCK_STALE`, `CLAUDE_WATCHER_DOWN` and `CLAUDE_UNAVAILABLE` as first-class states with mandatory diagnostics, so that "no verdict" can never present as "still working". (H5, H6, M5)

---

## 9. Output contract

- **Reviewed against SHA:** `d6d94f61dcaac83ac7fabd4b608e5037c94ad9c1`
- **Verdict:** `BLOCK`
- **Current problems:** 5 CRITICAL, 12 HIGH, 11 MEDIUM, 4 LOW — see §1. The loop has never completed a task; zero `ai/deepseek-*` PRs exist; five unreviewed orphan branches touching V11 signal source do.
- **Target architecture:** §3.
- **Patch/commit:** none. This audit is read-only. `WRITE_LOCK.md` is `LOCKED: true` / `OWNER: DEEPSEEK` and was not contended. No push was made, so `base_sha` for issue #103 is unchanged.
- **Regression risks:** Phase 1 changes the consensus parser; V-1 case 1 (template → PENDING) is the mandatory regression test. Phase 2.2 changes the validation-command contract and will reject existing task JSON that uses free-form commands — issues #98/#101/#103 must be rewritten. Phase 3.3 deletes files that `ai-loop-selftest.mjs` requires; the selftest must be rewritten in the same change.
- **Risk impact:** no trading risk parameter, gate, threshold or execution authority was read, proposed for change, or changed. Every finding is confined to AI orchestration infrastructure, except C4, which is a production-deploy exposure the AI loop's own trigger shares.
- **State impact:** none from this audit. Noted for the orphan branches: `54855eff` introduces KV key `v11:watch` absent from `V78_KV_KEY_REGISTRY.md`. `TRADING_STATE` and `v775:books` untouched.
- **Execution impact:** none. `SIGNAL_ONLY` unchanged. No Hyro/TK2/Futures/Binance execution path was read or altered.
- **Data integrity:** no market data, ATR, quote, P/L or deployment evidence was fabricated. Every claim above is labelled VERIFIED, INFERRED or UNKNOWN, and every VERIFIED claim traces to a file+line on this SHA, an Actions run id, or a live GitHub API response quoted inline.
- **Required next action:** Phase 0 (§4) is operator-only and should precede all code changes — in particular credential rotation and disabling the three publicly-triggerable deploy workflows. Then Phase 1.1/1.2 (the fabricated-ACCEPT fix) must land before any attempt to make the loop produce a PR.
