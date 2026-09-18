#!/usr/bin/env python3
"""Apply one narrowly-scoped DeepSeek coding response after fail-closed validation."""

from __future__ import annotations

import json
import sys
from pathlib import Path, PurePosixPath


ALLOWED_FILES = {
    "AI_SKILL_LIBRARY/v4/survival/policy.yaml",
    "AI_SKILL_LIBRARY/v4/survival/policy_adapter.py",
    "AI_SKILL_LIBRARY/v4/survival/secrets.py",
    "AI_SKILL_LIBRARY/tests/test_survival_policy.py",
    "AI_SKILL_LIBRARY/tests/test_survival_secrets.py",
}


def reject(reason: str) -> "None":
    print(f"DEEPSEEK_OUTPUT_REJECTED={reason}", file=sys.stderr)
    raise SystemExit(1)


def main() -> int:
    if len(sys.argv) != 3:
        reject("usage")
    response_path = Path(sys.argv[1])
    root = Path(sys.argv[2]).resolve()
    try:
        response = json.loads(response_path.read_text(encoding="utf-8"))
        choice = response["choices"][0]
        content = choice["message"]["content"]
        if not isinstance(content, str):
            reject("missing_content")
        stripped = content.strip()
        if stripped.startswith("```"):
            first_newline = stripped.find("\n")
            if first_newline < 0 or not stripped.endswith("```"):
                reject("invalid_fence")
            stripped = stripped[first_newline + 1 : -3].strip()
        try:
            payload = json.loads(stripped)
        except json.JSONDecodeError:
            object_start = stripped.find("{")
            if object_start < 0:
                raise
            payload, _ = json.JSONDecoder().raw_decode(stripped[object_start:])
        files = payload["files"]
    except (OSError, KeyError, IndexError, TypeError, json.JSONDecodeError):
        reject("invalid_response")
    if not isinstance(files, dict):
        reject("invalid_files")
    provided = set(files)
    unexpected = provided - ALLOWED_FILES
    if unexpected:
        reject("path_not_allowed")
    if provided != ALLOWED_FILES:
        reject("file_set_mismatch")
    for relative, file_content in files.items():
        path = PurePosixPath(relative)
        if path.is_absolute() or ".." in path.parts or not isinstance(file_content, str):
            reject("invalid_file")
        target = root.joinpath(*path.parts)
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(file_content, encoding="utf-8")
    usage = response.get("usage") or {}
    print(f"DEEPSEEK_FINISH_REASON={response['choices'][0].get('finish_reason', 'unknown')}")
    prompt_tokens = int(usage.get("prompt_tokens") or 0)
    completion_tokens = int(usage.get("completion_tokens") or 0)
    print(f"DEEPSEEK_USAGE_PROMPT_TOKENS={prompt_tokens}")
    print(f"DEEPSEEK_USAGE_COMPLETION_TOKENS={completion_tokens}")
    conservative_usd = prompt_tokens / 1_000_000 + completion_tokens * 2 / 1_000_000
    print(f"DEEPSEEK_SPEND_ESTIMATE_USD_LE={conservative_usd:.6f}")
    print("DEEPSEEK_OUTPUT_APPLIED=PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
