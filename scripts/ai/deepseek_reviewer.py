#!/usr/bin/env python3
"""DeepSeek ADVERSARIAL_REVIEWER for the bounded multi-AI engineering loop.

Role (see docs/ai-coengineer/AI_LOOP_CONTRACT.md):
  - inspect the exact PR diff for the exact head SHA
  - inspect test / check evidence attached to that head
  - return a machine-readable ACCEPT / REJECT / BLOCKED verdict
  - post or update exactly one PR comment

Hard limits:
  - never modifies source
  - never merges
  - never deploys
  - never prints the API key
  - bounded: network timeout, max 3 attempts, bounded exponential backoff

Only the Python standard library is used, matching scripts/ai/deepseek_implementer.py.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
import time
import urllib.error
import urllib.request

API_URL = os.environ.get("DEEPSEEK_API_URL", "https://api.deepseek.com/chat/completions")
MODEL = os.environ.get("DEEPSEEK_MODEL", "deepseek-chat")

REQUEST_TIMEOUT_SEC = int(os.environ.get("DEEPSEEK_TIMEOUT_SEC", "120"))
MAX_ATTEMPTS = 3
BACKOFF_BASE_SEC = 2.0
BACKOFF_CAP_SEC = 16.0

# Infrastructure-sized PRs run well past 60k chars. DeepSeek's context comfortably holds
# ~160k chars of diff alongside the system prompt and a 4k-token reply, and a reviewer that
# cannot see the whole diff must REJECT (see fetch_diff), so a too-small budget would make
# large PRs permanently unreviewable.
MAX_DIFF_CHARS = int(os.environ.get("DEEPSEEK_MAX_DIFF_CHARS", "160000"))
# An oversized diff is split at file boundaries and reviewed in chunks rather than
# truncated. The cap keeps the work bounded; beyond it the PR is genuinely too large to
# review in one pass and the reviewer says so instead of pretending otherwise.
MAX_DIFF_CHUNKS = int(os.environ.get("DEEPSEEK_MAX_DIFF_CHUNKS", "6"))
# MAX_ATTEMPTS bounds retries per call. This bounds the WHOLE review, so a chunked
# review cannot quietly multiply into an unbounded number of API requests.
MAX_TOTAL_REQUESTS = int(os.environ.get("DEEPSEEK_MAX_TOTAL_REQUESTS", "12"))
MAX_EVIDENCE_CHARS = 8000

COMMENT_MARKER = "<!-- ai-loop:deepseek-review -->"
# The account this reviewer runs as. Only its own comments may be updated in place, and
# only its comments are admissible as a verdict on the controller side.
BOT_LOGIN = os.environ.get("AI_LOOP_BOT_LOGIN", "github-actions[bot]")

BEGIN = "DEEPSEEK_REVIEW_BEGIN"
END = "DEEPSEEK_REVIEW_END"

SHA_RE = re.compile(r"^[0-9a-f]{40}$")

# Patterns that must never be echoed back into a PR comment or stdout.
SECRET_PATTERNS = [
    re.compile(r"sk-[A-Za-z0-9_\-]{16,}"),
    re.compile(r"gh[pousr]_[A-Za-z0-9]{20,}"),
    re.compile(r"(DEEPSEEK_API_KEY|ANTHROPIC_API_KEY|CLOUDFLARE_API_TOKEN|TWELVEDATA_API_KEY|GITHUB_TOKEN)\s*[:=]\s*\S+", re.I),
    re.compile(r"-----BEGIN [A-Z ]*PRIVATE KEY-----"),
]


class LoopBlocked(Exception):
    """A hard blocker: the reviewer cannot produce a verdict at all."""

    def __init__(self, classification: str, message: str) -> None:
        super().__init__(message)
        self.classification = classification
        self.message = message


def redact(text: str) -> str:
    """Strip anything that looks like a credential before it leaves this process."""
    if not text:
        return text
    out = text
    for pat in SECRET_PATTERNS:
        out = pat.sub("[REDACTED]", out)
    key = os.environ.get("DEEPSEEK_API_KEY")
    if key and len(key) >= 8:
        out = out.replace(key, "[REDACTED]")
    token = os.environ.get("GITHUB_TOKEN")
    if token and len(token) >= 8:
        out = out.replace(token, "[REDACTED]")
    return out


def log(message: str) -> None:
    print(redact(message), flush=True)


def run(cmd: list[str], timeout: int = 120) -> subprocess.CompletedProcess:
    return subprocess.run(
        cmd, capture_output=True, text=True, timeout=timeout, check=False,
        encoding="utf-8", errors="replace",
    )


def gh_json(args: list[str], timeout: int = 90):
    proc = run(["gh"] + args, timeout=timeout)
    if proc.returncode != 0:
        raise LoopBlocked("GITHUB_ERROR", f"gh {' '.join(args)} failed: {redact(proc.stderr.strip())}")
    try:
        return json.loads(proc.stdout or "null")
    except json.JSONDecodeError as exc:
        raise LoopBlocked("GITHUB_ERROR", f"gh returned non-JSON: {exc}") from exc


# --------------------------------------------------------------------------------------
# Context gathering
# --------------------------------------------------------------------------------------

def fetch_pr(repo: str, pr: int) -> dict:
    data = gh_json([
        "pr", "view", str(pr), "--repo", repo,
        "--json", "number,title,body,headRefName,baseRefName,headRefOid,additions,deletions,changedFiles,state",
    ])
    if not isinstance(data, dict) or not data.get("headRefOid"):
        raise LoopBlocked("GITHUB_ERROR", f"PR #{pr} metadata unavailable")
    return data


def fetch_diff(repo: str, pr: int) -> str:
    """Return the COMPLETE diff. Fitting it to the model is split_diff's job."""
    proc = run(["gh", "pr", "diff", str(pr), "--repo", repo], timeout=180)
    if proc.returncode != 0:
        raise LoopBlocked("GITHUB_ERROR", f"gh pr diff failed: {redact(proc.stderr.strip())}")
    return proc.stdout or ""


def _split_file_diff(file_diff: str) -> list[str]:
    """Split one file's diff at @@ hunk boundaries, repeating the file header each time.

    Never slices mid-hunk: a half hunk is malformed diff text that would mislead the
    reviewer about what actually changed.
    """
    hunks = re.split(r"(?m)^(?=@@ )", file_diff)
    header = hunks[0] if hunks else file_diff
    bodies = [h for h in hunks[1:] if h.strip()]
    if not bodies:
        # No hunk markers to split on (binary/rename-only). Emit as-is rather than
        # corrupting it; an over-budget single piece is still a faithful piece.
        return [file_diff]

    out: list[str] = []
    current = header
    for hunk in bodies:
        if len(current) + len(hunk) > MAX_DIFF_CHARS and current != header:
            out.append(current)
            current = header + hunk
        else:
            current += hunk
    if current.strip() and current != header:
        out.append(current)
    return out or [file_diff]


def split_diff(diff: str) -> list[str]:
    """Split an oversized diff into review chunks at file boundaries.

    Truncating and rejecting was correct but made any PR larger than the budget
    permanently unreviewable, and simply raising the budget just defers the same wall.
    Chunking at `diff --git` boundaries keeps every hunk intact and lets the whole change
    be reviewed. Verdicts are merged by the caller: any REJECT wins.
    """
    if len(diff) <= MAX_DIFF_CHARS:
        return [diff]

    # Keep each file's diff whole; only split BETWEEN files.
    parts = re.split(r"(?m)^(?=diff --git )", diff)
    parts = [p for p in parts if p.strip()]

    chunks: list[str] = []
    current = ""
    for part in parts:
        if len(part) > MAX_DIFF_CHARS:
            # A single file larger than the budget. Slicing at raw byte offsets would cut
            # hunks in half and hand the reviewer malformed, misleading diff text, so split
            # at @@ hunk boundaries and repeat the file header on every piece.
            if current:
                chunks.append(current)
                current = ""
            chunks.extend(_split_file_diff(part))
            continue
        if len(current) + len(part) > MAX_DIFF_CHARS:
            chunks.append(current)
            current = part
        else:
            current += part
    if current:
        chunks.append(current)

    if len(chunks) > MAX_DIFF_CHUNKS:
        raise LoopBlocked(
            "DIFF_TOO_LARGE",
            f"diff needs {len(chunks)} chunks but the cap is {MAX_DIFF_CHUNKS}; "
            "split this PR into smaller reviewable changes",
        )
    return chunks


def fetch_changed_files(repo: str, pr: int) -> list[str]:
    """Full file list, so a truncated diff still reveals the true scope of the change."""
    try:
        data = gh_json(["pr", "view", str(pr), "--repo", repo, "--json", "files",
                        "--jq", "[.files[] | \"\\(.path) (+\\(.additions)/-\\(.deletions))\"]"])
        return list(data or [])
    except LoopBlocked:
        return []


def fetch_checks(repo: str, sha: str) -> tuple[str, list[str]]:
    """Return (rollup, failing_names) for the exact head SHA."""
    try:
        data = gh_json(["api", f"repos/{repo}/commits/{sha}/check-runs", "--jq", ".check_runs"])
    except LoopBlocked:
        return "UNKNOWN", []
    if not isinstance(data, list) or not data:
        return "UNKNOWN", []
    failing, pending = [], 0
    for run_item in data:
        status = (run_item or {}).get("status")
        conclusion = (run_item or {}).get("conclusion")
        name = (run_item or {}).get("name") or "unnamed"
        if status != "completed":
            pending += 1
        elif conclusion in ("failure", "timed_out", "cancelled", "action_required"):
            failing.append(name)
    if failing:
        return "FAIL", failing
    if pending:
        return "PENDING", []
    return "PASS", []


def read_evidence(path: str | None) -> str:
    if not path:
        return "(no local test evidence file supplied)"
    try:
        with open(path, "r", encoding="utf-8", errors="replace") as fh:
            text = fh.read()
    except OSError as exc:
        return f"(evidence file unreadable: {exc})"
    if len(text) > MAX_EVIDENCE_CHARS:
        text = text[:MAX_EVIDENCE_CHARS] + "\n[evidence truncated]"
    return text


# --------------------------------------------------------------------------------------
# DeepSeek call
# --------------------------------------------------------------------------------------

SYSTEM_PROMPT = f"""You are DEEPSEEK, the ADVERSARIAL_REVIEWER in a bounded multi-AI engineering loop
for a SIGNAL-ONLY trading repository. You are a reviewer, not an implementer. You never
authorize deployment and you never merge.

Your job is to try to REFUTE the claim that this PR is safe and correct. Default to REJECT
when you are genuinely uncertain about a capital-safety or execution-correctness issue.
Do not invent defects to look useful; a clean diff deserves ACCEPT.

Priority order when weighing findings:
CAPITAL SAFETY > EXECUTION CORRECTNESS > DATA INTEGRITY > RELIABILITY > UX CLARITY >
PERFORMANCE > PROFIT OPTIMIZATION.

Treat any of the following as a BLOCKER, not a nit:
- weakening SIGNAL-ONLY architecture or executionAuthority
- weakening quote freshness, structural SL, RR gates, anti-chase or hard-news safeguards
- fabricating broker/exchange quotes, P/L, or backtest statistics
- resetting TRADING_STATE or v775:books
- restoring Hyro auto-trade, TK2, Futures Signal or Binance20 execution
- mutating the V73 frozen prior
- committing or printing a secret
- duplicate execution, lost idempotency, or a race in the order/signal lifecycle

Also look hard for: stale/missing data handling, fail-open behaviour, partial API
degradation, restart/recovery, KV state migration, and Telegram duplication/spam.

Your reply MUST BEGIN with the machine-readable block, before any prose. Putting it last
means a long analysis can run out of room and lose it entirely, which makes the whole
review unusable. Emit the block first, then add brief notes after it if you wish (under
250 words).

Start your reply with exactly this block:

{BEGIN}
HEAD_SHA=<the exact head sha you were given>
VERDICT=ACCEPT|REJECT|BLOCKED
BLOCKERS=<one finding per line, or the single word NONE>
NON_BLOCKING=<one finding per line, or the single word NONE>
{END}

Rules for the block:
- It must be the FIRST thing in your reply. Nothing may precede the BEGIN line.
- HEAD_SHA must be copied verbatim from the prompt.
- VERDICT=ACCEPT requires BLOCKERS=NONE. Never emit ACCEPT with a non-empty BLOCKERS list.
- Use BLOCKED only if you cannot review at all (for example the diff is unavailable).
- Anything after {END} is optional commentary and is not parsed.
"""


def build_user_prompt(pr: dict, diff: str, checks_status: str, failing: list[str], evidence: str, objective: str | None, changed_files: list[str] | None = None, part: tuple[int, int] | None = None) -> str:
    parts = [
        f"REPOSITORY: hanlinh227-ship-it/trading-api",
        f"PR: #{pr['number']} — {pr.get('title') or '(no title)'}",
        f"BRANCH: {pr.get('headRefName')} -> {pr.get('baseRefName')}",
        f"HEAD_SHA: {pr['headRefOid']}",
        f"SIZE: +{pr.get('additions', 0)}/-{pr.get('deletions', 0)} across {pr.get('changedFiles', 0)} file(s)",
        "",
    ]
    if objective:
        parts += ["LOOP OBJECTIVE (what this PR is supposed to achieve):", objective, ""]
    if changed_files:
        parts += ["COMPLETE CHANGED-FILE LIST (authoritative scope, even if the diff below is truncated):"]
        parts += [f"  - {f}" for f in changed_files]
        parts += [""]
    parts += [
        "PR DESCRIPTION (author intent - verify the diff actually matches it):",
        (pr.get("body") or "(empty)").strip(),
        "",
        f"GITHUB CHECK ROLLUP for {pr['headRefOid']}: {checks_status}",
        ("FAILING CHECKS: " + ", ".join(failing)) if failing else "FAILING CHECKS: none",
        "",
        "LOCAL DETERMINISTIC TEST EVIDENCE:",
        evidence.strip(),
        "",
        "EXACT PR DIFF:",
        "```diff",
        diff,
        "```",
        "",
    ]
    if part and part[1] > 1:
        parts += [
            f"NOTE: this is PART {part[0]} OF {part[1]} of a diff too large for one request.",
            "Review ONLY what is shown here. Do not flag the split itself as a finding - the",
            "other parts are reviewed separately and every verdict is merged, with any REJECT",
            "winning. The authoritative full scope is the changed-file list above.",
            "Do NOT report that something is missing, undefined or unreferenced merely because",
            "you cannot see it in this part - it is very likely defined in another part. Only",
            "report a defect you can demonstrate from the text actually shown here.",
            "",
        ]
    parts += [
        f"Review the diff above against the head SHA {pr['headRefOid']} and emit your block.",
    ]
    return "\n".join(parts)


def classify_http_error(exc: urllib.error.HTTPError) -> tuple[str, bool]:
    """Return (classification, retryable)."""
    code = exc.code
    if code in (401, 403):
        return "AUTH_ERROR", False
    if code == 402:
        return "PAYMENT_REQUIRED", False
    if code == 429:
        return "RATE_LIMITED", True
    if code == 400:
        return "BAD_REQUEST", False
    if 500 <= code < 600:
        return "SERVER_ERROR", True
    return f"HTTP_{code}", False


# One HTTP attempt budget for the ENTIRE review, shared by the initial call and the
# protocol-repair call. Without this, two invocations of three attempts each could make
# six requests, breaking the contract's "maximum attempts = 3".
_ATTEMPTS_USED = [0]
_TOTAL_REQUESTS = [0]


def attempts_remaining() -> int:
    return max(0, MAX_ATTEMPTS - _ATTEMPTS_USED[0])


def reset_attempts() -> None:
    """Start a fresh attempt budget. Called once per diff chunk, never mid-review.

    The per-review total is deliberately NOT reset: MAX_ATTEMPTS bounds retries within a
    call, MAX_TOTAL_REQUESTS bounds the review end to end.
    """
    _ATTEMPTS_USED[0] = 0


def merge_results(results: list[dict]) -> dict:
    """Combine per-chunk verdicts. Any rejection wins; ACCEPT requires unanimity."""
    if not results:
        raise LoopBlocked("EMPTY_REVIEW", "no chunk produced a verdict")
    if len(results) == 1:
        return results[0]
    blockers, non_blocking = [], []
    saw_reject = saw_blocked = False
    for r in results:
        blockers.extend(r["blockers"])
        non_blocking.extend(r["non_blocking"])
        if r["verdict"] == "REJECT":
            saw_reject = True
        elif r["verdict"] == "BLOCKED":
            saw_blocked = True
            blockers.append("A diff chunk could not be reviewed (chunk verdict BLOCKED).")
    # REJECT takes precedence over BLOCKED. Both fail the gate, but BLOCKED stops the loop
    # outright while REJECT feeds actionable findings into another round - so an
    # unreviewable chunk must not mask a concrete rejection from a chunk that WAS reviewed.
    if saw_reject:
        verdict = "REJECT"
    elif saw_blocked:
        verdict = "BLOCKED"
    else:
        verdict = "ACCEPT"
    if blockers and verdict == "ACCEPT":
        verdict = "REJECT"
    seen = set()
    blockers = [b for b in blockers if not (b in seen or seen.add(b))]
    seen = set()
    non_blocking = [n for n in non_blocking if not (n in seen or seen.add(n))]
    return {
        "head_sha": results[0]["head_sha"],
        "verdict": verdict,
        "blockers": blockers,
        "non_blocking": non_blocking,
        "downgraded": any(r.get("downgraded") for r in results),
    }


def call_deepseek(system_prompt: str, user_prompt: str) -> str:
    key = os.environ.get("DEEPSEEK_API_KEY")
    if not key:
        raise LoopBlocked("MISSING_SECRET", "DEEPSEEK_API_KEY is not available to this job")
    if attempts_remaining() <= 0:
        raise LoopBlocked("ATTEMPTS_EXHAUSTED",
                          f"the {MAX_ATTEMPTS}-attempt budget for this review is already spent")

    payload = json.dumps({
        "model": MODEL,
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ],
        "temperature": 0.0,
        "max_tokens": 4000,
        "stream": False,
    }).encode("utf-8")

    last: tuple[str, str] | None = None
    budget = attempts_remaining()
    for attempt in range(1, budget + 1):
        _ATTEMPTS_USED[0] += 1
        req = urllib.request.Request(
            API_URL,
            data=payload,
            headers={"Authorization": f"Bearer {key}", "Content-Type": "application/json"},
            method="POST",
        )
        if _TOTAL_REQUESTS[0] >= MAX_TOTAL_REQUESTS:
            raise LoopBlocked("REQUEST_BUDGET_EXHAUSTED",
                              f"this review already made {_TOTAL_REQUESTS[0]} requests "
                              f"(cap {MAX_TOTAL_REQUESTS})")
        _TOTAL_REQUESTS[0] += 1
        try:
            with urllib.request.urlopen(req, timeout=REQUEST_TIMEOUT_SEC) as resp:
                body = json.loads(resp.read().decode("utf-8"))
            content = (body.get("choices") or [{}])[0].get("message", {}).get("content")
            if not content:
                raise LoopBlocked("EMPTY_RESPONSE", "DeepSeek returned no message content")
            return content
        except urllib.error.HTTPError as exc:
            classification, retryable = classify_http_error(exc)
            detail = ""
            try:
                detail = redact(exc.read().decode("utf-8", "replace"))[:400]
            except Exception:
                pass
            last = (classification, f"HTTP {exc.code}: {detail}")
            log(f"DeepSeek attempt {_ATTEMPTS_USED[0]}/{MAX_ATTEMPTS} failed [{classification}]")
            if not retryable:
                raise LoopBlocked(classification, last[1]) from exc
        except urllib.error.URLError as exc:
            last = ("NETWORK_ERROR", str(exc.reason))
            log(f"DeepSeek attempt {_ATTEMPTS_USED[0]}/{MAX_ATTEMPTS} failed [NETWORK_ERROR]")
        except TimeoutError:
            last = ("TIMEOUT", f"no response within {REQUEST_TIMEOUT_SEC}s")
            log(f"DeepSeek attempt {_ATTEMPTS_USED[0]}/{MAX_ATTEMPTS} failed [TIMEOUT]")
        except json.JSONDecodeError as exc:
            last = ("BAD_RESPONSE", f"non-JSON response: {exc}")
            log(f"DeepSeek attempt {_ATTEMPTS_USED[0]}/{MAX_ATTEMPTS} failed [BAD_RESPONSE]")

        if attempt < budget:
            delay = min(BACKOFF_BASE_SEC * (2 ** (attempt - 1)), BACKOFF_CAP_SEC)
            log(f"backing off {delay:.0f}s before retry")
            time.sleep(delay)

    classification, message = last or ("UNKNOWN", "exhausted attempts")
    raise LoopBlocked(classification, f"{_ATTEMPTS_USED[0]}/{MAX_ATTEMPTS} attempts exhausted: {message}")


# --------------------------------------------------------------------------------------
# Verdict block handling
# --------------------------------------------------------------------------------------

def parse_block(text: str) -> dict:
    """Extract and normalise the machine-readable verdict block."""
    if BEGIN not in text or END not in text:
        raise LoopBlocked("PROTOCOL_ERROR", "DeepSeek reply did not contain a verdict block")
    body = text.split(BEGIN, 1)[1].split(END, 1)[0]

    fields: dict[str, list[str]] = {}
    current: str | None = None
    for raw in body.splitlines():
        line = raw.rstrip()
        if not line.strip():
            continue
        m = re.match(r"^\s*(HEAD_SHA|VERDICT|BLOCKERS|NON_BLOCKING)\s*=\s*(.*)$", line)
        if m:
            current = m.group(1)
            fields[current] = []
            rest = m.group(2).strip()
            if rest:
                fields[current].append(rest)
        elif current:
            fields[current].append(line.strip())

    def one(name: str) -> str:
        vals = fields.get(name) or []
        return vals[0].strip() if vals else ""

    def many(name: str) -> list[str]:
        vals = [v.strip(" -*\t") for v in (fields.get(name) or [])]
        vals = [v for v in vals if v]
        if len(vals) == 1 and vals[0].upper() in ("NONE", "N/A", "-"):
            return []
        return vals

    verdict = one("VERDICT").upper()
    if verdict not in ("ACCEPT", "REJECT", "BLOCKED"):
        raise LoopBlocked("PROTOCOL_ERROR", f"unrecognised VERDICT value: {verdict!r}")

    blockers = many("BLOCKERS")
    non_blocking = many("NON_BLOCKING")

    # Contradiction guard from the contract: ACCEPT with blockers is downgraded to REJECT.
    downgraded = False
    if verdict == "ACCEPT" and blockers:
        verdict = "REJECT"
        downgraded = True

    return {
        "head_sha": one("HEAD_SHA").lower(),
        "verdict": verdict,
        "blockers": blockers,
        "non_blocking": non_blocking,
        "downgraded": downgraded,
    }


def render_block(head_sha: str, verdict: str, blockers: list[str], non_blocking: list[str],
                 trust: str = "trusted") -> str:
    lines = [BEGIN, f"HEAD_SHA={head_sha}", f"VERDICT={verdict}", f"TRUST={trust}"]
    lines.append("BLOCKERS=" + (blockers[0] if blockers else "NONE"))
    lines.extend(blockers[1:])
    lines.append("NON_BLOCKING=" + (non_blocking[0] if non_blocking else "NONE"))
    lines.extend(non_blocking[1:])
    lines.append(END)
    return "\n".join(lines)


def build_comment(head_sha: str, result: dict, prose: str, trust: str = "trusted") -> str:
    icon = {"ACCEPT": "✅", "REJECT": "❌", "BLOCKED": "⛔"}.get(result["verdict"], "❔")
    parts = [
        COMMENT_MARKER,
        f"## {icon} DeepSeek adversarial review — `{head_sha[:12]}`",
        "",
        f"**Verdict:** `{result['verdict']}`  •  **Reviewed SHA:** `{head_sha}`",
        "",
    ]
    if trust != "trusted":
        parts += [
            "> **UNTRUSTED REVIEW.** No reviewer exists at the base revision yet, so this one",
            "> was bootstrapped from the PR head - meaning the change under review supplied its",
            "> own reviewer. The findings are still worth reading, but this verdict cannot count",
            "> as an acceptance and the controller will not gate on it.",
            "",
        ]
    if result.get("downgraded"):
        parts += [
            "> Note: DeepSeek returned `ACCEPT` while also listing blockers. Per the loop "
            "contract this contradiction is downgraded to `REJECT`.",
            "",
        ]
    if result["blockers"]:
        parts += ["### Blockers", ""] + [f"- {b}" for b in result["blockers"]] + [""]
    else:
        parts += ["### Blockers", "", "None.", ""]
    if result["non_blocking"]:
        parts += ["### Non-blocking", ""] + [f"- {n}" for n in result["non_blocking"]] + [""]

    if prose.strip():
        parts += [
            "<details><summary>Reviewer notes</summary>",
            "",
            prose.strip()[:6000],
            "",
            "</details>",
            "",
        ]
    parts += [
        "```",
        render_block(head_sha, result["verdict"], result["blockers"], result["non_blocking"], trust),
        "```",
        "",
        "_DeepSeek is an adversarial reviewer only. It cannot merge or deploy._",
    ]
    return redact("\n".join(parts))


def build_blocked_comment(head_sha: str, classification: str, message: str, trust: str = "trusted") -> str:
    return redact("\n".join([
        COMMENT_MARKER,
        f"## ⛔ DeepSeek adversarial review could not complete — `{head_sha[:12]}`",
        "",
        f"**Classification:** `{classification}`",
        "",
        f"```\n{message}\n```",
        "",
        "```",
        render_block(head_sha, "BLOCKED", [f"DeepSeek review unavailable ({classification})"], [], trust),
        "```",
    ]))


def upsert_comment(repo: str, pr: int, body: str) -> None:
    """Post one comment, or update the existing loop comment in place."""
    comment_id = None
    try:
        comments = gh_json(["api", f"repos/{repo}/issues/{pr}/comments", "--paginate",
                            "--jq", "[.[] | {id, body, login: .user.login}]"])
        for c in comments or []:
            # Author check is mandatory, not cosmetic. Matching on the marker alone also
            # matches any comment that merely QUOTES it - a human comment discussing the
            # protocol - and the reviewer would then overwrite that person's comment and
            # strand its own verdict under a non-bot author, which the controller must
            # ignore. That stalls the loop at PENDING forever.
            if c.get("login") != BOT_LOGIN:
                continue
            if COMMENT_MARKER in (c.get("body") or ""):
                comment_id = c.get("id")
    except LoopBlocked as exc:
        log(f"could not list existing comments ({exc.classification}); will post a new one")

    # Never assume the temp directory exists: a missing RUNNER_TEMP/TEMP would raise
    # FileNotFoundError here and turn a completed review into a failed one.
    tmp_dir = os.environ.get("RUNNER_TEMP") or os.environ.get("TEMP") or "."
    try:
        os.makedirs(tmp_dir, exist_ok=True)
    except OSError:
        tmp_dir = "."
    tmp = os.path.join(tmp_dir, "deepseek_review_body.md")
    try:
        with open(tmp, "w", encoding="utf-8", newline="\n") as fh:
            fh.write(body)
    except OSError as exc:
        raise LoopBlocked("IO_ERROR", f"could not stage the comment body: {exc}") from exc

    if comment_id:
        proc = run(["gh", "api", "-X", "PATCH", f"repos/{repo}/issues/comments/{comment_id}",
                    "-F", f"body=@{tmp}"], timeout=90)
        if proc.returncode == 0:
            log(f"updated existing DeepSeek review comment {comment_id}")
            return
        log("comment update failed; falling back to a new comment")

    proc = run(["gh", "pr", "comment", str(pr), "--repo", repo, "--body-file", tmp], timeout=90)
    if proc.returncode != 0:
        raise LoopBlocked("GITHUB_ERROR", f"failed to post PR comment: {redact(proc.stderr.strip())}")
    log("posted DeepSeek review comment")


def emit_outputs(pairs: dict) -> None:
    path = os.environ.get("GITHUB_OUTPUT")
    if not path:
        return
    try:
        with open(path, "a", encoding="utf-8") as fh:
            for k, v in pairs.items():
                fh.write(f"{k}={v}\n")
    except OSError:
        pass


# --------------------------------------------------------------------------------------

def main() -> int:
    ap = argparse.ArgumentParser(description="DeepSeek adversarial PR reviewer (bounded loop V1)")
    ap.add_argument("--pr", type=int, required=True, help="pull request number")
    ap.add_argument("--repo", default=os.environ.get("GITHUB_REPOSITORY", "hanlinh227-ship-it/trading-api"))
    ap.add_argument("--expect-sha", default=None, help="fail if the PR head is not this SHA")
    ap.add_argument("--evidence-file", default=os.environ.get("AI_LOOP_EVIDENCE_FILE"),
                    help="path to local deterministic test evidence")
    ap.add_argument("--objective", default=os.environ.get("AI_LOOP_OBJECTIVE"),
                    help="the loop objective this PR is meant to achieve")
    ap.add_argument("--trust", choices=["trusted", "bootstrap"], default="trusted",
                    help="trusted = this reviewer came from the base revision; bootstrap = it "
                         "came from the PR head because none exists at base, so the review is "
                         "UNTRUSTED and must not be counted as an acceptance")
    ap.add_argument("--no-comment", action="store_true", help="do not post to GitHub")
    ap.add_argument("--dry-run", action="store_true",
                    help="gather context and validate wiring without calling DeepSeek")
    args = ap.parse_args()

    head_sha = "0" * 40
    try:
        pr = fetch_pr(args.repo, args.pr)
        head_sha = pr["headRefOid"]
        if not SHA_RE.match(head_sha):
            raise LoopBlocked("GITHUB_ERROR", f"malformed head sha {head_sha!r}")
        if args.expect_sha and args.expect_sha.lower() != head_sha.lower():
            raise LoopBlocked(
                "STALE_HEAD",
                f"PR head moved: expected {args.expect_sha}, found {head_sha}. Review would be stale.",
            )

        log(f"reviewing PR #{args.pr} at {head_sha}")
        diff = fetch_diff(args.repo, args.pr)
        if not diff.strip():
            raise LoopBlocked("EMPTY_DIFF", "PR diff is empty; nothing to review")
        checks_status, failing = fetch_checks(args.repo, head_sha)
        evidence = read_evidence(args.evidence_file)
        changed_files = fetch_changed_files(args.repo, args.pr)
        chunks = split_diff(diff)
        prompts = [
            build_user_prompt(pr, c, checks_status, failing, evidence, args.objective,
                              changed_files, part=(i, len(chunks)))
            for i, c in enumerate(chunks, start=1)
        ]
        user_prompt = prompts[0]

        if args.dry_run:
            has_key = bool(os.environ.get("DEEPSEEK_API_KEY"))
            # Phrased to avoid a NAME: VALUE shape, which redact() would (correctly) mask.
            log("DRY RUN - no DeepSeek API call was made")
            log(f"  diff chars       {len(diff)} (budget {MAX_DIFF_CHARS})")
            log(f"  review chunks    {len(chunks)} (cap {MAX_DIFF_CHUNKS})")
            log(f"  changed files    {len(changed_files)}")
            log(f"  prompt chars     {len(user_prompt)}")
            log(f"  checks rollup    {checks_status}")
            log(f"  api key detected {'yes' if has_key else 'NO'} (value never read)")
            log(f"  api url          {API_URL}")
            log(f"  model            {MODEL}")
            emit_outputs({"verdict": "DRY_RUN", "head_sha": head_sha, "api_key_present": str(has_key).lower()})
            print(render_block(head_sha, "BLOCKED", ["DRY_RUN - no verdict produced"], [], args.trust))
            return 0

        results = []
        proses = []
        for idx, prompt_text in enumerate(prompts, start=1):
            if len(prompts) > 1:
                log(f"reviewing chunk {idx}/{len(prompts)}")
            # Each chunk is its own logical review and gets its own bounded attempt budget.
            reset_attempts()
            reply = call_deepseek(SYSTEM_PROMPT, prompt_text)
            try:
                result = parse_block(reply)
            except LoopBlocked as exc:
                if exc.classification != "PROTOCOL_ERROR":
                    raise
                # The model reviewed but broke format. Re-ask once, terse, block only.
                # Bounded: exactly one repair attempt, then the review is BLOCKED.
                log("reply lacked a verdict block; issuing one bounded protocol-repair request")
                repair = (
                    "Your previous reply omitted the mandatory machine-readable block.\n\n"
                    "Reply with ONLY the block below, starting at the very first "
                    "character, and no other text whatsoever:\n\n"
                    f"{BEGIN}\n"
                    f"HEAD_SHA={head_sha}\n"
                    "VERDICT=ACCEPT|REJECT|BLOCKED\n"
                    "BLOCKERS=<one per line, or NONE>\n"
                    "NON_BLOCKING=<one per line, or NONE>\n"
                    f"{END}\n\n"
                    "Base it on the review you just performed. Here it is again for reference:\n\n"
                    + reply[:6000]
                )
                reply = call_deepseek(SYSTEM_PROMPT, repair)
                result = parse_block(reply)

            if result["head_sha"] != head_sha.lower():
                raise LoopBlocked(
                    "STALE_REVIEW",
                    f"DeepSeek reported HEAD_SHA={result['head_sha']} but the PR head is {head_sha}",
                )
            results.append(result)
            # Commentary follows the block now that the block comes first.
            proses.append(reply.split(END, 1)[-1] if END in reply else "")

        result = merge_results(results)
        prose = "\n\n".join(p for p in proses if p.strip())
        if not args.no_comment:
            upsert_comment(args.repo, args.pr, build_comment(head_sha, result, prose, args.trust))

        emit_outputs({
            "verdict": result["verdict"],
            "head_sha": head_sha,
            "blocker_count": str(len(result["blockers"])),
            "trust": args.trust,
        })
        print(render_block(head_sha, result["verdict"], result["blockers"], result["non_blocking"], args.trust))

        # REJECT is a valid review outcome, not a job failure. The controller decides.
        return 0

    except LoopBlocked as exc:
        log(f"DEEPSEEK_BLOCKED [{exc.classification}] {exc.message}")
        if not args.no_comment and SHA_RE.match(head_sha):
            try:
                upsert_comment(args.repo, args.pr, build_blocked_comment(head_sha, exc.classification, exc.message, args.trust))
            except LoopBlocked as inner:
                log(f"could not post blocked comment: {inner.message}")
        emit_outputs({"verdict": "BLOCKED", "head_sha": head_sha, "classification": exc.classification})
        print(render_block(head_sha, "BLOCKED", [f"{exc.classification}: {exc.message}"], [], args.trust))
        # A review that cannot complete must fail the job loudly.
        return 1
    except subprocess.TimeoutExpired as exc:
        log(f"DEEPSEEK_BLOCKED [SUBPROCESS_TIMEOUT] {exc}")
        return 1


if __name__ == "__main__":
    sys.exit(main())
