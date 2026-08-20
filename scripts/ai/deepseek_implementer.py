#!/usr/bin/env python3
"""Bounded cloud-only DeepSeek implementation loop for GitHub Actions.

Reads one JSON task spec, calls DeepSeek for a scoped unified diff, applies it,
runs deterministic validation commands, and feeds failures back to DeepSeek for
bounded repair rounds. It never commits, pushes, merges, deploys, or writes
secrets. GitHub Actions owns those lifecycle operations.
"""

from __future__ import annotations

import argparse
import json
import os
import pathlib
import re
import shlex
import subprocess
import sys
import tempfile
import urllib.error
import urllib.request

ROOT = pathlib.Path(__file__).resolve().parents[2]
API_URL = os.environ.get("DEEPSEEK_API_URL", "https://api.deepseek.com/chat/completions")
MODEL = os.environ.get("DEEPSEEK_MODEL", "deepseek-chat")

HARD_FORBIDDEN_PREFIXES = (".git/",)
HARD_FORBIDDEN_EXACT = {".env", "cloudflare-worker/.dev.vars"}
SECRET_PATTERNS = (
    re.compile(r"sk-[A-Za-z0-9_-]{20,}"),
    re.compile(r"DEEPSEEK_API_KEY\s*[:=]\s*[^$\s]+", re.I),
    re.compile(r"ANTHROPIC_API_KEY\s*[:=]\s*[^$\s]+", re.I),
    re.compile(r"OPENAI_API_KEY\s*[:=]\s*[^$\s]+", re.I),
)
DANGEROUS_VALIDATION = re.compile(
    r"\b(rm\s+-rf|git\s+reset\s+--hard|git\s+clean|git\s+push|git\s+commit|wrangler\s+deploy|curl\b.*(?:-X\s*(?:POST|PUT|PATCH|DELETE)|--request\s*(?:POST|PUT|PATCH|DELETE)))",
    re.I,
)


def fail(message: str) -> None:
    print(f"DEEPSEEK_WORKER_BLOCK: {message}", file=sys.stderr)
    raise SystemExit(2)


def run_shell(command: str, timeout: int = 180) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["bash", "-lc", command],
        cwd=ROOT,
        text=True,
        capture_output=True,
        timeout=timeout,
        check=False,
    )


def run_git(*args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["git", *args], cwd=ROOT, text=True, capture_output=True, check=False
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


def patch_paths(patch: str) -> list[str]:
    paths: list[str] = []
    for line in patch.splitlines():
        if line.startswith("+++ b/") or line.startswith("--- a/"):
            p = line[6:].strip()
            if p != "/dev/null":
                paths.append(normalize_path(p))
    return sorted(set(paths))


def extract_patch(text: str) -> str:
    """Extract either git-style or standard a/b unified diff without accepting prose-only output."""
    text = text.strip()
    fenced = re.search(r"```(?:diff|patch)?\s*(.*?)```", text, re.S | re.I)
    if fenced:
        text = fenced.group(1).strip()

    git_start = text.find("diff --git ")
    if git_start >= 0:
        return text[git_start:].rstrip() + "\n"

    standard = re.search(r"(?m)^--- a/[^\n]+\n\+\+\+ b/[^\n]+", text)
    if standard:
        return text[standard.start():].rstrip() + "\n"

    raise ValueError("model response did not contain a unified git diff")


def load_task(path: pathlib.Path) -> dict:
    try:
        task = json.loads(path.read_text(encoding="utf-8"))
    except Exception as exc:
        fail(f"cannot read task JSON: {exc}")
    required = [
        "task_id",
        "base_sha",
        "objective",
        "allowed_paths",
        "forbidden_paths",
        "acceptance_criteria",
    ]
    missing = [k for k in required if not task.get(k)]
    if missing:
        fail("task missing fields: " + ", ".join(missing))
    if not isinstance(task["allowed_paths"], list) or not task["allowed_paths"]:
        fail("allowed_paths must be a non-empty list")
    if not isinstance(task["forbidden_paths"], list):
        fail("forbidden_paths must be a list")
    if not isinstance(task["acceptance_criteria"], list) or not task["acceptance_criteria"]:
        fail("acceptance_criteria must be a non-empty list")
    task["max_rounds"] = max(1, min(int(task.get("max_rounds", 2)), 4))
    task["max_output_tokens"] = max(512, min(int(task.get("max_output_tokens", 5000)), 8000))
    task["max_patch_regeneration_attempts"] = max(
        0, min(int(task.get("max_patch_regeneration_attempts", 1)), 1)
    )
    task["validation_commands"] = list(task.get("validation_commands") or [])[:10]
    for cmd in task["validation_commands"]:
        if not isinstance(cmd, str) or not cmd.strip():
            fail("validation_commands must contain non-empty strings")
        if DANGEROUS_VALIDATION.search(cmd):
            fail("dangerous validation command blocked: " + cmd)
    return task


def collect_context(task: dict) -> str:
    max_chars = max(10000, min(int(task.get("context_max_chars", 160000)), 220000))
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


def current_diff(max_chars: int = 80000) -> str:
    p = run_git("diff", "--no-ext-diff", "--unified=3")
    if p.returncode != 0:
        return "[DIFF_UNAVAILABLE]"
    return p.stdout[-max_chars:]


def call_deepseek(
    task: dict,
    context: str,
    feedback: str,
    round_no: int,
    generation_attempt: int = 1,
) -> str:
    key = os.environ.get("DEEPSEEK_API_KEY")
    if not key:
        fail("DEEPSEEK_API_KEY secret is unavailable")
    system = (
        "You are the primary implementation agent for a SIGNAL-ONLY Trading repository.\n"
        "Return exactly ONE complete unified git diff and no prose. The response must begin with either 'diff --git a/' or '--- a/' and use a/ and b/ repository paths. "
        "Every hunk header/count must be internally consistent and the complete patch must pass git apply --check. Never return a partial/truncated patch. "
        "If patch-format feedback is present, regenerate the ENTIRE patch from scratch rather than returning a fragment or explanation. "
        "Obey the task allow-list. Never expose secrets, never reset state, never weaken freshness, structural SL, RR, hard-news, execution authority, "
        "or protected risk controls. Never restore Hyro auto-trade, Futures Signal, TK2, Binance20 production execution, "
        "or production Anthropic API. Do not deploy. Do not fabricate test or runtime evidence.\n"
        "Fix the root cause with the smallest coherent patch. A failed validation is evidence to repair, not permission to weaken safeguards."
    )
    user = {
        "task_id": task["task_id"],
        "round": round_no,
        "generation_attempt": generation_attempt,
        "max_rounds": task["max_rounds"],
        "objective": task["objective"],
        "allowed_paths": task["allowed_paths"],
        "forbidden_paths": task["forbidden_paths"],
        "acceptance_criteria": task["acceptance_criteria"],
        "instructions": task.get("instructions", []),
        "review_feedback": task.get("review_feedback") or None,
        "validation_feedback": feedback or None,
    }
    prompt = json.dumps(user, ensure_ascii=False, indent=2)
    if round_no == 1:
        prompt += "\n\nREPOSITORY CONTEXT:\n" + context
    else:
        prompt += "\n\nCURRENT WORKING DIFF:\n" + current_diff()
        prompt += "\n\nRELEVANT REPOSITORY CONTEXT:\n" + context
    body = json.dumps(
        {
            "model": MODEL,
            "messages": [
                {"role": "system", "content": system},
                {"role": "user", "content": prompt},
            ],
            "temperature": 0.1,
            "stream": False,
            "max_tokens": task["max_output_tokens"],
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
        detail = exc.read().decode("utf-8", errors="replace")[:1200]
        fail(f"DeepSeek HTTP {exc.code}: {detail}")
    except Exception as exc:
        fail(f"DeepSeek request failed: {exc}")
    try:
        return payload["choices"][0]["message"]["content"]
    except Exception:
        fail("DeepSeek response missing choices[0].message.content")


def verify_patch_scope(patch: str, task: dict) -> None:
    for pattern in SECRET_PATTERNS:
        if pattern.search(patch):
            fail("potential secret found in generated patch")
    changed = patch_paths(patch)
    if not changed:
        fail("generated patch contains no file paths")
    bad = [p for p in changed if not path_allowed(p, task["allowed_paths"], task["forbidden_paths"])]
    if bad:
        fail("patch touched paths outside scope: " + ", ".join(bad))


def apply_patch(patch: str) -> tuple[bool, str]:
    with tempfile.NamedTemporaryFile("w", encoding="utf-8", suffix=".patch", delete=False) as f:
        f.write(patch)
        patch_file = f.name
    try:
        check = run_shell("git apply --check " + shlex.quote(patch_file), timeout=60)
        if check.returncode != 0:
            return False, (check.stderr or check.stdout)[-5000:]
        applied = run_shell("git apply " + shlex.quote(patch_file), timeout=60)
        if applied.returncode != 0:
            return False, (applied.stderr or applied.stdout)[-5000:]
        return True, ""
    finally:
        pathlib.Path(patch_file).unlink(missing_ok=True)


def ensure_result_scope(task: dict) -> list[str]:
    diff = run_git("diff", "--name-only")
    if diff.returncode != 0:
        fail(diff.stderr.strip() or "cannot inspect resulting diff")
    resulting = [normalize_path(x) for x in diff.stdout.splitlines() if x.strip()]
    bad = [p for p in resulting if not path_allowed(p, task["allowed_paths"], task["forbidden_paths"])]
    if bad:
        fail("resulting workspace touched paths outside scope: " + ", ".join(bad))
    return resulting


def run_validations(task: dict) -> tuple[bool, str]:
    commands = task["validation_commands"]
    if not commands:
        return True, "NO_VALIDATION_COMMANDS_DECLARED"
    logs: list[str] = []
    for cmd in commands:
        p = run_shell(cmd, timeout=min(int(task.get("validation_timeout_sec", 180)), 300))
        logs.append(f"$ {cmd}\nexit={p.returncode}\n{(p.stdout + p.stderr)[-9000:]}")
        if p.returncode != 0:
            return False, "\n\n".join(logs)[-18000:]
    return True, "\n\n".join(logs)[-18000:]


def generate_and_apply_patch(
    task: dict,
    context: str,
    feedback: str,
    round_no: int,
) -> tuple[bool, str]:
    """Generate a patch and allow one bounded full-regeneration attempt for format/apply failures."""
    max_attempts = 1 + task["max_patch_regeneration_attempts"]
    attempt_feedback = feedback

    for generation_attempt in range(1, max_attempts + 1):
        response = call_deepseek(
            task,
            context,
            attempt_feedback,
            round_no,
            generation_attempt=generation_attempt,
        )
        try:
            patch = extract_patch(response)
        except ValueError:
            attempt_feedback = (
                "PATCH_FORMAT_REGEN_REQUIRED: previous response was not a complete unified diff. "
                "Regenerate the entire patch from scratch. Return exactly one patch only, beginning with "
                "'diff --git a/' or '--- a/', using repository-relative a/ and b/ paths."
            )
            if generation_attempt < max_attempts:
                continue
            return False, attempt_feedback

        verify_patch_scope(patch, task)
        ok, apply_error = apply_patch(patch)
        if ok:
            return True, ""

        attempt_feedback = (
            "PATCH_APPLY_REGEN_REQUIRED:\n"
            + apply_error
            + "\nRegenerate the ENTIRE patch from scratch. Do not return a fragment. "
            "Ensure all @@ hunk ranges/counts match the supplied repository context and that the final patch passes git apply --check."
        )
        if generation_attempt < max_attempts:
            continue
        return False, attempt_feedback

    return False, "PATCH_GENERATION_UNREACHABLE"


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("task_file")
    args = ap.parse_args()
    task_path = (ROOT / args.task_file).resolve()
    if ROOT not in task_path.parents:
        fail("task_file must be inside repository")
    task = load_task(task_path)

    head = run_git("rev-parse", "HEAD")
    if head.returncode != 0:
        fail(head.stderr.strip() or "cannot read git HEAD")
    actual_sha = head.stdout.strip()
    if actual_sha != str(task["base_sha"]).strip():
        fail(f"stale task: base_sha={task['base_sha']} current={actual_sha}")

    context = collect_context(task)
    feedback = str(task.get("review_feedback") or "")
    last_validation = ""
    rounds_used = 0

    for round_no in range(1, task["max_rounds"] + 1):
        rounds_used = round_no
        ok, patch_feedback = generate_and_apply_patch(task, context, feedback, round_no)
        if not ok:
            fail(patch_feedback)

        resulting = ensure_result_scope(task)
        if not resulting:
            feedback = "PATCH_APPLIED_BUT_NO_RESULTING_DIFF"
            if round_no >= task["max_rounds"]:
                fail(feedback)
            continue

        valid, last_validation = run_validations(task)
        if valid:
            print(
                json.dumps(
                    {
                        "status": "IMPLEMENTED_VALIDATED",
                        "task_id": task["task_id"],
                        "rounds_used": rounds_used,
                        "files": resulting,
                        "validation": "PASS" if task["validation_commands"] else "NOT_DECLARED",
                    },
                    ensure_ascii=False,
                )
            )
            return
        feedback = "VALIDATION_FAILED:\n" + last_validation

    fail("max rounds exhausted without passing validation: " + last_validation[-6000:])


if __name__ == "__main__":
    main()
