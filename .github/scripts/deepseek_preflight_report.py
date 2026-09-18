"""Print the non-sensitive parts of a DeepSeek preflight response, and nothing else.

The preflight workflow could inline this, but a response body is exactly the
place an unexpected field turns up, and `cat`-ing one into a public Actions log
is how a token ends up in a build artifact. So the body never reaches the log:
this reads it, names the handful of fields that are safe, and prints those.

Anything not named here is dropped. That is the point - a denylist would have to
anticipate what a provider might add, and an allowlist does not.

Usage: deepseek_preflight_report.py {models|usage|error} <path.json>
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

#: Usage counters worth reporting. Integers the provider reports about billing
#: and cache behaviour; none of them can carry a credential.
USAGE_FIELDS = (
    "prompt_tokens",
    "completion_tokens",
    "total_tokens",
    "prompt_cache_hit_tokens",
    "prompt_cache_miss_tokens",
)


def _load(path: str) -> dict | None:
    try:
        document = json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        print("response_not_json=true")
        return None
    return document if isinstance(document, dict) else None


def report_models(document: dict) -> None:
    ids = sorted(
        str(row.get("id"))
        for row in document.get("data") or []
        if isinstance(row, dict) and row.get("id")
    )
    print(f"model_count={len(ids)}")
    for model_id in ids:
        print(f"model_id={model_id}")


def report_usage(document: dict) -> None:
    usage = document.get("usage") or {}
    for field in USAGE_FIELDS:
        if isinstance(usage.get(field), int):
            print(f"{field}={usage[field]}")
    served = document.get("model")
    if isinstance(served, str):
        print(f"model_served={served}")
    # The generated text is deliberately not printed. It is the model's output,
    # not evidence about the lane, and printing it buys nothing.


def report_error(document: dict) -> None:
    error = document.get("error")
    error = error if isinstance(error, dict) else {}
    # Type and code only. An error *message* is provider-authored free text and
    # can echo request content back, so it does not go to the log.
    print(f"error_type={error.get('type', 'unknown')}")
    print(f"error_code={error.get('code', 'unknown')}")


def main(argv: list[str]) -> int:
    if len(argv) != 3 or argv[1] not in {"models", "usage", "error"}:
        print("usage: deepseek_preflight_report.py {models|usage|error} <path.json>")
        return 2
    document = _load(argv[2])
    if document is None:
        return 0
    {"models": report_models, "usage": report_usage, "error": report_error}[argv[1]](document)
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
