#!/usr/bin/env python3
"""Apply one narrowly-scoped DeepSeek coding response after fail-closed validation.

Four lane runs reported ``DEEPSEEK_API_HEALTH=PASS`` and then died on
``invalid_response``, which named nothing: the previous version wrapped the
whole parse in one ``except`` that collapsed a truncated body, a missing key, an
unreadable file and a type error into the same verdict, and printed
``finish_reason`` and the token counts only on the success path. So the one
number that distinguishes "the provider misbehaved" from "the reply did not fit
in max_tokens" was never printed on the runs that needed it.

This version inverts that. Diagnostics are recorded *before* the payload is
parsed, every rejection carries its own reason code, and the envelope is
validated separately from the payload inside it - a healthy provider returning
an unusable body is a different fact from an unhealthy provider, and the lane
log now says which happened:

    DEEPSEEK_API_HEALTH=PASS   with   DEEPSEEK_PAYLOAD_VALID=FAIL

Nothing about the response body is ever printed. The reason codes are a closed
vocabulary defined here, the diagnostics are counts and enum values, and the
only per-file information that reaches the log is a path already on the
allowlist. A response body is exactly where an unexpected field turns up, and a
public Actions log is exactly where a token should not.

Writes are all-or-nothing. The previous version validated file contents inside
the write loop, so a bad fifth file left four already written to the working
tree - a partial application the ownership guard would then have to catch.
Every file is validated first; nothing is written until the full allowlisted set passes.

Usage: deepseek_lane_apply.py <response.json> <repo-root>
"""

from __future__ import annotations

import json
import sys
from pathlib import Path, PurePosixPath

#: The lane's entire remit for the current bounded task. Exact paths only.
ALLOWED_FILES = {
    "AI_SKILL_LIBRARY/v4/tools/survival_plane_proof.py",
    "AI_SKILL_LIBRARY/tests/test_survival_plane_proof.py",
}

#: Closed vocabulary. A reason is produced here and never interpolates any part
#: of the response, so a rejection cannot echo the body it rejected.
REASONS = (
    "usage",
    "response_unreadable",
    "response_not_json",
    "envelope_not_object",
    "envelope_no_choices",
    "envelope_choice_malformed",
    "content_missing",
    "content_not_string",
    "content_empty",
    "content_truncated",
    "invalid_fence",
    "payload_not_json",
    "payload_not_object",
    "files_missing",
    "files_not_object",
    "file_set_mismatch",
    "path_not_allowed",
    "path_traversal",
    "file_content_not_string",
)

#: A finish_reason the provider uses to say the reply was cut off. This is the
#: distinction four runs needed and could not make: a truncated body is not a
#: malformed one, and the fix for it is max_tokens, not the parser.
TRUNCATING_FINISH_REASONS = frozenset({"length", "max_tokens"})

#: Every finish_reason this lane will repeat into a public log. `finish_reason`
#: is provider-authored free text, and printing it verbatim is how a response
#: body reaches the Actions log through a field that looked like an enum - the
#: same allowed-but-unbounded mistake this repository has now made three times.
#: An unrecognised value is reported as `other`, which is all the lane needs to
#: know about it.
REPORTABLE_FINISH_REASONS = frozenset({
    "stop", "length", "max_tokens", "tool_calls", "function_call",
    "content_filter", "insufficient_system_resource", "unknown",
})


def reject(reason: str) -> None:
    assert reason in REASONS, f"undeclared reason {reason!r}"
    print("DEEPSEEK_PAYLOAD_VALID=FAIL")
    print(f"DEEPSEEK_OUTPUT_REJECTED={reason}", file=sys.stderr)
    raise SystemExit(1)


def load_response(path: Path) -> dict:
    """The outer envelope only. Nothing here looks inside the content."""
    try:
        raw = path.read_text(encoding="utf-8")
    except OSError:
        print("DEEPSEEK_API_HEALTH=UNKNOWN")
        reject("response_unreadable")
    try:
        document = json.loads(raw)
    except json.JSONDecodeError:
        print("DEEPSEEK_API_HEALTH=FAIL")
        reject("response_not_json")
    if not isinstance(document, dict):
        print("DEEPSEEK_API_HEALTH=FAIL")
        reject("envelope_not_object")
    return document


def report_diagnostics(document: dict) -> str:
    """Print what is safe to print, BEFORE anything can fail.

    Everything here is a count, an enum value the provider defines, or a
    boolean. None of it can carry a credential, and all of it is exactly what
    a failing run needs in its log.
    """
    choices = document.get("choices")
    choices = choices if isinstance(choices, list) else []
    print(f"DEEPSEEK_CHOICE_COUNT={len(choices)}")

    choice = choices[0] if choices and isinstance(choices[0], dict) else {}
    finish_reason = choice.get("finish_reason")
    finish_reason = finish_reason if isinstance(finish_reason, str) else "unknown"
    # Reported through the closed vocabulary, never echoed. The value is still
    # returned in full so the truncation check below can use it - it just does
    # not reach the log unless the lane already knows the word.
    print("DEEPSEEK_FINISH_REASON="
          f"{finish_reason if finish_reason in REPORTABLE_FINISH_REASONS else 'other'}")

    message = choice.get("message")
    content = message.get("content") if isinstance(message, dict) else None
    print(f"DEEPSEEK_CONTENT_PRESENT={'true' if isinstance(content, str) else 'false'}")
    print(f"DEEPSEEK_CONTENT_LENGTH={len(content) if isinstance(content, str) else 0}")

    usage = document.get("usage")
    usage = usage if isinstance(usage, dict) else {}
    prompt_tokens = usage.get("prompt_tokens")
    completion_tokens = usage.get("completion_tokens")
    prompt_tokens = prompt_tokens if isinstance(prompt_tokens, int) else 0
    completion_tokens = completion_tokens if isinstance(completion_tokens, int) else 0
    print(f"DEEPSEEK_USAGE_PROMPT_TOKENS={prompt_tokens}")
    print(f"DEEPSEEK_USAGE_COMPLETION_TOKENS={completion_tokens}")
    # Deliberately conservative: an upper bound, so the number never
    # under-reports what the call may have cost.
    conservative_usd = prompt_tokens / 1_000_000 + completion_tokens * 2 / 1_000_000
    print(f"DEEPSEEK_SPEND_ESTIMATE_USD_LE={conservative_usd:.6f}")
    return finish_reason


def extract_content(document: dict, finish_reason: str) -> str:
    choices = document.get("choices")
    if not isinstance(choices, list) or not choices:
        reject("envelope_no_choices")
    choice = choices[0]
    if not isinstance(choice, dict):
        reject("envelope_choice_malformed")
    message = choice.get("message")
    if not isinstance(message, dict):
        reject("envelope_choice_malformed")
    if "content" not in message:
        reject("content_missing")
    content = message["content"]
    if not isinstance(content, str):
        reject("content_not_string")
    if not content.strip():
        # An empty body with finish_reason=length is a truncation, not an
        # empty answer, and saying so is the difference between raising
        # max_tokens and rewriting a parser that was never wrong.
        reject("content_truncated" if finish_reason in TRUNCATING_FINISH_REASONS
               else "content_empty")
    return content


def unwrap_payload(content: str, finish_reason: str) -> dict:
    """Accept an exact JSON object, or a fenced one whose inside is valid.

    A fence is tolerated because a model asked for JSON sometimes wraps it.
    What is NOT tolerated is scavenging: the previous version fell back to
    ``raw_decode`` from the first ``{`` it could find, which will happily parse
    the opening fragment of a truncated reply and hand back an object missing
    most of its files. That turned a truncation into a mismatch and hid the
    real cause.
    """
    stripped = content.strip()
    if stripped.startswith("```"):
        first_newline = stripped.find("\n")
        if first_newline < 0 or not stripped.endswith("```"):
            reject("invalid_fence")
        stripped = stripped[first_newline + 1:-3].strip()
    try:
        payload = json.loads(stripped)
    except json.JSONDecodeError:
        reject("content_truncated" if finish_reason in TRUNCATING_FINISH_REASONS
               else "payload_not_json")
    if not isinstance(payload, dict):
        reject("payload_not_object")
    return payload


def validate_files(payload: dict) -> dict:
    """Every check before any write. Full allowlisted set, or none."""
    if "files" not in payload:
        reject("files_missing")
    files = payload["files"]
    if not isinstance(files, dict):
        reject("files_not_object")
    provided = set(files)
    if provided - ALLOWED_FILES:
        reject("path_not_allowed")
    if provided != ALLOWED_FILES:
        reject("file_set_mismatch")
    for relative, file_content in files.items():
        path = PurePosixPath(relative)
        if path.is_absolute() or ".." in path.parts:
            reject("path_traversal")
        if not isinstance(file_content, str):
            reject("file_content_not_string")
    return files


def main(argv: list[str]) -> int:
    if len(argv) != 3:
        print("usage: deepseek_lane_apply.py <response.json> <repo-root>", file=sys.stderr)
        reject("usage")
    root = Path(argv[2]).resolve()

    document = load_response(Path(argv[1]))
    # The envelope parsed, so the provider answered. Payload validity is a
    # separate verdict from here on.
    print("DEEPSEEK_API_HEALTH=PASS")
    finish_reason = report_diagnostics(document)

    content = extract_content(document, finish_reason)
    payload = unwrap_payload(content, finish_reason)
    files = validate_files(payload)

    for relative, file_content in sorted(files.items()):
        target = root.joinpath(*PurePosixPath(relative).parts)
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(file_content, encoding="utf-8")
        print(f"DEEPSEEK_FILE_WRITTEN={relative}")

    print("DEEPSEEK_PAYLOAD_VALID=PASS")
    print("DEEPSEEK_OUTPUT_APPLIED=PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
