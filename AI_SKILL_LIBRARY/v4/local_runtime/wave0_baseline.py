"""Wave 0 baseline: prompts and real verifiers for the canonical 12 tasks.

`v4/control_plane/wave0.json` fixes the composition - twelve task ids, their
categories and which verifier each one answers to - and `control_plane/benchmark.py`
owns ingestion and the freeze. Neither is changed here. What was missing was the
other half: the tasks carry no prompts, and the verifier names had no
implementations, so nothing could actually be run against them.

The rule these verifiers are written to is that each one must be able to fail
for the reason it claims to check. A verifier that returns True is not a
verifier, and twelve of those would freeze a baseline that measured nothing.
So:

* MATH and CODING are checked by computing, not by reading. The coding tasks ask
  for an arithmetic expression and it is evaluated - under a restricted AST
  walk that permits literals and arithmetic and nothing else, so model-written
  text is never handed to a general `eval`. An expression containing a call, a
  name, an attribute or a subscript is refused rather than run.
* STRUCTURED_OUTPUT is checked by parsing. Either it is JSON with the required
  keys or it is not.
* VIETNAMESE requires the expected term *and* evidence the answer is actually
  in Vietnamese - a diacritic outside plain ASCII - because an English answer
  containing a borrowed word would otherwise pass a Vietnamese task.
* GENERAL_REASONING matches the expected answer on word boundaries and refuses
  answers that also assert a listed contradiction, so naming both a thing and
  its opposite is not a pass.

Prompts are frozen by content hash before any run, for the same reason the
capability suite is: so a score cannot quietly come to belong to a different
set of questions than the one it claims.
"""

from __future__ import annotations

import ast
import hashlib
import json
import re
import unicodedata
from pathlib import Path
from typing import Any, Mapping

PROMPTS_PATH = Path(__file__).resolve().parent / "benchmarks" / "wave0_prompts.json"

#: Greedy. `reproducible` in the canonical report means two runs agreed, which
#: is only a meaningful claim under deterministic decoding.
#: `reset_state` clears the KV cache before each call. Without it the repeat
#: run continues from the first run's context and can diverge under greedy
#: decoding - which it did, on 2 of 12 tasks, making "reproducible" a
#: measurement of cache carry-over rather than of the model.
DECODING: Mapping[str, Any] = {"temperature": 0.0, "top_k": 1, "top_p": 1.0, "seed": 0,
                               "reset_state": True}


class Wave0Error(RuntimeError):
    """The prompt set is unusable. Never a stand-in for a failed verifier."""


def load_prompts(path: Path | None = None) -> dict[str, Any]:
    path = path or PROMPTS_PATH
    try:
        data = json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise Wave0Error(f"cannot load Wave 0 prompts: {exc}") from exc
    if not isinstance(data, dict) or not isinstance(data.get("prompts"), dict):
        raise Wave0Error("Wave 0 prompts file must carry a 'prompts' object")
    return data


def prompts_hash(data: Mapping[str, Any]) -> str:
    body = json.dumps(data, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return hashlib.sha256(body.encode("utf-8")).hexdigest()


# -- verifiers -------------------------------------------------------------


def _normalize(text: str) -> str:
    return re.sub(r"\s+", " ", (text or "").strip().lower())


def _contains_word(haystack: str, needle: str) -> bool:
    return bool(re.search(rf"(?<!\w){re.escape(_normalize(needle))}(?!\w)", _normalize(haystack)))


_ALLOWED_NODES = (
    ast.Expression, ast.BinOp, ast.UnaryOp, ast.Constant,
    ast.Add, ast.Sub, ast.Mult, ast.Div, ast.FloorDiv, ast.Mod, ast.Pow,
    ast.USub, ast.UAdd, ast.Tuple, ast.List,
)


def safe_arithmetic_value(expression: str) -> tuple[Any, str | None]:
    """Evaluate an arithmetic expression, or refuse to.

    The refusal is the point. Model output is text, and this is the one place
    it would be tempting to run it - so the AST is walked first and anything
    that is not a literal or an arithmetic operator (a call, a name, an
    attribute, a subscript, a comprehension) is rejected without evaluation.
    """
    source = (expression or "").strip()
    if not source:
        return None, "empty_expression"
    if len(source) > 200:
        return None, "expression_too_long"
    try:
        tree = ast.parse(source, mode="eval")
    except SyntaxError as exc:
        return None, f"not_a_python_expression: {exc.msg}"
    for node in ast.walk(tree):
        if not isinstance(node, _ALLOWED_NODES):
            return None, f"disallowed_expression_node: {type(node).__name__}"
    try:
        return eval(compile(tree, "<wave0>", "eval"), {"__builtins__": {}}, {}), None
    except Exception as exc:  # noqa: BLE001 - division by zero, overflow, ...
        return None, f"evaluation_failed: {type(exc).__name__}"


def _first_number(text: str) -> float | None:
    match = re.search(r"-?\d+(?:\.\d+)?", text or "")
    return float(match.group(0)) if match else None


def _has_vietnamese_diacritics(text: str) -> bool:
    for char in text or "":
        if char.isascii():
            continue
        decomposed = unicodedata.normalize("NFD", char)
        if any(unicodedata.combining(part) for part in decomposed):
            return True
    return False


def verify(category: str, expectation: Mapping[str, Any], output: str) -> dict[str, Any]:
    """Run the verifier for a category. Returns passed plus why not."""
    text = output or ""
    failures: list[str] = []

    if not text.strip():
        return {"passed": False, "failures": ["empty_output"], "category": category}

    for banned in expectation.get("must_not_contain") or []:
        if _contains_word(text, banned):
            failures.append(f"asserted_contradiction:{banned}")

    if category == "MATH":
        expected = float(expectation["expected_number"])
        observed = _first_number(text)
        if observed is None:
            failures.append("no_number_in_output")
        elif abs(observed - expected) > 1e-9:
            failures.append(f"wrong_number:{observed}!={expected}")

    elif category == "CODING":
        expected = expectation["expected_value"]
        candidate = text.strip().splitlines()[0].strip().rstrip(".")
        value, why = safe_arithmetic_value(candidate)
        if why:
            failures.append(why)
        elif value != expected:
            failures.append(f"expression_value:{value!r}!={expected!r}")

    elif category == "STRUCTURED_OUTPUT":
        start, end = text.find("{"), text.rfind("}")
        if start < 0 or end <= start:
            failures.append("no_json_object_in_output")
        else:
            try:
                parsed = json.loads(text[start:end + 1])
            except json.JSONDecodeError as exc:
                parsed = None
                failures.append(f"invalid_json: {exc.msg}")
            if isinstance(parsed, dict):
                for key in expectation.get("required_keys") or []:
                    if key not in parsed:
                        failures.append(f"missing_key:{key}")
            elif parsed is not None:
                failures.append("json_is_not_an_object")

    elif category == "VIETNAMESE":
        if not _has_vietnamese_diacritics(text):
            failures.append("answer_is_not_in_vietnamese")
        if not any(_contains_word(text, term) for term in expectation["any_of"]):
            failures.append("expected_term_absent")

    elif category == "GENERAL_REASONING":
        if not any(_contains_word(text, term) for term in expectation["any_of"]):
            failures.append("expected_answer_absent")

    else:
        failures.append(f"unknown_category:{category}")

    return {"passed": not failures, "failures": failures, "category": category}
