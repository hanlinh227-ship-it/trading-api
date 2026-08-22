#!/usr/bin/env python3
"""AUTO-INTAKE V1: GitHub Issue -> bounded pipeline task.

Discovers GitHub issues explicitly marked as AI-loop tasks, parses the
machine-readable AI_TASK_JSON block, validates scope and safety, enforces
idempotency, reports durable status to GitHub, and fails closed on any
underspecified or unsafe write task. Does not merge or deploy.
"""

from __future__ import annotations

import argparse
import json
import os
import pathlib
import re
import sys
import urllib.error
import urllib.request

ROOT = pathlib.Path(__file__).resolve().parents[2]

GITHUB_API = os.environ.get("GITHUB_API_URL", "https://api.github.com")
REPO = os.environ.get("GITHUB_REPOSITORY", "hanlinh227-ship-it/trading-api")
GITHUB_TOKEN = os.environ.get("GITHUB_TOKEN", "")

AI_TASK_MARKER = "[AI-TASK]"
AI_TASK_JSON_BEGIN = "AI_TASK_JSON_BEGIN"
AI_TASK_JSON_END = "AI_TASK_JSON_END"

REQUIRED_FIELDS = [
    "task_id", "base_sha", "objective", "allowed_paths",
    "forbidden_paths", "acceptance_criteria", "validation_commands",
    "max_rounds", "max_output_tokens", "requires_claude",
    "auto_merge", "context_files",
]

HARD_FORBIDDEN_PREFIXES = (".git/",)
HARD_FORBIDDEN_EXACT = {".env", "cloudflare-worker/.dev.vars"}

SECRET_PATTERNS = (
    re.compile(r"sk-[A-Za-z0-9_-]{20,}"),
    re.compile(r"DEEPSEEK_API_KEY\s*[:=]\s*[^$\s]+", re.I),
    re.compile(r"ANTHROPIC_API_KEY\s*[:=]\s*[^$\s]+", re.I),
    re.compile(r"OPENAI_API_KEY\s*[:=]\s*[^$\s]+", re.I),
)

DANGEROUS_SHELL = re.compile(
    r"(?:^|[;|&`])\s*(?:rm\s+-rf|git\s+reset\s+--hard|git\s+clean|git\s+push|git\s+commit|wrangler\s+deploy|curl\b.*(?:-X\s*(?:POST|PUT|PATCH|DELETE)|--request\s*(?:POST|PUT|PATCH|DELETE)))",
    re.I,
)

STATUS_LABEL_PREFIX = "ai-status:"


def fail(message: str) -> None:
    print(f"AUTO_INTAKE_BLOCK: {message}", file=sys.stderr)
    raise SystemExit(2)


def normalize_path(value: str) -> str:
    value = value.strip().replace("\\", "/")
    while value.startswith("./"):
        value = value[2:]
    return value


def path_allowed(path: str, allowed: list[str], forbidden: list[str]) -> bool:
    path = normalize_path(path)
    if path in HARD_FORBIDDEN_EXACT or any(path.startswith(p) for p in HARD_FORBIDDEN_PREFIXES):
        return False
    for raw in forbidden:
        item = normalize_path(str(raw))
        if path == item or path.startswith(item.rstrip("/") + "/"):
            return False
    for raw in allowed:
        item = normalize_path(str(raw))
        if item.endswith("/**"):
            prefix = item[:-3].rstrip("/")
            if path == prefix or path.startswith(prefix + "/"):
                return True
        elif path == item or path.startswith(item.rstrip("/") + "/"):
            return True
    return False


def contains_secret(text: str) -> bool:
    return any(pattern.search(text or "") for pattern in SECRET_PATTERNS)


def github_request(method: str, url: str, body: dict | None = None) -> dict | list | None:
    if not GITHUB_TOKEN:
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
        detail = exc.read().decode("utf-8", errors="replace")[:800]
        fail(f"GitHub {method} {url} HTTP {exc.code}: {detail}")
    except Exception as exc:
        fail(f"GitHub {method} {url} failed: {exc}")


def list_ai_issues() -> list[dict]:
    url = f"{GITHUB_API}/repos/{REPO}/issues?state=open&per_page=100"
    issues = github_request("GET", url)
    if not isinstance(issues, list):
        fail("GitHub issues response is not a list")
    return [i for i in issues if AI_TASK_MARKER in (i.get("title") or "")]


def extract_task_json(issue: dict) -> dict:
    body = issue.get("body") or ""
    start = body.find(AI_TASK_JSON_BEGIN)
    end = body.find(AI_TASK_JSON_END)
    if start < 0 or end <= start:
        fail(f"issue #{issue.get('number')} missing AI_TASK_JSON block")
    raw = body[start + len(AI_TASK_JSON_BEGIN):end].strip()
    try:
        task = json.loads(raw)
    except Exception as exc:
        fail(f"issue #{issue.get('number')} invalid AI_TASK_JSON: {exc}")
    if not isinstance(task, dict):
        fail(f"issue #{issue.get('number')} AI_TASK_JSON must be an object")
    return task


def validate_task(task: dict, issue_number: int) -> dict:
    missing = [k for k in REQUIRED_FIELDS if k not in task]
    if missing:
        fail(f"issue #{issue_number} task missing fields: {', '.join(missing)}")
    if not isinstance(task["allowed_paths"], list) or not task["allowed_paths"]:
        fail(f"issue #{issue_number} allowed_paths must be a non-empty list")
    if not isinstance(task["forbidden_paths"], list):
        fail(f"issue #{issue_number} forbidden_paths must be a list")
    if not isinstance(task["acceptance_criteria"], list) or not task["acceptance_criteria"]:
        fail(f"issue #{issue_number} acceptance_criteria must be a non-empty list")
    if not isinstance(task["validation_commands"], list):
        fail(f"issue #{issue_number} validation_commands must be a list")
    for cmd in task["validation_commands"]:
        if not isinstance(cmd, str) or not cmd.strip():
            fail(f"issue #{issue_number} validation_commands must contain non-empty strings")
        if DANGEROUS_SHELL.search(cmd):
            fail(f"issue #{issue_number} dangerous validation command blocked: {cmd}")
    if not isinstance(task["context_files"], list):
        fail(f"issue #{issue_number} context_files must be a list")
    if not isinstance(task["requires_claude"], bool):
        fail(f"issue #{issue_number} requires_claude must be a boolean")
    if not isinstance(task["auto_merge"], bool):
        fail(f"issue #{issue_number} auto_merge must be a boolean")
    if task["auto_merge"]:
        fail(f"issue #{issue_number} auto_merge is not permitted in AUTO-INTAKE V1")
    if not isinstance(task["base_sha"], str) or not re.fullmatch(r"[0-9a-f]{40}", task["base_sha"]):
        fail(f"issue #{issue_number} base_sha must be a 40-char hex SHA")
    if not isinstance(task["task_id"], str) or not re.fullmatch(r"[A-Za-z0-9._-]{3,64}", task["task_id"]):
        fail(f"issue #{issue_number} task_id must be 3-64 chars of [A-Za-z0-9._-]")
    if not isinstance(task["objective"], str) or not task["objective"].strip():
        fail(f"issue #{issue_number} objective must be a non-empty string")
    if contains_secret(json.dumps(task)):
        fail(f"issue #{issue_number} task contains a potential secret")
    # Fail closed: any code-changing task must declare explicit scope.
    if not task["allowed_paths"]:
        fail(f"issue #{issue_number} code-changing task requires explicit allowed_paths")
    # Normalize bounded fields.
    task["max_rounds"] = max(1, min(int(task.get("max_rounds", 2)), 4))
    task["max_output_tokens"] = max(512, min(int(task.get("max_output_tokens", 5000)), 8000))
    task["validation_commands"] = list(task["validation_commands"])[:10]
    task["context_files"] = list(task["context_files"])[:20]
    return task


def task_already_processed(task_id: str) -> bool:
    state_dir = ROOT / ".ai-intake"
    state_file = state_dir / f"{task_id}.json"
    return state_file.is_file()


def mark_processed(task: dict, issue_number: int) -> None:
    state_dir = ROOT / ".ai-intake"
    state_dir.mkdir(parents=True, exist_ok=True)
    state_file = state_dir / f"{task['task_id']}.json"
    state = {
        "task_id": task["task_id"],
        "issue_number": issue_number,
        "base_sha": task["base_sha"],
        "status": "RECEIVED",
        "created_at": __import__("datetime").datetime.utcnow().isoformat() + "Z",
    }
    state_file.write_text(json.dumps(state, indent=2), encoding="utf-8")


def report_status(issue_number: int, status: str, detail: str = "") -> None:
    url = f"{GITHUB_API}/repos/{REPO}/issues/{issue_number}/comments"
    body = f"**AUTO-INTAKE V1** status: `{status}`"
    if detail:
        body += f"\n\n{detail}"
    github_request("POST", url, {"body": body})
    # Update label to reflect durable status.
    label_url = f"{GITHUB_API}/repos/{REPO}/issues/{issue_number}/labels"
    github_request("POST", label_url, {"labels": [f"{STATUS_LABEL_PREFIX}{status.lower()}"]})


def write_task_file(task: dict, issue_number: int) -> pathlib.Path:
    tasks_dir = ROOT / ".ai-intake" / "tasks"
    tasks_dir.mkdir(parents=True, exist_ok=True)
    task_file = tasks_dir / f"{task['task_id']}.json"
    task_file.write_text(json.dumps(task, indent=2, ensure_ascii=False), encoding="utf-8")
    return task_file


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--issue", type=int, default=None, help="Specific issue number to process")
    args = ap.parse_args()

    issues = list_ai_issues()
    if args.issue:
        issues = [i for i in issues if i.get("number") == args.issue]
        if not issues:
            fail(f"issue #{args.issue} not found or not an AI-TASK")

    if not issues:
        print(json.dumps({"status": "NO_AI_TASKS", "count": 0}))
        return

    processed = 0
    for issue in issues:
        number = issue.get("number")
        try:
            task = extract_task_json(issue)
            task = validate_task(task, number)
            if task_already_processed(task["task_id"]):
                report_status(number, "DUPLICATE_SKIPPED", f"task_id `{task['task_id']}` already processed")
                continue
            report_status(number, "RECEIVED", f"task_id `{task['task_id']}` accepted")
            mark_processed(task, number)
            task_file = write_task_file(task, number)
            report_status(number, "READY", f"task file written to `{task_file.relative_to(ROOT)}`")
            print(json.dumps({
                "status": "READY",
                "task_id": task["task_id"],
                "issue_number": number,
                "task_file": str(task_file.relative_to(ROOT)),
            }, ensure_ascii=False))
            processed += 1
        except SystemExit:
            report_status(number, "FAILED", "AUTO-INTAKE validation failed; see workflow logs")
            raise
        except Exception as exc:
            report_status(number, "FAILED", f"unexpected error: {exc}")
            raise

    print(json.dumps({"status": "DONE", "processed": processed, "total": len(issues)}))


if __name__ == "__main__":
    main()
