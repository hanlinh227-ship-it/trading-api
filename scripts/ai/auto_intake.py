#!/usr/bin/env python3
"""AUTO-INTAKE V1: GitHub Issue -> bounded pipeline task.

Discovers GitHub issues explicitly marked as AI-loop tasks, parses the
machine-readable AI_TASK_JSON block, validates scope and safety, enforces
durable GitHub-backed idempotency, reports singular durable status to GitHub,
and fails closed on any underspecified or unsafe write task.

Hard invariants:
- never merges, pushes or deploys;
- never accepts a hard-forbidden or repo-wide write scope;
- never accepts arbitrary shell in validation_commands;
- a malformed issue never aborts the rest of the batch;
- a task is only marked processed AFTER its task file is durably written.
"""

from __future__ import annotations

import argparse
import datetime
import hashlib
import json
import os
import pathlib
import re
import subprocess
import sys
import urllib.error
import urllib.parse
import urllib.request

# The control plane may be executed from an immutable main-pinned copy while
# operating on an untrusted PR worktree. AI_REPO_ROOT names the repository to
# act on; the executable itself always comes from wherever this file lives.
ROOT = pathlib.Path(
    os.environ.get("AI_REPO_ROOT") or pathlib.Path(__file__).resolve().parents[2]
).resolve()

GITHUB_API = os.environ.get("GITHUB_API_URL", "https://api.github.com")
REPO = os.environ.get("GITHUB_REPOSITORY", "hanlinh227-ship-it/trading-api")
GITHUB_TOKEN = os.environ.get("GITHUB_TOKEN", "")

AI_TASK_MARKER = "[AI-TASK]"
AI_TASK_JSON_BEGIN = "AI_TASK_JSON_BEGIN"
AI_TASK_JSON_END = "AI_TASK_JSON_END"

PER_PAGE = 100
MAX_ISSUE_PAGES = 20
# Bounded by a SINGLE issue's own comment count, not by repo-wide history.
MAX_ISSUE_COMMENT_PAGES = 20

REQUIRED_FIELDS = [
    "task_id", "base_sha", "objective", "allowed_paths",
    "forbidden_paths", "acceptance_criteria", "validation_commands",
    "max_rounds", "max_output_tokens", "requires_claude",
    "auto_merge", "context_files",
]

# --- scope safety -----------------------------------------------------------

HARD_FORBIDDEN_PREFIXES = (".git/",)
HARD_FORBIDDEN_EXACT = {
    ".env", "cloudflare-worker/.dev.vars", ".git", ".", "*", "**",
}
BROAD_SCOPE_EXACT = {".", "./", "*", "**", "./**", "**/*", "*/**", "/", ""}
BROAD_SCOPE_PREFIXES = ("./",)

SECRET_PATTERNS = (
    re.compile(r"sk-[A-Za-z0-9_-]{20,}"),
    re.compile(r"DEEPSEEK_API_KEY\s*[:=]\s*[^$\s]+", re.I),
    re.compile(r"ANTHROPIC_API_KEY\s*[:=]\s*[^$\s]+", re.I),
    re.compile(r"OPENAI_API_KEY\s*[:=]\s*[^$\s]+", re.I),
)

# --- validation command grammar (strict allowlist) --------------------------

SAFE_VALIDATION_GRAMMAR = re.compile(
    r"^[A-Za-z0-9_./-]+(?:\s+[A-Za-z0-9_./=-]+)*$"
)
SAFE_VALIDATION_COMMANDS = {
    "python", "python3", "pytest", "ruff", "flake8", "mypy",
    "git", "echo", "true", "false",
}
SAFE_VALIDATION_GIT_SUBCOMMANDS = {
    "diff", "status", "log", "show", "rev-parse", "ls-files",
    "check-ignore", "check-attr",
}
# Python modules that EXECUTE the code they are pointed at. Their path
# arguments must be trusted, immutable repository validators.
EXECUTING_PYTHON_MODULES = {"pytest", "unittest"}
# Modules that only compile/parse/inspect. Their path arguments are data.
NON_EXECUTING_PYTHON_MODULES = {
    "py_compile", "compileall", "json.tool", "mypy", "ruff", "flake8",
}
SAFE_PYTHON_MODULES = EXECUTING_PYTHON_MODULES | NON_EXECUTING_PYTHON_MODULES
# Commands whose path arguments are executed as code.
EXECUTING_HEADS = {"pytest"}
# The complete, fixed set of repository files a code-EXECUTING validator may be
# pointed at, each mapped to its FULL immutable dependency closure. Exact paths
# only: directory trust is not permitted, because a task whose allowed_paths
# cover a trusted directory could drop a new file there and have it executed
# with workflow credentials.
#
# The closure matters as much as the entry point: allowlisting a validator that
# imports a task-writable module would let the task's modified copy of that
# module execute with workflow credentials. Every file a validator loads must
# therefore be outside the task's writable scope.
VALIDATOR_DEPENDENCIES: dict[str, tuple[str, ...]] = {
    "scripts/ai/tests/test_auto_intake.py": (
        "scripts/ai/tests/test_auto_intake.py",
        "scripts/ai/auto_intake.py",
        "scripts/ai/deepseek_implementer.py",
        # Auto-loaded by the runner before the target executes.
        "conftest.py",
        "scripts/conftest.py",
        "scripts/ai/conftest.py",
        "scripts/ai/tests/conftest.py",
        # Every implicit pytest configuration source. `-c` suppresses these,
        # but they stay in the closure so the boundary does not depend on
        # pytest's config-precedence rules staying the same.
        "pytest.ini",
        ".pytest.ini",
        "pytest.toml",
        ".pytest.toml",
        "tox.ini",
        "setup.cfg",
        "pyproject.toml",
        "scripts/ai/tests/pytest.ini",
        "scripts/ai/tests/.pytest.ini",
        "scripts/ai/tests/pytest.toml",
        "scripts/ai/tests/.pytest.toml",
        "scripts/ai/tests/tox.ini",
        "scripts/ai/tests/setup.cfg",
        "scripts/ai/tests/pyproject.toml",
    ),
}

# The single configuration file an executing pytest validator may be pinned to.
# Passing `-c <file>` makes that file pytest's ONLY config source, so no
# task-writable pytest.ini / .pytest.ini / pytest.toml / .pytest.toml /
# pyproject.toml / tox.ini / setup.cfg can inject addopts such as `-p evil`.
TRUSTED_VALIDATOR_CONFIGS: frozenset[str] = frozenset({
    "scripts/ai/tests/pytest.ini",
})

# An executing test runner accepts ONLY these options. This is a strict
# allowlist, not a denylist: plugin and configuration injection has too many
# spellings (-p, -P, -c, --rootdir, --import-mode, --pyargs, --doctest-modules,
# discover, ...) for enumeration of the bad ones to ever be complete, and every
# one of them can execute task-authored Python before the named validator runs.
# Anything not listed here is refused, so a new pytest option cannot silently
# become an injection path.
PERMITTED_RUNNER_OPTIONS = {
    "-v", "-vv", "-q", "-qq", "-x",
    "--verbose", "--quiet", "--exitfirst",
}
PERMITTED_RUNNER_OPTION_PREFIXES = ("--maxfail=", "--tb=")


def is_permitted_runner_option(token: str) -> bool:
    if token in PERMITTED_RUNNER_OPTIONS:
        return True
    return token.startswith(PERMITTED_RUNNER_OPTION_PREFIXES)
TRUSTED_PYTHON_VALIDATORS: frozenset[str] = frozenset(VALIDATOR_DEPENDENCIES)


def validator_closure(item: str) -> tuple[str, ...]:
    """Every repository file executing `item` will load. Fail-closed default."""
    return VALIDATOR_DEPENDENCIES.get(item, (item,))
SHELL_META_CHARS = set(";|&`$<>(){}!*?[]~#\\\"'\n\r\t")
SHELL_KEYWORDS = {
    "if", "then", "else", "elif", "fi", "for", "while", "do", "done",
    "case", "esac", "function", "select", "time", "coproc", "in",
}
SHELL_INTERPRETERS = {"sh", "bash", "zsh", "dash", "ksh", "fish", "pwsh", "powershell", "cmd"}
NETWORK_WRITE_TOKENS = {"curl", "wget", "nc", "ncat", "telnet", "ssh", "scp", "sftp", "rsync", "ftp"}
GIT_WRITE_COMMANDS = {
    "add", "commit", "push", "merge", "rebase", "reset", "clean", "checkout",
    "switch", "restore", "fetch", "pull", "clone", "init", "tag", "branch",
    "remote", "submodule", "apply", "am", "cherry-pick", "revert", "stash",
    "gc", "prune", "filter-branch", "config", "update-ref", "worktree",
}
DEPLOY_COMMANDS = {
    "wrangler", "deploy", "serverless", "terraform", "kubectl", "helm",
    "docker", "docker-compose", "flyctl", "vercel", "netlify", "aws",
    "gcloud", "az",
}
ARBITRARY_EXECUTORS = {
    "eval", "exec", "source", ".", "xargs", "find", "perl", "ruby", "node",
    "deno", "go", "rustc", "gcc", "cc", "make", "npx", "npm", "yarn", "pnpm",
    "pip", "pip3", "poetry", "uv", "env", "sudo", "su", "chmod", "chown",
    "rm", "mv", "cp", "dd", "mkfifo", "tee",
}
FORBIDDEN_FLAGS = {"-c", "--command", "-e", "--eval", "--exec", "-i", "--interactive"}

MAX_VALIDATION_COMMAND_LEN = 500

STATUS_LABEL_PREFIX = "ai-status:"
VALID_STATUSES = ("RECEIVED", "READY", "FAILED", "DUPLICATE_SKIPPED")

RECEIPT_MARKER = "AUTO_INTAKE_RECEIPT"
RECEIPT_RE = re.compile(rf"{RECEIPT_MARKER}:\s*([A-Za-z0-9._-]{{3,64}})")

# Durable O(1) processed-task ledger. A GitHub label is permanent repository
# state: it never ages out of a pagination window and survives every fresh
# checkout, runner and restart.
RECEIPT_LABEL_PREFIX = "ai-intake-done:"
MAX_LABEL_LEN = 50
RECEIPT_LABEL_COLOR = "0e8a16"


class TaskError(Exception):
    """Per-issue, recoverable rejection. Never aborts the whole batch."""


class ReceiptRaceLost(Exception):
    """Another concurrent intake run created the durable receipt first."""


def fail(message: str) -> None:
    """Process-fatal, fail-closed abort."""
    print(f"AUTO_INTAKE_BLOCK: {message}", file=sys.stderr)
    raise SystemExit(2)


def reject(message: str) -> None:
    """Per-issue fail-closed rejection."""
    raise TaskError(message)


def normalize_path(value: str) -> str:
    value = value.strip().replace("\\", "/")
    while value.startswith("./"):
        value = value[2:]
    return value


def is_hard_forbidden_scope(item: str) -> bool:
    if item in HARD_FORBIDDEN_EXACT:
        return True
    return any(item.startswith(p) for p in HARD_FORBIDDEN_PREFIXES)


def is_broad_scope(item: str) -> bool:
    if item in BROAD_SCOPE_EXACT:
        return True
    first = item.split("/", 1)[0]
    return first in {"", ".", "..", "*", "**"} or "*" in first or "?" in first


def repo_safe_path(value) -> str | None:
    """Normalize a repository-relative path, or return None if it is unsafe.

    Rejects non-strings, absolute paths, `~` expansion, `..` traversal, glob
    scopes, hard-forbidden paths, and anything whose resolved real path escapes
    the repository ROOT (including via symlink).
    """
    if not isinstance(value, str):
        return None
    stripped = value.strip()
    if not stripped:
        return None
    if stripped.startswith("/") or stripped.startswith("~"):
        return None
    if any(ch in stripped for ch in "*?"):
        return None
    item = normalize_path(stripped)
    if not item or item in {".", ".."}:
        return None
    if ".." in item.split("/"):
        return None
    if is_hard_forbidden_scope(item):
        return None
    try:
        root = pathlib.Path(os.path.realpath(ROOT))
        resolved = pathlib.Path(os.path.realpath(ROOT / item))
    except Exception:
        return None
    if resolved != root and root not in resolved.parents:
        return None
    return item


def is_trusted_validator_path(item: str) -> bool:
    """Exact-match membership in the fixed validator allowlist. No prefixes."""
    return item in TRUSTED_PYTHON_VALIDATORS


def looks_like_path(token: str) -> bool:
    """Treat any non-flag token that names a file or directory as a path.

    Dotfiles such as `.env` and `cloudflare-worker/.dev.vars` must be caught
    here, so a bare `.` in the token is enough to demand a safety check.
    """
    if token.startswith("-"):
        return False
    return "/" in token or "." in token


def validate_allowed_scope(allowed: list) -> None:
    """Reject any allowed_paths entry that is hard-forbidden or repo-wide.

    BLOCKER 1: HARD_FORBIDDEN is enforced against every allowed_paths entry,
    including the concrete prefix of a `dir/**` scope.
    """
    if not isinstance(allowed, list) or not allowed:
        reject("allowed_paths must be a non-empty list")
    for raw in allowed:
        if not isinstance(raw, str):
            reject(f"allowed_paths entry must be a string: {raw!r}")
        stripped = raw.strip()
        if not stripped:
            reject("allowed_paths contains an empty entry")
        if stripped.startswith("/") or stripped.startswith("~"):
            reject(f"absolute allowed_paths entry rejected: {raw}")
        if any(stripped.startswith(p) and normalize_path(stripped) == "" for p in BROAD_SCOPE_PREFIXES):
            reject(f"overly broad allowed_paths entry: {raw}")
        item = normalize_path(stripped)
        if not item:
            reject(f"overly broad allowed_paths entry: {raw}")
        if ".." in item.split("/"):
            reject(f"path traversal in allowed_paths entry: {raw}")
        if is_hard_forbidden_scope(item):
            reject(f"forbidden allowed_paths entry: {raw}")
        if is_broad_scope(item):
            reject(f"overly broad allowed_paths entry: {raw}")
        prefix = item[:-3].rstrip("/") if item.endswith("/**") else item
        if not prefix:
            reject(f"overly broad allowed_paths entry: {raw}")
        if is_hard_forbidden_scope(prefix):
            reject(f"forbidden allowed_paths entry: {raw}")
        if is_broad_scope(prefix):
            reject(f"overly broad allowed_paths entry: {raw}")


def validate_context_files(context_files, issue_number: int) -> None:
    """BLOCKER 1: context_files must be safe, in-repo, regular files.

    Rejects absolute paths, `..` traversal, globs, hard-forbidden paths
    (`.git`, `.git/**`, `.env`, `cloudflare-worker/.dev.vars`), anything whose
    real path escapes ROOT (including via symlink), and anything that is not an
    existing regular file in this checkout.
    """
    if not isinstance(context_files, list):
        reject(f"issue #{issue_number} context_files must be a list")
    for raw in context_files:
        if not isinstance(raw, str) or not raw.strip():
            reject(f"issue #{issue_number} context_files must contain non-empty strings")
        item = repo_safe_path(raw)
        if item is None:
            reject(f"issue #{issue_number} unsafe context_files entry: {raw!r}")
        target = ROOT / item
        if target.is_symlink():
            reject(f"issue #{issue_number} context_files entry is a symlink: {raw!r}")
        if not target.is_file():
            reject(
                f"issue #{issue_number} context_files entry is not a regular "
                f"repository file: {raw!r}"
            )


def validate_forbidden_scope(forbidden: list) -> None:
    if not isinstance(forbidden, list):
        reject("forbidden_paths must be a list")
    for raw in forbidden:
        if not isinstance(raw, str) or not raw.strip():
            reject("forbidden_paths must contain non-empty strings")


def path_allowed(path: str, allowed: list, forbidden: list) -> bool:
    path = normalize_path(path)
    if is_hard_forbidden_scope(path):
        return False
    for raw in forbidden:
        item = normalize_path(str(raw))
        if not item:
            continue
        if path == item or path.startswith(item.rstrip("/") + "/"):
            return False
    for raw in allowed:
        item = normalize_path(str(raw))
        if not item:
            continue
        if item.endswith("/**"):
            prefix = item[:-3].rstrip("/")
            if path == prefix or path.startswith(prefix + "/"):
                return True
        elif path == item or path.startswith(item.rstrip("/") + "/"):
            return True
    return False


def contains_secret(text: str) -> bool:
    return any(pattern.search(text or "") for pattern in SECRET_PATTERNS)


def validate_validation_command(command, allowed: list | None = None,
                                forbidden: list | None = None) -> bool:
    """Return True only if command is a safe, bounded, non-write command.

    BLOCKER 4: strict allowlist / bounded grammar. No pipes, chaining,
    redirects, command substitution, shell interpreters, network writes,
    git writes, deploy commands or arbitrary executors.
    """
    if not isinstance(command, str) or not command.strip():
        return False
    if len(command) > MAX_VALIDATION_COMMAND_LEN:
        return False
    if any(ch in command for ch in SHELL_META_CHARS):
        return False
    if not SAFE_VALIDATION_GRAMMAR.match(command):
        return False
    tokens = command.split()
    if not tokens:
        return False
    head = tokens[0]
    if head in SHELL_INTERPRETERS or head in ARBITRARY_EXECUTORS:
        return False
    if head in NETWORK_WRITE_TOKENS or head in DEPLOY_COMMANDS:
        return False
    if head == "git":
        if len(tokens) < 2 or tokens[1] not in SAFE_VALIDATION_GIT_SUBCOMMANDS:
            return False
        if tokens[1] in GIT_WRITE_COMMANDS:
            return False
    elif head in {"python", "python3"}:
        # BLOCKER 2: never execute an arbitrary issue-selected .py file. Python
        # validation runs ONLY an allowlisted module.
        if len(tokens) < 3 or tokens[1] != "-m":
            return False
        if tokens[2] not in SAFE_PYTHON_MODULES:
            return False
    elif head not in SAFE_VALIDATION_COMMANDS:
        return False

    # Does this command EXECUTE the code it is pointed at?
    executes = head in EXECUTING_HEADS or (
        head in {"python", "python3"} and tokens[2] in EXECUTING_PYTHON_MODULES
    )
    if executes:
        # Arguments to the runner itself, excluding `-m <module>`.
        arg_tokens = tokens[3:] if head in {"python", "python3"} else tokens[1:]
        # A test runner with no explicit target auto-discovers tests from the
        # task-writable worktree, so `pytest`, `pytest -v` and
        # `python3 -m unittest` must be refused. Exactly one named target, and
        # it must be an immutable allowlisted validator.
        is_pytest = head == "pytest" or (
            head in {"python", "python3"} and tokens[2] == "pytest"
        )
        targets: list[str] = []
        config: str | None = None
        # Tokens consumed as pinned-config syntax; exempt from the generic
        # forbidden-flag and validator-target checks below because the parser
        # has already validated them against TRUSTED_VALIDATOR_CONFIGS.
        consumed: set[str] = set()
        index = 0
        while index < len(arg_tokens):
            token = arg_tokens[index]
            if token == "-c":
                if config is not None or index + 1 >= len(arg_tokens):
                    return False
                config = arg_tokens[index + 1]
                consumed.update({token, config})
                index += 2
                continue
            if token.startswith("-c="):
                if config is not None:
                    return False
                config = token[3:]
                consumed.update({token, config})
                index += 1
                continue
            if looks_like_path(token):
                targets.append(token)
                index += 1
                continue
            # Everything that is not the target or the pinned config must be an
            # explicitly permitted option. This stops `-p evil`, `--rootdir=…`,
            # `--import-mode=…`, `discover`, `--pyargs` and future equivalents.
            if not is_permitted_runner_option(token):
                return False
            index += 1
        if len(targets) != 1:
            return False
        if is_pytest:
            # pytest auto-loads config from the worktree unless pinned. Require
            # the pin, and require it to name the immutable trusted config.
            if config is None:
                return False
            config_path = normalize_path(config)
            if config_path not in TRUSTED_VALIDATOR_CONFIGS:
                return False
            if allowed is not None and path_allowed(
                config_path, allowed, forbidden or []
            ):
                return False
            consumed.add(config_path)
            config_tokens = consumed
        elif config is not None:
            return False
        else:
            config_tokens = set()

    config_tokens = config_tokens if executes else set()
    for token in tokens[1:]:
        if token in config_tokens:
            continue
        if not looks_like_path(token):
            continue
        item = repo_safe_path(token)
        if item is None:
            return False
        if executes:
            if not is_trusted_validator_path(item):
                return False
            # A validator the task itself may rewrite is task-authored code, not
            # a trusted validator. The same is true of anything the validator
            # IMPORTS, so the whole dependency closure must be outside the
            # task's writable scope. Refuse to run it with workflow creds.
            if allowed is not None:
                for dependency in validator_closure(item):
                    if path_allowed(dependency, allowed, forbidden or []):
                        return False

    for token in tokens[1:]:
        if token in config_tokens:
            continue
        if token in FORBIDDEN_FLAGS:
            return False
        if token in SHELL_KEYWORDS or token in SHELL_INTERPRETERS:
            return False
        if token in GIT_WRITE_COMMANDS or token in NETWORK_WRITE_TOKENS or token in DEPLOY_COMMANDS:
            return False
        if token in ARBITRARY_EXECUTORS:
            return False
    return True


def validate_numeric_field(value, field_name: str) -> int:
    """Return integer value or reject bool/string/float/list fail-closed.

    BLOCKER 8: type-check BEFORE any bounds logic.
    """
    if isinstance(value, bool) or not isinstance(value, int):
        reject(f"{field_name} must be an integer, got {type(value).__name__}")
    return value


def clamp(value: int, low: int, high: int) -> int:
    return max(low, min(value, high))


# --- GitHub transport -------------------------------------------------------


def github_request(
    method: str, url: str, body: dict | None = None, allow_fail: bool = False
) -> dict | list | None:
    if not GITHUB_TOKEN:
        if allow_fail:
            return None
        fail("GITHUB_TOKEN secret is unavailable")
    data = json.dumps(body).encode("utf-8") if body is not None else None
    req = urllib.request.Request(
        url, data=data,
        headers={
            "Authorization": f"Bearer {GITHUB_TOKEN}",
            "Accept": "application/vnd.github+json",
            "Content-Type": "application/json",
        },
        method=method,
    )
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            raw = resp.read().decode("utf-8")
            return json.loads(raw) if raw else None
    except urllib.error.HTTPError as exc:
        if allow_fail:
            return None
        detail = exc.read().decode("utf-8", errors="replace")[:800]
        fail(f"GitHub {method} {url} HTTP {exc.code}: {detail}")
    except Exception as exc:
        if allow_fail:
            return None
        fail(f"GitHub {method} {url} failed: {exc}")


def is_ai_task_issue(issue: dict) -> bool:
    if not isinstance(issue, dict):
        return False
    if "pull_request" in issue:
        return False
    return AI_TASK_MARKER in (issue.get("title") or "")


def list_ai_issues(max_pages: int = MAX_ISSUE_PAGES) -> list[dict]:
    """BLOCKER 7: paginated issue discovery (no silent first-100 truncation)."""
    collected: list[dict] = []
    truncated = True
    for page in range(1, max_pages + 1):
        url = f"{GITHUB_API}/repos/{REPO}/issues?state=open&per_page={PER_PAGE}&page={page}"
        batch = github_request("GET", url)
        if not isinstance(batch, list):
            fail("GitHub issues response is not a list")
        collected.extend(i for i in batch if isinstance(i, dict))
        if len(batch) < PER_PAGE:
            truncated = False
            break
    if truncated:
        fail(f"issue discovery exceeded {max_pages} pages; refusing to truncate silently")
    return [i for i in collected if is_ai_task_issue(i)]


def fetch_issue(number: int) -> dict:
    """BLOCKER 7: --issue N fetches issue N directly."""
    url = f"{GITHUB_API}/repos/{REPO}/issues/{int(number)}"
    issue = github_request("GET", url)
    if not isinstance(issue, dict) or not issue.get("number"):
        fail(f"issue #{number} could not be fetched")
    if "pull_request" in issue:
        fail(f"#{number} is a pull request, not an AI-TASK issue")
    if AI_TASK_MARKER not in (issue.get("title") or ""):
        fail(f"issue #{number} is not marked {AI_TASK_MARKER}")
    return issue


# --- durable idempotency (GitHub is the source of truth) --------------------


def receipt_label(task_id: str) -> str:
    """Deterministic, collision-safe durable ledger key for a task_id.

    Readable form when it fits GitHub's 50-character label limit, otherwise a
    stable truncation + sha256 suffix. Pure function: same task_id always maps
    to the same label, on every runner, forever.
    """
    readable = f"{RECEIPT_LABEL_PREFIX}{task_id}"
    if len(readable) <= MAX_LABEL_LEN:
        return readable
    digest = hashlib.sha256(task_id.encode("utf-8")).hexdigest()[:16]
    keep = MAX_LABEL_LEN - len(RECEIPT_LABEL_PREFIX) - len(digest) - 1
    return f"{RECEIPT_LABEL_PREFIX}{task_id[:keep]}~{digest}"


def github_request_status(method: str, url: str, body: dict | None = None) -> int:
    """Perform a request and return ONLY its HTTP status.

    Returns 0 when the request could not be completed at all. Never calls
    fail(): transport problems must stay inside the per-issue boundary.
    """
    if not GITHUB_TOKEN:
        return 0
    data = json.dumps(body).encode("utf-8") if body is not None else None
    req = urllib.request.Request(
        url, data=data,
        headers={
            "Authorization": f"Bearer {GITHUB_TOKEN}",
            "Accept": "application/vnd.github+json",
            "Content-Type": "application/json",
        },
        method=method,
    )
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            return int(resp.status)
    except urllib.error.HTTPError as exc:
        return int(exc.code)
    except Exception:
        return 0


def github_status_probe(url: str) -> int:
    """GET `url` and return the HTTP status only.

    Callers must treat anything other than an explicit 200/404 as
    INDETERMINATE and fail closed; never as "absent".
    """
    return github_request_status("GET", url)


def durable_receipt_present(task_id: str) -> bool:
    """BLOCKER 2: O(1) durable GitHub-backed processed check.

    Looks up a permanent repository label keyed by task_id. This is bounded
    (one request), deterministic, independent of how much issue/comment history
    has accumulated, and survives fresh checkouts and runner restarts.
    """
    name = urllib.parse.quote(receipt_label(task_id), safe="")
    code = github_status_probe(f"{GITHUB_API}/repos/{REPO}/labels/{name}")
    if code == 200:
        return True
    if code == 404:
        return False
    reject(
        f"durable receipt lookup for task_id `{task_id}` is INDETERMINATE "
        f"(HTTP {code}); failing closed rather than risking reprocessing"
    )


def issue_receipt_task_ids(issue_number: int) -> set[str]:
    """Receipt task_ids recorded on ONE issue.

    Bounded by that single issue's own comment count, so it can never age out
    the way a repo-wide history scan does. Secondary audit check only; the
    label ledger above is authoritative.
    """
    found: set[str] = set()
    for page in range(1, MAX_ISSUE_COMMENT_PAGES + 1):
        url = (
            f"{GITHUB_API}/repos/{REPO}/issues/{issue_number}/comments"
            f"?per_page={PER_PAGE}&page={page}"
        )
        batch = github_request("GET", url, allow_fail=True)
        if not isinstance(batch, list):
            break
        for comment in batch:
            if not isinstance(comment, dict):
                continue
            match = RECEIPT_RE.search(comment.get("body") or "")
            if match:
                found.add(match.group(1))
        if len(batch) < PER_PAGE:
            break
    return found


def local_receipt_exists(task_id: str) -> bool:
    return (ROOT / ".ai-intake" / f"{task_id}.json").is_file()


def task_already_processed(
    task_id: str, issue_number: int | None = None, seen: dict[str, int] | None = None
) -> bool:
    """Durable duplicate check. Fail-closed on any indeterminate answer."""
    if seen is not None and task_id in seen:
        return True
    if durable_receipt_present(task_id):
        return True
    if issue_number is not None and task_id in issue_receipt_task_ids(issue_number):
        return True
    return local_receipt_exists(task_id)


def create_receipt_label(task_id: str, issue_number: int) -> None:
    """BLOCKER 4: CLAIM the durable receipt; never merely observe it.

    Only the process whose POST actually creates the label (201) owns the task.
    A 422 means another concurrent run created it first -> we LOST the race and
    must become a duplicate. A later GET 200 is NOT proof of ownership, so it is
    never used to convert a failed claim into success.
    """
    name = receipt_label(task_id)
    code = github_request_status(
        "POST", f"{GITHUB_API}/repos/{REPO}/labels",
        {
            "name": name,
            "color": RECEIPT_LABEL_COLOR,
            "description": f"AUTO-INTAKE V1 processed task {task_id}"[:100],
        },
    )
    if code == 422:
        raise ReceiptRaceLost(
            f"durable receipt `{name}` already claimed by a concurrent run"
        )
    if code not in (200, 201):
        raise TaskError(
            f"durable receipt label `{name}` could not be claimed (HTTP {code})"
        )
    # Best-effort visibility only; never affects ownership.
    github_request(
        "POST", f"{GITHUB_API}/repos/{REPO}/issues/{issue_number}/labels",
        {"labels": [name]}, allow_fail=True,
    )


def post_receipt(issue_number: int, task: dict, task_file: pathlib.Path) -> None:
    """Human-readable audit comment. Best-effort; never gates ownership."""
    body = (
        f"{RECEIPT_MARKER}: {task['task_id']}\n"
        f"AUTO_INTAKE_ISSUE: {issue_number}\n"
        f"AUTO_INTAKE_BASE_SHA: {task['base_sha']}\n"
        f"AUTO_INTAKE_TASK_FILE: {task_file.relative_to(ROOT).as_posix()}\n"
    )
    url = f"{GITHUB_API}/repos/{REPO}/issues/{issue_number}/comments"
    # BLOCKER 5: audit trail only. Ownership is already established by the
    # durable claim, so a transport failure here must not undo it, escalate to
    # SystemExit, or abort the batch.
    if github_request("POST", url, {"body": body}, allow_fail=True) is None:
        print(
            f"AUTO_INTAKE_RECEIPT_AUDIT_DEGRADED: #{issue_number} "
            f"task_id={task['task_id']} (durable claim already held)",
            file=sys.stderr,
        )


def mark_processed(task: dict, issue_number: int) -> None:
    """Local cache only; never the sole source of truth."""
    state_dir = ROOT / ".ai-intake"
    state_dir.mkdir(parents=True, exist_ok=True)
    state_file = state_dir / f"{task['task_id']}.json"
    state = {
        "task_id": task["task_id"],
        "issue_number": issue_number,
        "base_sha": task["base_sha"],
        "status": "RECEIVED",
        "created_at": datetime.datetime.now(datetime.timezone.utc).isoformat(),
    }
    state_file.write_text(json.dumps(state, indent=2), encoding="utf-8")


# --- durable singular status ------------------------------------------------


def set_status_label(issue_number: int, status: str) -> None:
    """BLOCKER 6: exactly one ai-status:* label survives each transition."""
    target = f"{STATUS_LABEL_PREFIX}{status.lower()}"
    base = f"{GITHUB_API}/repos/{REPO}/issues/{issue_number}/labels"
    current = github_request("GET", f"{base}?per_page={PER_PAGE}", allow_fail=True)
    names: list[str] = []
    if isinstance(current, list):
        names = [c.get("name") for c in current if isinstance(c, dict) and c.get("name")]
    for name in names:
        if name.startswith(STATUS_LABEL_PREFIX) and name != target:
            quoted = urllib.parse.quote(name, safe="")
            github_request("DELETE", f"{base}/{quoted}", allow_fail=True)
    if target not in names:
        github_request("POST", base, {"labels": [target]}, allow_fail=True)


def report_status(issue_number: int, status: str, detail: str = "") -> None:
    if status not in VALID_STATUSES:
        raise TaskError(f"unknown intake status: {status}")
    url = f"{GITHUB_API}/repos/{REPO}/issues/{issue_number}/comments"
    body = f"**AUTO-INTAKE V1** status: `{status}`"
    if detail:
        body += f"\n\n{detail}"
    github_request("POST", url, {"body": body}, allow_fail=True)
    set_status_label(issue_number, status)


# --- task parsing / validation ----------------------------------------------


def extract_task_json(issue: dict) -> dict:
    body = issue.get("body") or ""
    number = issue.get("number")
    start = body.find(AI_TASK_JSON_BEGIN)
    end = body.find(AI_TASK_JSON_END)
    if start < 0 or end <= start:
        reject(f"issue #{number} missing AI_TASK_JSON block")
    if body.count(AI_TASK_JSON_BEGIN) != 1 or body.count(AI_TASK_JSON_END) != 1:
        reject(f"issue #{number} must contain exactly one AI_TASK_JSON block")
    raw = body[start + len(AI_TASK_JSON_BEGIN):end].strip()
    try:
        task = json.loads(raw)
    except Exception as exc:
        reject(f"issue #{number} invalid AI_TASK_JSON: {exc}")
    if not isinstance(task, dict):
        reject(f"issue #{number} AI_TASK_JSON must be an object")
    return task


def resolve_authoritative_head() -> str | None:
    """BLOCKER 3: current authoritative repository HEAD, or None.

    Local git is authoritative for the checkout the implementer will run in.
    Falls back to the repository's default-branch head on GitHub. Returning
    None means UNKNOWN, and every caller must fail closed on it.
    """
    try:
        proc = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            cwd=str(ROOT), capture_output=True, text=True, check=False, timeout=30,
        )
        sha = (proc.stdout or "").strip()
        if proc.returncode == 0 and re.fullmatch(r"[0-9a-f]{40}", sha):
            return sha
    except Exception:
        pass
    repo = github_request("GET", f"{GITHUB_API}/repos/{REPO}", allow_fail=True)
    branch = "main"
    if isinstance(repo, dict) and isinstance(repo.get("default_branch"), str):
        branch = repo["default_branch"]
    ref = github_request(
        "GET", f"{GITHUB_API}/repos/{REPO}/commits/{branch}", allow_fail=True
    )
    if isinstance(ref, dict) and re.fullmatch(r"[0-9a-f]{40}", str(ref.get("sha", ""))):
        return str(ref["sha"])
    return None


def validate_task(task: dict, issue_number: int, head_resolver=None) -> dict:
    missing = [k for k in REQUIRED_FIELDS if k not in task]
    if missing:
        reject(f"issue #{issue_number} task missing fields: {', '.join(missing)}")

    validate_allowed_scope(task["allowed_paths"])
    validate_forbidden_scope(task["forbidden_paths"])

    if not isinstance(task["acceptance_criteria"], list) or not task["acceptance_criteria"]:
        reject(f"issue #{issue_number} acceptance_criteria must be a non-empty list")
    if not isinstance(task["validation_commands"], list):
        reject(f"issue #{issue_number} validation_commands must be a list")
    for cmd in task["validation_commands"]:
        if not validate_validation_command(
            cmd, task["allowed_paths"], task["forbidden_paths"]
        ):
            reject(f"issue #{issue_number} unsafe validation command blocked: {cmd!r}")
    validate_context_files(task["context_files"], issue_number)
    if not isinstance(task["requires_claude"], bool):
        reject(f"issue #{issue_number} requires_claude must be a boolean")
    # AI LOOP V2 invariant: every engineering task carries an independent Claude
    # review. This only ever ADDS a required reviewer, so it cannot weaken the
    # gate; it replaces the same normalization the workflow used to do inline.
    task["requires_claude"] = True
    if not isinstance(task["auto_merge"], bool):
        reject(f"issue #{issue_number} auto_merge must be a boolean")
    if task["auto_merge"]:
        reject(f"issue #{issue_number} auto_merge is not permitted in AUTO-INTAKE V1")
    if not isinstance(task["base_sha"], str) or not re.fullmatch(r"[0-9a-f]{40}", task["base_sha"]):
        reject(f"issue #{issue_number} base_sha must be a 40-char hex SHA")
    resolver = head_resolver or resolve_authoritative_head
    head = resolver()
    if not isinstance(head, str) or not re.fullmatch(r"[0-9a-f]{40}", head or ""):
        reject(
            f"issue #{issue_number} authoritative HEAD could not be resolved; "
            f"failing closed rather than accepting an unverifiable base_sha"
        )
    if task["base_sha"] != head:
        reject(
            f"issue #{issue_number} STALE base_sha: declared {task['base_sha']} "
            f"but authoritative HEAD is {head}"
        )
    if not isinstance(task["task_id"], str) or not re.fullmatch(r"[A-Za-z0-9._-]{3,64}", task["task_id"]):
        reject(f"issue #{issue_number} task_id must be 3-64 chars of [A-Za-z0-9._-]")
    if not isinstance(task["objective"], str) or not task["objective"].strip():
        reject(f"issue #{issue_number} objective must be a non-empty string")
    if contains_secret(json.dumps(task)):
        reject(f"issue #{issue_number} task contains a potential secret")

    # Type-check BEFORE bounds logic; then clamp.
    task["max_rounds"] = clamp(validate_numeric_field(task["max_rounds"], "max_rounds"), 1, 4)
    task["max_output_tokens"] = clamp(
        validate_numeric_field(task["max_output_tokens"], "max_output_tokens"), 512, 8000
    )
    task["validation_commands"] = list(task["validation_commands"])[:10]
    task["context_files"] = list(task["context_files"])[:20]
    return task


def write_task_file(task: dict, issue_number: int) -> pathlib.Path:
    tasks_dir = ROOT / ".ai-intake" / "tasks"
    tasks_dir.mkdir(parents=True, exist_ok=True)
    task_file = tasks_dir / f"{task['task_id']}.json"
    payload = dict(task)
    payload["source_issue"] = issue_number
    task_file.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
    if not task_file.is_file():
        raise OSError(f"task file was not written: {task_file}")
    return task_file


# --- per-issue processing ---------------------------------------------------


def process_issue(issue: dict, seen: dict[str, int], head_resolver=None) -> dict:
    number = issue.get("number")
    task = extract_task_json(issue)
    task = validate_task(task, number, head_resolver=head_resolver)
    task_id = task["task_id"]

    if task_already_processed(task_id, issue_number=number, seen=seen):
        report_status(number, "DUPLICATE_SKIPPED", f"task_id `{task_id}` already processed")
        return {"status": "DUPLICATE_SKIPPED", "task_id": task_id, "issue_number": number}

    report_status(number, "RECEIVED", f"task_id `{task_id}` accepted")

    # BLOCKER 3: the task file must exist BEFORE the task is marked processed.
    task_file = write_task_file(task, number)
    # Durable ledger entry first, then the human-readable audit comment, then
    # the local cache. If the durable entry cannot be written we do not mark.
    create_receipt_label(task_id, number)
    post_receipt(number, task, task_file)
    mark_processed(task, number)
    seen[task_id] = number

    rel = task_file.relative_to(ROOT).as_posix()
    report_status(number, "READY", f"task file written to `{rel}`")
    return {
        "status": "READY",
        "task_id": task_id,
        "issue_number": number,
        "task_file": rel,
    }


def safe_report_status(issue_number, status: str, detail: str = "") -> None:
    """Report status without ever letting transport noise escape the boundary."""
    try:
        report_status(issue_number, status, detail)
    except BaseException as exc:  # noqa: BLE001 - contains SystemExit by design
        print(
            f"AUTO_INTAKE_STATUS_REPORT_FAILED: #{issue_number} {status}: {exc}",
            file=sys.stderr,
        )


def run_intake(issues: list[dict], seen: dict[str, int] | None = None,
               head_resolver=None) -> dict:
    """BLOCKER 5: one malformed issue never aborts the batch.

    `seen` is an in-batch memo only; durability comes from the GitHub ledger.
    """
    if seen is None:
        seen = {}
    results: list[dict] = []
    failures: list[dict] = []
    for issue in issues:
        number = issue.get("number") if isinstance(issue, dict) else None
        try:
            results.append(process_issue(issue, seen, head_resolver=head_resolver))
        except ReceiptRaceLost as exc:
            # BLOCKER 4: lost the durable claim to a concurrent run.
            print(f"AUTO_INTAKE_RACE_LOST: #{number}: {exc}", file=sys.stderr)
            results.append({
                "status": "DUPLICATE_SKIPPED",
                "issue_number": number,
                "detail": "durable receipt claimed by a concurrent run",
            })
            safe_report_status(number, "DUPLICATE_SKIPPED", str(exc))
        except SystemExit as exc:
            # BLOCKER 5: a transport-level fail() must not abort the batch.
            failures.append({"issue_number": number, "error": f"SystemExit: {exc.code}"})
            print(f"AUTO_INTAKE_ISSUE_ABORTED: #{number}: SystemExit {exc.code}", file=sys.stderr)
            safe_report_status(number, "FAILED", "AUTO-INTAKE transport failure; see workflow logs")
        except TaskError as exc:
            failures.append({"issue_number": number, "error": str(exc)})
            print(f"AUTO_INTAKE_ISSUE_REJECTED: #{number}: {exc}", file=sys.stderr)
            safe_report_status(number, "FAILED", f"AUTO-INTAKE rejected this task: {exc}")
        except Exception as exc:  # noqa: BLE001 - isolate any per-issue defect
            failures.append({"issue_number": number, "error": f"{type(exc).__name__}: {exc}"})
            print(f"AUTO_INTAKE_ISSUE_ERROR: #{number}: {exc}", file=sys.stderr)
            safe_report_status(number, "FAILED", "AUTO-INTAKE processing error; see workflow logs")
    ready = [r for r in results if r["status"] == "READY"]
    return {
        "status": "DONE",
        "processed": len(ready),
        "skipped": len(results) - len(ready),
        "failed": len(failures),
        "total": len(issues),
        "results": results,
        "failures": failures,
    }


def validate_task_file(path: pathlib.Path, expect_head: str) -> dict:
    """Re-apply the AUTO-INTAKE safety boundary to an already-materialized task.

    Used by the bounded repair path, where the task is rebuilt against a PR head
    rather than freshly intaken. Same validators, same fail-closed semantics, one
    pipeline — no second, weaker parser.
    """
    try:
        task = json.loads(path.read_text(encoding="utf-8"))
    except Exception as exc:
        fail(f"cannot read task file {path}: {exc}")
    if not isinstance(task, dict):
        fail(f"task file {path} must contain a JSON object")
    task = validate_task(task, 0, head_resolver=lambda: expect_head)
    path.write_text(json.dumps(task, indent=2, ensure_ascii=False), encoding="utf-8")
    return task


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--issue", type=int, default=None, help="Specific issue number to process")
    ap.add_argument("--validate-task-file", default=None,
                    help="Re-validate an existing task file through the same boundary")
    ap.add_argument("--expect-head", default=None,
                    help="Authoritative head the task file must be bound to")
    args = ap.parse_args()

    if args.validate_task_file:
        if not args.expect_head:
            fail("--validate-task-file requires --expect-head")
        try:
            task = validate_task_file(pathlib.Path(args.validate_task_file), args.expect_head)
        except TaskError as exc:
            fail(f"task file rejected by AUTO-INTAKE boundary: {exc}")
        print(json.dumps({
            "status": "TASK_FILE_VALIDATED",
            "task_id": task["task_id"],
            "base_sha": task["base_sha"],
        }))
        return

    if args.issue:
        issues = [fetch_issue(args.issue)]
    else:
        issues = list_ai_issues()

    if not issues:
        print(json.dumps({"status": "NO_AI_TASKS", "count": 0}))
        return

    summary = run_intake(issues)
    print(json.dumps(summary, ensure_ascii=False))
    if summary["failed"]:
        raise SystemExit(2)


if __name__ == "__main__":
    main()
