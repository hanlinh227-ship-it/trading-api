from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json
import os
from pathlib import Path
import random
from typing import Any

from g8.candidate import CandidateSpec, candidate_hash


_DIMENSION_OPTIONS: dict[str, tuple[str, tuple[Any, ...]]] = {
    "sample": ("threshold", (0.50, 0.55, 0.60, 0.70, 0.80)),
    "stability": ("model_family", ("logistic", "random_forest")),
    "cost": ("risk_atr", (0.8, 1.2, 1.6)),
    "calibration": ("calibration", ("none", "platt", "isotonic")),
    "agreement": (
        "feature_pack",
        (
            ("base_g7",),
            ("base_g7", "flow"),
            ("base_g7", "htf"),
            ("base_g7", "flow", "htf"),
        ),
    ),
    "regime": ("regime", ("TREND_UP", "TREND_DOWN", "RANGE", "COMPRESSION", "EXPANSION")),
    "structure": (
        "family",
        ("setup_trend", "setup_breakout", "setup_sweep", "setup_compression", "setup_exhaustion"),
    ),
}


@dataclass(frozen=True)
class HypothesisSpec:
    candidate: CandidateSpec
    research_dimension: str
    parent_hash: str
    changed_fields: tuple[str, ...]

    @property
    def hypothesis_hash(self) -> str:
        payload = {
            "candidate": self.candidate.material_dict(),
            "research_dimension": self.research_dimension,
            "changed_fields": list(self.changed_fields),
        }
        raw = json.dumps(payload, sort_keys=True, separators=(",", ":"), allow_nan=False)
        return hashlib.sha256(raw.encode("utf-8")).hexdigest()


class FailureMemory:
    def __init__(self, path: Path | str):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)

    def rejected_hashes(self) -> set[str]:
        if not self.path.exists():
            return set()
        hashes: set[str] = set()
        for line in self.path.read_text(encoding="utf-8").splitlines():
            if not line.strip():
                continue
            payload = json.loads(line)
            value = payload.get("hypothesis_hash")
            if value:
                hashes.add(str(value))
        return hashes

    def record_rejection(self, hypothesis_hash: str, *, reason: str) -> None:
        payload = {
            "hypothesis_hash": str(hypothesis_hash),
            "reason": str(reason),
            "record_type": "rejection",
            "research_only": True,
        }
        line = json.dumps(payload, sort_keys=True, separators=(",", ":")) + "\n"
        with self.path.open("a", encoding="utf-8") as handle:
            handle.write(line)
            handle.flush()
            os.fsync(handle.fileno())


def generate_hypotheses(
    parent: CandidateSpec,
    *,
    research_dimension: str,
    seed: int,
    budget: int,
    failure_memory: FailureMemory,
) -> list[HypothesisSpec]:
    if research_dimension not in _DIMENSION_OPTIONS:
        raise ValueError(f"unsupported research dimension: {research_dimension}")
    budget = max(0, int(budget))
    if budget == 0:
        return []

    field_name, options = _DIMENSION_OPTIONS[research_dimension]
    parent_digest = candidate_hash(parent)
    proposals: list[HypothesisSpec] = []
    current = getattr(parent, field_name)
    for value in options:
        if value == current:
            continue
        child = parent.with_updates(**{field_name: value, "parent_hash": parent_digest})
        proposals.append(
            HypothesisSpec(
                candidate=child,
                research_dimension=research_dimension,
                parent_hash=parent_digest,
                changed_fields=(field_name,),
            )
        )

    random.Random(int(seed)).shuffle(proposals)
    rejected = failure_memory.rejected_hashes()
    result: list[HypothesisSpec] = []
    seen: set[str] = set()
    for hypothesis in proposals:
        digest = hypothesis.hypothesis_hash
        if digest in rejected or digest in seen:
            continue
        seen.add(digest)
        result.append(hypothesis)
        if len(result) >= budget:
            break
    return result
