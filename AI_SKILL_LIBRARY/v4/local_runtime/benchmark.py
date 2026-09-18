"""Wave 0: measure a local model's capability by actually running it.

The Model Mesh refuses a candidate that declares zero capability, and a
capability score is benchmark evidence. So the number has to be *measured*, and
measured in a way that someone who distrusts this lane can check.

Four properties make that possible, and each is enforced here rather than
promised in a comment:

* **the suite is frozen before the run.** `BenchmarkSuite.content_hash` covers
  every item, the harness prefix and the decoding parameters. Edit an item,
  reword the prefix, change `max_tokens`, and the hash changes - so a score can
  never silently belong to a different suite than the one it was recorded
  against. Tuning the questions until the model passes is still possible, but
  it is no longer *invisible*, which is the part that matters.
* **decoding is deterministic.** Greedy, temperature 0, fixed seed. Two runs of
  the same suite on the same weights give the same score, so a disagreement is
  a real difference rather than sampling noise.
* **every raw generation is kept.** The score is a count over per-item records
  that each carry the exact text llama.cpp emitted. Nobody has to trust the
  arithmetic; they can redo it.
* **an incomplete run cannot be promoted.** If any item errors, the run is
  DEGRADED and `promotable` is False. A score computed over a partial suite
  looks exactly like a score computed over a whole one, which is precisely why
  it must not be allowed to reach the registry.

What this is *not*: a public benchmark. It is a small locally-defined suite,
and it is named that way everywhere so no reader mistakes it for MMLU or GSM8K.
It measures whether the model can follow a short instruction and answer bounded
reasoning questions correctly - enough to justify a capability floor decision,
and nothing more than that.
"""

from __future__ import annotations

import hashlib
import json
import re
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Mapping, Sequence

BENCHMARKS_DIR = Path(__file__).resolve().parent / "benchmarks"

#: Greedy decoding. Not a preference - a requirement for a reproducible score.
DETERMINISTIC_DECODING: Mapping[str, Any] = {
    "temperature": 0.0,
    "top_k": 1,
    "top_p": 1.0,
    "seed": 0,
}


class BenchmarkError(RuntimeError):
    """The suite itself is unusable. Distinct from a model answering badly."""


@dataclass(frozen=True)
class BenchmarkItem:
    """One scored question.

    `choices` present means multiple choice and `answer` is a choice label;
    absent means short answer and `answer` is matched on word boundaries.
    `must_not_contain` exists so a generation that names every option at once
    cannot score by containing the right one among them.
    """

    item_id: str
    capability: str
    question: str
    answer: str
    choices: tuple[tuple[str, str], ...] = ()
    must_not_contain: tuple[str, ...] = ()

    @property
    def multiple_choice(self) -> bool:
        return bool(self.choices)

    def canonical(self) -> Mapping[str, Any]:
        return {
            "item_id": self.item_id,
            "capability": self.capability,
            "question": self.question,
            "answer": self.answer,
            "choices": [list(pair) for pair in self.choices],
            "must_not_contain": list(self.must_not_contain),
        }


@dataclass(frozen=True)
class BenchmarkSuite:
    suite_id: str
    version: str
    capability: str
    description: str
    prefix: str
    max_tokens: int
    items: tuple[BenchmarkItem, ...]
    decoding: Mapping[str, Any] = field(default_factory=lambda: dict(DETERMINISTIC_DECODING))

    def __post_init__(self) -> None:
        if not self.items:
            raise BenchmarkError(f"suite {self.suite_id} has no items")
        ids = [item.item_id for item in self.items]
        duplicates = sorted({i for i in ids if ids.count(i) > 1})
        if duplicates:
            raise BenchmarkError(f"suite {self.suite_id} has duplicate item ids: {duplicates}")
        for item in self.items:
            if item.multiple_choice:
                labels = {label for label, _ in item.choices}
                if item.answer not in labels:
                    raise BenchmarkError(
                        f"{self.suite_id}/{item.item_id}: answer {item.answer!r} is not one of {sorted(labels)}"
                    )

    @property
    def content_hash(self) -> str:
        """Binds a score to the exact suite that produced it."""
        body = json.dumps(
            {
                "suite_id": self.suite_id,
                "version": self.version,
                "capability": self.capability,
                "prefix": self.prefix,
                "max_tokens": self.max_tokens,
                "decoding": dict(sorted(self.decoding.items())),
                "items": [item.canonical() for item in self.items],
            },
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=False,
        )
        return hashlib.sha256(body.encode("utf-8")).hexdigest()

    def prompt_for(self, item: BenchmarkItem) -> str:
        lines = [self.prefix.rstrip("\n"), "", f"Q: {item.question}"]
        for label, text in item.choices:
            lines.append(f"({label}) {text}")
        lines.append("Answer:")
        return "\n".join(lines)


def load_suite(path: Path) -> BenchmarkSuite:
    try:
        raw = json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise BenchmarkError(f"cannot load benchmark suite {path}: {exc}") from exc
    if not isinstance(raw, dict):
        raise BenchmarkError(f"benchmark suite {path} must be an object")
    try:
        items = tuple(
            BenchmarkItem(
                item_id=str(row["item_id"]),
                capability=str(row.get("capability") or raw["capability"]),
                question=str(row["question"]),
                answer=str(row["answer"]),
                choices=tuple((str(a), str(b)) for a, b in (row.get("choices") or [])),
                must_not_contain=tuple(str(v) for v in (row.get("must_not_contain") or [])),
            )
            for row in raw["items"]
        )
        return BenchmarkSuite(
            suite_id=str(raw["suite_id"]),
            version=str(raw["version"]),
            capability=str(raw["capability"]),
            description=str(raw.get("description") or ""),
            prefix=str(raw["prefix"]),
            max_tokens=int(raw["max_tokens"]),
            items=items,
            decoding=dict(raw.get("decoding") or DETERMINISTIC_DECODING),
        )
    except (KeyError, TypeError, ValueError) as exc:
        raise BenchmarkError(f"malformed benchmark suite {path}: {exc}") from exc


# -- scoring ---------------------------------------------------------------

_LABEL_RE = re.compile(r"[A-Za-z]")


def _normalize(text: str) -> str:
    return re.sub(r"\s+", " ", text.strip().lower())


def extract_choice(generation: str) -> str | None:
    """The first letter the model committed to, or None if it committed to none.

    Read from the head of the generation on purpose. A model that answers "B"
    and then rambles through the other options has still answered B; one whose
    first letter is wrong has not been rescued by mentioning the right one
    later.
    """
    head = generation.strip()
    if not head:
        return None
    match = _LABEL_RE.search(head[:8])
    return match.group(0).upper() if match else None


def score_item(item: BenchmarkItem, generation: str) -> bool:
    text = generation or ""
    for banned in item.must_not_contain:
        if re.search(rf"\b{re.escape(banned.lower())}\b", _normalize(text)):
            return False
    if item.multiple_choice:
        return extract_choice(text) == item.answer.upper()
    return bool(re.search(rf"\b{re.escape(_normalize(item.answer))}\b", _normalize(text)))


# -- running ---------------------------------------------------------------

STATUS_COMPLETE = "COMPLETE"
STATUS_DEGRADED = "DEGRADED"


@dataclass(frozen=True)
class ItemResult:
    item_id: str
    capability: str
    prompt: str
    generation: str | None
    passed: bool
    error: str | None
    latency_ms: float | None

    def to_dict(self) -> Mapping[str, Any]:
        return {
            "item_id": self.item_id,
            "capability": self.capability,
            "prompt": self.prompt,
            "generation": self.generation,
            "passed": self.passed,
            "error": self.error,
            "latency_ms": self.latency_ms,
        }


@dataclass(frozen=True)
class BenchmarkRun:
    suite_id: str
    suite_version: str
    suite_hash: str
    capability: str
    model_id: str
    artifact_sha256: str
    backend_version: str | None
    results: tuple[ItemResult, ...]
    started_at: str
    wall_ms: float

    @property
    def attempted(self) -> int:
        return len(self.results)

    @property
    def errors(self) -> int:
        return sum(1 for r in self.results if r.error)

    @property
    def passed(self) -> int:
        return sum(1 for r in self.results if r.passed)

    @property
    def status(self) -> str:
        return STATUS_DEGRADED if self.errors else STATUS_COMPLETE

    @property
    def score(self) -> float:
        """Errors are scored as failures and also disqualify promotion.

        Dividing by attempted rather than by successful generations matters: a
        run where half the items crashed must not report the accuracy of the
        half that survived as though it were the model's score.
        """
        if not self.results:
            return 0.0
        return round(self.passed / self.attempted, 6)

    @property
    def promotable(self) -> bool:
        return self.status == STATUS_COMPLETE and bool(self.results)

    def to_dict(self) -> Mapping[str, Any]:
        return {
            "suite_id": self.suite_id,
            "suite_version": self.suite_version,
            "suite_hash": self.suite_hash,
            "capability": self.capability,
            "model_id": self.model_id,
            "artifact_sha256": self.artifact_sha256,
            "backend_version": self.backend_version,
            "started_at": self.started_at,
            "wall_ms": self.wall_ms,
            "attempted": self.attempted,
            "passed": self.passed,
            "errors": self.errors,
            "score": self.score,
            "run_status": self.status,
            "promotable": self.promotable,
            "measurement_kind": "local_suite",
            "is_public_benchmark": False,
            "decoding": "greedy/deterministic",
            "results": [r.to_dict() for r in self.results],
        }


def run_suite(
    suite: BenchmarkSuite,
    generate,
    *,
    model_id: str,
    artifact_sha256: str,
    backend_version: str | None = None,
    started_at: str,
) -> BenchmarkRun:
    """Run every item. `generate(prompt, max_tokens, decoding) -> str`.

    Never raises for a model failure - an item that errors is recorded as an
    error, because a suite that aborts on item 3 would otherwise leave the
    remaining items indistinguishable from questions never asked.
    """
    results: list[ItemResult] = []
    started = time.monotonic()
    for item in suite.items:
        prompt = suite.prompt_for(item)
        item_started = time.monotonic()
        try:
            generation = generate(prompt, suite.max_tokens, dict(suite.decoding))
        except Exception as exc:  # noqa: BLE001 - a model failure is data, not a crash
            results.append(
                ItemResult(
                    item_id=item.item_id,
                    capability=item.capability,
                    prompt=prompt,
                    generation=None,
                    passed=False,
                    error=f"{type(exc).__name__}: {exc}",
                    latency_ms=round((time.monotonic() - item_started) * 1000.0, 3),
                )
            )
            continue
        text = "" if generation is None else str(generation)
        results.append(
            ItemResult(
                item_id=item.item_id,
                capability=item.capability,
                prompt=prompt,
                generation=text,
                passed=score_item(item, text),
                error=None,
                latency_ms=round((time.monotonic() - item_started) * 1000.0, 3),
            )
        )
    return BenchmarkRun(
        suite_id=suite.suite_id,
        suite_version=suite.version,
        suite_hash=suite.content_hash,
        capability=suite.capability,
        model_id=model_id,
        artifact_sha256=artifact_sha256,
        backend_version=backend_version,
        results=tuple(results),
        started_at=started_at,
        wall_ms=round((time.monotonic() - started) * 1000.0, 3),
    )
