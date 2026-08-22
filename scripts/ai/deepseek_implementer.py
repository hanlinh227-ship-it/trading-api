#!/usr/bin/env python3
"""Bounded cloud-only DeepSeek implementation loop for GitHub Actions.

DeepSeek returns structured edits, never hand-written git patches. The worker
applies edits transactionally, lets git generate the diff, enforces scope and
secret guards, runs deterministic validation, and feeds failures back for
bounded repair. Fuzzy similarity is used only to select recovery context; every
replacement still requires old_text to match the current source exactly once.
"""

from __future__ import annotations

import argparse
import difflib
import json
import os
import pathlib
import re
import subprocess
import sys
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
EXACT_MATCH_ERROR = re.compile(
    r"STRUCTURED_EDIT_EXACT_MATCH_FAILED: edit=(\d+) path=([^\s]+) matches=(\d+) expected=1"
)


def fail(message: str) -> None:
    print(f"DEEPSEEK_WORKER_BLOCK: {message}", file=sys.stderr)
    raise SystemExit(2)


def run_shell(command: str, timeout: int = 180) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["bash", "-lc", command], cwd=ROOT, text=True,
        capture_output=True, timeout=timeout, check=False,
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


def contains_secret(text: str) -> bool:
    return any(pattern.search(text or "") for pattern in SECRET_PATTERNS)


def load_task(path: pathlib.Path) -> dict:
    try:
        task = json.loads(path.read_text(encoding="utf-8"))
    except Exception as exc:
        fail(f"cannot read task JSON: {exc}")
    required = [
        "task_id", "base_sha", "objective", "allowed_paths",
        "forbidden_paths", "acceptance_criteria",
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


def extract_json_object(text: str) -> dict:
    text = text.strip()
    fenced = re.search(r"```(?:json)?\s*(.*?)```", text, re.S | re.I)
    if fenced:
        text = fenced.group(1).strip()
    try:
        obj = json.loads(text)
    except Exception:
        start = text.find("{")
        end = text.rfind("}")
        if start < 0 or end <= start:
            raise ValueError("response did not contain a JSON object")
        try:
            obj = json.loads(text[start:end + 1])
        except Exception as exc:
            raise ValueError(f"invalid JSON response: {exc}") from exc
    if not isinstance(obj, dict):
        raise ValueError("response JSON must be an object")
    return obj


def validate_edit_spec(obj: dict, task: dict) -> list[dict]:
    edits = obj.get("edits")
    if not isinstance(edits, list) or not edits:
        raise ValueError("response must contain non-empty edits array")
    if len(edits) > 24:
        raise ValueError("too many edits; maximum is 24")
    clean: list[dict] = []
    for index, edit in enumerate(edits, start=1):
        if not isinstance(edit, dict):
            raise ValueError(f"edit {index} must be an object")
        op = str(edit.get("op", "replace")).strip().lower()
        path = normalize_path(str(edit.get("path", "")))
        if op not in {"replace", "create"}:
            raise ValueError(f"edit {index} has unsupported op={op}")
        if not path or not path_allowed(path, task["allowed_paths"], task["forbidden_paths"]):
            raise ValueError(f"edit {index} path outside scope: {path or '[EMPTY]'}")
        new_text = edit.get("new_text")
        if not isinstance(new_text, str):
            raise ValueError(f"edit {index} new_text must be a string")
        if contains_secret(new_text):
            raise ValueError(f"edit {index} may contain a secret")
        if op == "replace":
            old_text = edit.get("old_text")
            if not isinstance(old_text, str) or not old_text:
                raise ValueError(f"edit {index} replace requires non-empty old_text")
            clean.append({"op": op, "path": path, "old_text": old_text, "new_text": new_text})
        else:
            clean.append({"op": op, "path": path, "new_text": new_text})
    return clean


def apply_structured_edits(edits: list[dict]) -> tuple[bool, str]:
    """Apply all edits transactionally; no file is written unless every guard passes."""
    staged: dict[str, str] = {}
    existed: dict[str, bool] = {}
    try:
        for idx, edit in enumerate(edits, start=1):
            rel = edit["path"]
            path = ROOT / rel
            if rel not in staged:
                existed[rel] = path.is_file()
                staged[rel] = path.read_text(encoding="utf-8", errors="replace") if path.is_file() else ""
            if edit["op"] == "create":
                if existed[rel] or staged[rel]:
                    return False, f"STRUCTURED_EDIT_CREATE_EXISTS: edit={idx} path={rel}"
                staged[rel] = edit["new_text"]
                existed[rel] = True
                continue
            if not existed[rel]:
                return False, f"STRUCTURED_EDIT_REPLACE_MISSING_FILE: edit={idx} path={rel}"
            old_text = edit["old_text"]
            count = staged[rel].count(old_text)
            if count != 1:
                return False, f"STRUCTURED_EDIT_EXACT_MATCH_FAILED: edit={idx} path={rel} matches={count} expected=1"
            staged[rel] = staged[rel].replace(old_text, edit["new_text"], 1)
        for rel, data in staged.items():
            if contains_secret(data):
                return False, f"STRUCTURED_EDIT_RESULT_SECRET_GUARD: path={rel}"
        for rel, data in staged.items():
            path = ROOT / rel
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(data, encoding="utf-8")
        return True, ""
    except Exception as exc:
        return False, f"STRUCTURED_EDIT_APPLY_EXCEPTION: {exc}"


def recovery_excerpt(edit: dict, max_chars: int = 16000) -> str:
    """Return real nearby source for regeneration. Similarity selects context only."""
    rel = edit.get("path", "")
    path = ROOT / rel
    if edit.get("op") != "replace" or not path.is_file():
        return "[RECOVERY_SOURCE_UNAVAILABLE]"
    source = path.read_text(encoding="utf-8", errors="replace")
    src_lines = source.splitlines()
    old_lines = str(edit.get("old_text", "")).splitlines()
    if not src_lines:
        return "[RECOVERY_SOURCE_EMPTY]"

    # Prefer an exact distinctive line as an anchor.
    anchors = sorted(
        {line.strip() for line in old_lines if len(line.strip()) >= 16},
        key=len,
        reverse=True,
    )
    center = None
    for anchor in anchors[:12]:
        hits = [i for i, line in enumerate(src_lines) if anchor in line]
        if len(hits) == 1:
            center = hits[0]
            break

    # If no unique anchor exists, find the closest matching block of lines.
    if center is None and old_lines:
        matcher = difflib.SequenceMatcher(None, old_lines, src_lines, autojunk=False)
        blocks = [b for b in matcher.get_matching_blocks() if b.size > 0]
        if blocks:
            best = max(blocks, key=lambda b: b.size)
            center = best.b + max(0, best.size // 2)

    if center is None:
        center = min(len(src_lines) // 2, len(src_lines) - 1)

    radius = 90
    start = max(0, center - radius)
    end = min(len(src_lines), center + radius + 1)
    excerpt = "\n".join(f"{i + 1:06d}: {src_lines[i]}" for i in range(start, end))
    if len(excerpt) > max_chars:
        excerpt = excerpt[:max_chars]
    return f"PATH: {rel}\nLINES {start + 1}-{end}\n{excerpt}"


def exact_match_recovery_feedback(error: str, edits: list[dict]) -> str:
    match = EXACT_MATCH_ERROR.search(error)
    if not match:
        return error + "\nRegenerate structured edits from current repository context; old_text must match exactly once."
    index = int(match.group(1))
    if index < 1 or index > len(edits):
        return error + "\nRegenerate structured edits from current repository context; old_text must match exactly once."
    edit = edits[index - 1]
    excerpt = recovery_excerpt(edit)
    return (
        error
        + "\nEXACT_MATCH_RECOVERY_REQUIRED: The previous old_text was not present exactly once. "
          "Regenerate the failing edit using the REAL CURRENT SOURCE excerpt below. "
          "Copy old_text verbatim from this excerpt (without the numeric line prefixes). "
          "Do not use fuzzy replacement and do not broaden scope. Other edits may be regenerated if needed, "
          "but every replace old_text must match exactly once.\n\n"
        + excerpt
    )


def call_deepseek(task: dict, context: str, feedback: str, round_no: int) -> str:
    key = os.environ.get("DEEPSEEK_API_KEY")
    if not key:
        fail("DEEPSEEK_API_KEY secret is unavailable")
    system = (
        "You are the primary implementation agent for a SIGNAL-ONLY Trading repository.\n"
        "Return exactly ONE JSON object and no prose. Never return a git diff. Schema:\n"
        '{"edits":[{"op":"replace","path":"repo/path","old_text":"exact existing text","new_text":"replacement"},'
        '{"op":"create","path":"repo/path","new_text":"full new file"}]}\n'
        "For replace, old_text must be copied EXACTLY from supplied repository source and occur exactly once. "
        "If recovery feedback includes numbered source lines, copy source text without the numeric prefixes. "
        "Prefer small local replacements and multiple edits over rewriting a large file. "
        "Obey the task allow-list. Never expose secrets, reset state, weaken freshness, structural SL, RR, hard-news, execution authority, or protected risk controls. "
        "Never restore Hyro auto-trade, Futures Signal, TK2, Binance20 production execution, or production Anthropic API. "
        "Do not deploy or fabricate test/runtime evidence. Fix the root cause with the smallest coherent edits."
    )
    user = {
        "task_id": task["task_id"],
        "round": round_no,
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
    body = json.dumps({
        "model": MODEL,
        "messages": [
            {"role": "system", "content": system},
            {"role": "user", "content": prompt},
        ],
        "temperature": 0.1,
        "stream": False,
        "max_tokens": task["max_output_tokens"],
        "response_format": {"type": "json_object"},
    }).encode("utf-8")
    req = urllib.request.Request(
        API_URL, data=body,
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


def capture_untracked_files() -> set[str]:
    untracked = run_git("ls-files", "--others", "--exclude-standard")
    if untracked.returncode != 0:
        fail(untracked.stderr.strip() or "cannot inspect untracked files")
    return {normalize_path(x) for x in untracked.stdout.splitlines() if x.strip()}


def ensure_result_scope(task: dict, before_untracked: set[str]) -> list[str]:
    diff = run_git("diff", "--name-only")
    if diff.returncode != 0:
        fail(diff.stderr.strip() or "cannot inspect resulting diff")
    resulting = [normalize_path(x) for x in diff.stdout.splitlines() if x.strip()]
    after_untracked = capture_untracked_files()
    newly_untracked = after_untracked - before_untracked
    resulting.extend(sorted(newly_untracked))
    bad = [p for p in resulting if not path_allowed(p, task["allowed_paths"], task["forbidden_paths"])]
    if bad:
        fail("resulting workspace touched paths outside scope: " + ", ".join(bad))
    patch = current_diff(160000)
    if contains_secret(patch):
        fail("potential secret found in resulting diff")
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
    before_untracked = capture_untracked_files()

    for round_no in range(1, task["max_rounds"] + 1):
        response = call_deepseek(task, context, feedback, round_no)
        try:
            obj = extract_json_object(response)
            edits = validate_edit_spec(obj, task)
        except ValueError as exc:
            feedback = "STRUCTURED_EDIT_FORMAT_INVALID: " + str(exc)
            if round_no >= task["max_rounds"]:
                fail(feedback)
            continue

        ok, edit_error = apply_structured_edits(edits)
        if not ok:
            feedback = exact_match_recovery_feedback(edit_error, edits)
            if round_no >= task["max_rounds"]:
                fail(feedback)
            continue

        resulting = ensure_result_scope(task, before_untracked)
        if not resulting:
            feedback = "STRUCTURED_EDITS_APPLIED_BUT_NO_RESULTING_DIFF"
            if round_no >= task["max_rounds"]:
                fail(feedback)
            continue

        valid, last_validation = run_validations(task)
        if valid:
            print(json.dumps({
                "status": "IMPLEMENTED_VALIDATED",
                "task_id": task["task_id"],
                "rounds_used": round_no,
                "files": resulting,
                "validation": "PASS" if task["validation_commands"] else "NOT_DECLARED",
                "transport": "STRUCTURED_EDITS_V1_EXACT_RECOVERY",
            }, ensure_ascii=False))
            return
        feedback = "VALIDATION_FAILED:\n" + last_validation

    fail("max rounds exhausted without passing validation: " + last_validation[-6000:])


if __name__ == "__main__":
    main()
