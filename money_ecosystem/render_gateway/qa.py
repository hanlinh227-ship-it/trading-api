from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from hashlib import sha256
from pathlib import Path
from typing import Any, Mapping

from PIL import Image

from .contract import QualityTier
from .scene_contract import ExactSceneContract


class QAStatus(str, Enum):
    VERIFIED = "VERIFIED"
    HEURISTIC_PASS = "HEURISTIC_PASS"
    HUMAN_REVIEW = "HUMAN_REVIEW"
    RETRY = "RETRY"
    REJECTED = "REJECTED"


class AssertionStatus(str, Enum):
    PASS = "PASS"
    FAIL = "FAIL"
    UNVERIFIED = "UNVERIFIED"


@dataclass(frozen=True)
class QAAssertion:
    gate: str
    key: str
    status: AssertionStatus
    score: float | None
    evidence_source: str
    reason: str


@dataclass(frozen=True)
class QAReport:
    status: QAStatus
    sha256: str | None
    assertions: tuple[QAAssertion, ...]
    reason: str


def _assertion(gate: str, key: str, raw: Mapping[str, Any] | None) -> QAAssertion:
    if not isinstance(raw, Mapping):
        return QAAssertion(gate, key, AssertionStatus.UNVERIFIED, None, "none", "missing evidence")
    try:
        status = AssertionStatus(str(raw.get("status", "UNVERIFIED")))
    except ValueError:
        status = AssertionStatus.UNVERIFIED
    score_raw = raw.get("score")
    score = float(score_raw) if isinstance(score_raw, (int, float)) else None
    source = str(raw.get("evidence_source", "none")).strip() or "none"
    reason = str(raw.get("reason", "")).strip()
    if status is AssertionStatus.PASS and source == "none":
        status = AssertionStatus.UNVERIFIED
        reason = reason or "PASS claim has no evidence source"
    return QAAssertion(gate, key, status, score, source, reason)


def _file_gate(path: Path, expected: tuple[int, int]) -> tuple[str | None, list[QAAssertion]]:
    assertions: list[QAAssertion] = []
    if not path.is_file() or path.stat().st_size == 0:
        assertions.append(QAAssertion("A", "file", AssertionStatus.FAIL, 0.0, "filesystem", "missing/empty image"))
        return None, assertions
    digest = sha256(path.read_bytes()).hexdigest()
    try:
        with Image.open(path) as image:
            image.load()
            dimensions = image.size
    except Exception as exc:
        assertions.append(QAAssertion("A", "decode", AssertionStatus.FAIL, 0.0, "Pillow", f"decode failed: {exc}"))
        return digest, assertions
    if tuple(dimensions) != tuple(expected):
        assertions.append(QAAssertion("A", "dimensions", AssertionStatus.FAIL, 0.0, "Pillow", f"expected {expected}, got {dimensions}"))
    else:
        assertions.append(QAAssertion("A", "dimensions", AssertionStatus.PASS, 1.0, "Pillow", "dimensions match"))
    return digest, assertions


def evaluate_scene(
    scene: ExactSceneContract,
    artifact: Path | str,
    evidence: Mapping[str, Any],
    *,
    quality_tier: QualityTier = QualityTier.FLOW_GRADE,
) -> QAReport:
    path = Path(artifact)
    expected = evidence.get("expected_dimensions")
    if not isinstance(expected, (list, tuple)) or len(expected) != 2:
        expected = (0, 0)
    expected_dimensions = (int(expected[0]), int(expected[1]))
    digest, assertions = _file_gate(path, expected_dimensions)
    if any(item.status is AssertionStatus.FAIL for item in assertions):
        return QAReport(QAStatus.REJECTED, digest, tuple(assertions), "deterministic file QA failed")

    structural = evidence.get("structural") if isinstance(evidence.get("structural"), Mapping) else {}
    identity = evidence.get("identity") if isinstance(evidence.get("identity"), Mapping) else {}
    semantic = evidence.get("semantic") if isinstance(evidence.get("semantic"), Mapping) else {}
    finish = evidence.get("finish") if isinstance(evidence.get("finish"), Mapping) else {}

    assertions.append(_assertion("B", "entity_count", structural.get("entity_count")))
    if "no_extra_subjects" in structural:
        assertions.append(_assertion("B", "no_extra_subjects", structural.get("no_extra_subjects")))

    for entity_id in scene.required_entities:
        assertions.append(_assertion("C", entity_id, identity.get(entity_id)))

    assertions.extend([
        _assertion("D", "background", semantic.get("background")),
        _assertion("D", "actions", semantic.get("actions")),
        _assertion("D", "camera", semantic.get("camera")),
        _assertion("E", "quality", finish.get("quality")),
    ])

    failures = [item for item in assertions if item.status is AssertionStatus.FAIL]
    unverified = [item for item in assertions if item.status is AssertionStatus.UNVERIFIED]
    if failures:
        reason = "; ".join(f"{item.gate}:{item.key}={item.reason or 'failed'}" for item in failures)
        return QAReport(QAStatus.RETRY, digest, tuple(assertions), reason)

    if unverified:
        reason = "; ".join(f"{item.gate}:{item.key}={item.reason or 'unverified'}" for item in unverified)
        if quality_tier is QualityTier.FLOW_GRADE:
            return QAReport(QAStatus.HUMAN_REVIEW, digest, tuple(assertions), reason)
        return QAReport(QAStatus.HEURISTIC_PASS, digest, tuple(assertions), reason)

    return QAReport(QAStatus.VERIFIED, digest, tuple(assertions), "all mandatory QA gates have evidence-backed PASS")
