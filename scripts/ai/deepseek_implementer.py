#!/usr/bin/env python3
"""Cloud-only DeepSeek implementer for GitHub Actions.

The worker receives a task spec from the repository, asks DeepSeek for ONE unified
patch, validates the patch paths against the task allow-list and project hard
prohibitions, then applies it to the Actions workspace. It never deploys and it
never writes secrets to disk.

This file is infrastructure only. It does not contain Trading decision logic.
"""

from __future__ import annotations

import argparse
import json
import os
import pathlib
import re
import subprocess
import sys
import tempfile
import urllib.error
import urllib.request

ROOT = pathlib.Path(__file__).resolve().parents[2]
API_URL = os.environ.get("DEEPSEEK_API_URL", "https://api.deepseek.com/chat/completions")
MODEL = os.environ.get("DEEPSEEK_MODEL", "deepseek-chat")

HARD_FORBIDDEN_PREFIXES = (
    ".git/",
)

HARD_FORBIDDEN_EXACT = {
    ".env",
    "cloudflare-worker/.dev.vars",
}

SECRET_PATTERNS = (
    re.compile(r"sk-[A-Za-z0-9_-]{20,}"),
    re.compile(r"DEEPSEEK_API_KEY\s*[:=]\s*[^$\s]+", re.I),
    re.compile(r"ANTHROPIC_API_KEY\s*[:=]\s*[^$\s]+", re.I),
    re.compile(r"OPENAI_API_KEY\s*[:=]\s*[^$\s]+", re.I),
)


def fail(message: str) -> None:
    print(f"DEEPSEEK_WORKER_BLOCK: {message}", file=sys.stderr)
    raise SystemExit(2)


def run(*args: str, input_text: str | None = None) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        list(args),
        cwd=ROOT,
        input=input_text,
        text=True,
        capture_output=True,
        check=False,
    )


def normalize_path(value: str) -> str:
    value = value.strip().replace("\\", "/")
    while value.startswith("./"):
        value = value[2:]
    return value


def path_allowed(path: str, allowed: list[str], forbidden: list[str]) -> bool:
    path = normalize_path(path)
    if path in HARD_FORBIDDEN_EXACT or any(path.startswith(p) for p in HARD_FORBIDDEN_PREFIXES):
        return False
    for item in forbidden:
        item = normalize_path(item)
        if path == item or path.startswith(item.rstrip("/") + "/"):
            return False
    for item in allowed:
        item = normalize_path(item)
        if item.endswith("/**"):
            prefix = item[:-3].rstrip("/")
            if path == prefix or path.startswith(prefix + "/"):
                return True
        elif path == item or path.startswith(item.rstrip("/") + "/"):
            return True
    return False


def patch_paths(patch: str) -> list[str]:
    paths: list[str] = []
    for line in patch.splitlines():
        if line.startswith("+++ b/") or line.startswith("--- a/"):
            p = line[6:].strip()
            if p != "/dev/null":
                paths.append(normalize_path(p))
    return sorted(set(paths))


def extract_patch(text: str) -> str:
    text = text.strip()
    fenced = re.search(r"```(?:diff|patch)?\s*(.*?)```", text, re.S | re.I)
    if fenced:
        text = fenced.group(1).strip()
    first = text.find("diff --git ")
    if first >= 0:
        text = text[first:]
    if "diff --git " not in text:
        fail("model response did not contain a unified git diff")
    return text.rstrip() + "\n"


def load_task(path: pathlib.Path) -> dict:
    try:
        task = json.loads(path.read_text(encoding="utf-8"))
    except Exception as exc:
        fail(f"cannot read task JSON: {exc}")
    required = ["task_id", "base_sha", "objective", "allowed_paths", "forbidden_paths", "acceptance_criteria"]
    missing = [k for k in required if not task.get(k)]
    if missing:
        fail("task missing fields: " + ", ".join(missing))
    if not isinstance(task["allowed_paths"], list) or not task["allowed_paths"]:
        fail("allowed_paths must be a non-empty list")
    return task


def collect_context(task: dict) -> str:
    max_chars = int(os.environ.get("DEEPSEEK_CONTEXT_MAX_CHARS", "180000"))
    chunks: list[str] = []
    used = 0
    for raw in task.get("context_files", []):
        rel = normalize_path(str(raw))
        p = ROOT / rel
        if not p.is_file():
            chunks.append(f"\n### {rel}\n[MISSING]\n")
            continue
        data = p.read_text(encoding="utf-8", errors="replace")
        room = max_chars - used
        if room <= 0:
            break
        data = data[:room]
        chunks.append(f"\n### {rel}\n{data}\n")
        used += len(data)
    return "".join(chunks)


def call_deepseek(task: dict, context: str) -> str:
    key = os.environ.get("DEEPSEEK_API_KEY")
    if not key:
        fail("DEEPSEEK_API_KEY secret is unavailable")

    system = """You are the primary implementation agent for a SIGNAL-ONLY Trading repository.\n"
    system += "Return exactly ONE unified git diff and no prose. Obey the task allow-list. "
    system += "Never expose secrets, never reset state, never weaken risk/freshness/structural-SL/news/execution protections, "
    system += "never restore Hyro auto-trade/Futures/TK2/Binance20 production execution, and never enable production Anthropic API.\n"
    system += "Do not claim tests, deployment, or live verification unless the task context explicitly contains real evidence; this worker only implements."

    user = {
        "task_id": task["task_id"],
        "base_sha": task["base_sha"],
        "objective": task["objective"],
        "allowed_paths": task["allowed_paths"],
        "forbidden_paths": task["forbidden_paths"],
        "acceptance_criteria": task["acceptance_criteria"],
        "instructions": task.get("instructions", []),
    }
    prompt = json.dumps(user, ensure_ascii=False, indent=2) + "\n\nREPOSITORY CONTEXT:\n" + context
    body = json.dumps(
        {
            "model": MODEL,
            "messages": [
                {"role": "system", "content": system},
                {"role": "user", "content": prompt},
            ],
            "temperature": 0.1,
            "stream": False,
        }
    ).encode("utf-8")
    req = urllib.request.Request(
        API_URL,
        data=body,
        headers={"Authorization": f"Bearer {key}", "Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=180) as resp:
            payload = json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")[:1000]
        fail(f"DeepSeek HTTP {exc.code}: {detail}")
    except Exception as exc:
        fail(f"DeepSeek request failed: {exc}")
    try:
        return payload["choices"][0]["message"]["content"]
    except Exception:
        fail("DeepSeek response missing choices[0].message.content")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("task_file")
    args = ap.parse_args()
    task_path = (ROOT / args.task_file).resolve()
    if ROOT not in task_path.parents:
        fail("task_file must be inside repository")
    task = load_task(task_path)

    head = run("git", "rev-parse", "HEAD")
    if head.returncode != 0:
        fail(head.stderr.strip() or "cannot read git HEAD")
    actual_sha = head.stdout.strip()
    if actual_sha != str(task["base_sha"]).strip():
        fail(f"stale task: base_sha={task['base_sha']} current={actual_sha}")

    context = collect_context(task)
    patch = extract_patch(call_deepseek(task, context))

    for pattern in SECRET_PATTERNS:
        if pattern.search(patch):
            fail("potential secret found in generated patch")

    changed = patch_paths(patch)
    if not changed:
        fail("generated patch contains no file paths")
    bad = [p for p in changed if not path_allowed(p, task["allowed_paths"], task["forbidden_paths"])]
    if bad:
        fail("patch touched paths outside scope: " + ", ".join(bad))

    with tempfile.NamedTemporaryFile("w", encoding="utf-8", suffix=".patch", delete=False) as f:
        f.write(patch)
        patch_file = f.name
    try:
        check = run("git", "apply", "--check", patch_file)
        if check.returncode != 0:
            fail("git apply --check failed: " + (check.stderr.strip() or check.stdout.strip()))
        apply = run("git", "apply", patch_file)
        if apply.returncode != 0:
            fail("git apply failed: " + (apply.stderr.strip() or apply.stdout.strip()))
    finally:
        pathlib.Path(patch_file).unlink(missing_ok=True)

    diff = run("git", "diff", "--name-only")
    if diff.returncode != 0:
        fail(diff.stderr.strip() or "cannot inspect resulting diff")
    resulting = [normalize_path(x) for x in diff.stdout.splitlines() if x.strip()]
    bad = [p for p in resulting if not path_allowed(p, task["allowed_paths"], task["forbidden_paths"])]
    if bad:
        run("git", "reset", "--hard", "HEAD")
        fail("resulting workspace touched paths outside scope: " + ", ".join(bad))

    print(json.dumps({"status": "IMPLEMENTED_NOT_VALIDATED", "task_id": task["task_id"], "files": resulting}, ensure_ascii=False))


if __name__ == "__main__":
    main()
