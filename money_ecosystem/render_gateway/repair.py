from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

from .qa import QAReport, QAStatus


class RepairAction(str, Enum):
    NONE = "NONE"
    LOCAL_INPAINT = "LOCAL_INPAINT"
    PROVIDER_EDIT = "PROVIDER_EDIT"
    REGION_RERENDER = "REGION_RERENDER"
    FULL_RERENDER = "FULL_RERENDER"
    STRONGER_PROVIDER = "STRONGER_PROVIDER"
    HUMAN_REVIEW = "HUMAN_REVIEW"


@dataclass(frozen=True)
class RepairDecision:
    action: RepairAction
    reason: str


_RETRY_ORDER = (
    RepairAction.LOCAL_INPAINT,
    RepairAction.PROVIDER_EDIT,
    RepairAction.REGION_RERENDER,
    RepairAction.FULL_RERENDER,
    RepairAction.STRONGER_PROVIDER,
)


def next_repair(report: QAReport, attempt_history: list[str]) -> RepairDecision:
    if report.status in {QAStatus.VERIFIED, QAStatus.HEURISTIC_PASS}:
        return RepairDecision(RepairAction.NONE, "QA accepted")
    if report.status is QAStatus.HUMAN_REVIEW:
        return RepairDecision(RepairAction.HUMAN_REVIEW, report.reason or "human review required")
    index = len(attempt_history)
    if index >= len(_RETRY_ORDER):
        return RepairDecision(RepairAction.HUMAN_REVIEW, "repair ladder exhausted")
    action = _RETRY_ORDER[index]
    return RepairDecision(action, f"QA status {report.status.value}: {report.reason}")
