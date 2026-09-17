from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


STATES = (
    "AUTO_DEV_IDLE", "AUTO_DEV_PLANNING", "AUTO_DEV_BRANCH_CREATED",
    "AUTO_DEV_IMPLEMENTING", "AUTO_DEV_TESTING", "AUTO_DEV_BENCHMARKING",
    "AUTO_DEV_REVIEW", "AUTO_DEV_READY_TO_MERGE", "AUTO_DEV_REJECTED",
    "AUTO_DEV_ROLLED_BACK",
)
_NEXT = {state: STATES[index + 1] for index, state in enumerate(STATES[:7])}
_GATES = {"tests", "benchmark", "security", "authority", "pr"}
_ALLOWED_ACTIONS = {"create_branch", "edit_branch", "add_tests", "run_tests", "benchmark", "open_pr", "prepare_rollback"}
_FORBIDDEN_ACTIONS = {"bypass_ci", "disable_security", "change_router_authority", "expose_secrets", "enable_paid_api", "execute_trade", "mutate_main", "self_approve"}
_SCORE_FIELDS = {"quality", "latency", "resource_use", "reliability", "security", "vietnamese_retention", "instruction_adherence"}


@dataclass
class AutoDevRun:
    branch: str
    base_sha: str
    rollback_target: str
    state: str = "AUTO_DEV_IDLE"
    gates: dict[str, dict[str, Any]] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if self.branch in {"main", "master"} or not self.branch:
            raise ValueError("protected canonical branch cannot be an auto-development target")
        if not self.base_sha or not self.rollback_target:
            raise ValueError("base and rollback targets are required")

    def record_gate(self, name: str, passed: bool, evidence_ref: str) -> None:
        if name not in _GATES or not evidence_ref:
            raise ValueError("known gate and evidence reference are required")
        self.gates[name] = {"passed": passed is True, "evidence_ref": evidence_ref}
        if passed is not True:
            self.state = "AUTO_DEV_REJECTED"

    def transition(self, target: str) -> None:
        if self.state in {"AUTO_DEV_REJECTED", "AUTO_DEV_ROLLED_BACK", "AUTO_DEV_READY_TO_MERGE"}:
            raise ValueError("terminal auto-development state")
        if target == "AUTO_DEV_READY_TO_MERGE":
            if self.state != "AUTO_DEV_REVIEW" or set(self.gates) != _GATES or not all(row["passed"] for row in self.gates.values()):
                raise ValueError("all gates must pass before merge readiness")
            self.state = target
            return
        if target == "AUTO_DEV_ROLLED_BACK":
            self.state = target
            return
        if _NEXT.get(self.state) != target:
            raise ValueError("invalid auto-development transition")
        self.state = target

    def authorizes(self, action: str) -> bool:
        if action in _FORBIDDEN_ACTIONS:
            return False
        return action in _ALLOWED_ACTIONS


def evaluate_merge_readiness(before: dict[str, Any], after: dict[str, Any], rollback_target: str) -> dict[str, Any]:
    failures: list[str] = []
    if not rollback_target:
        failures.append("rollback_target_missing")
    if not isinstance(before, dict) or set(before) < _SCORE_FIELDS:
        failures.append("baseline_missing")
    if not isinstance(after, dict) or set(after) < _SCORE_FIELDS:
        failures.append("candidate_scorecard_incomplete")
    if failures:
        return {"passed": False, "failures": failures}
    for protected in ("reliability", "security", "vietnamese_retention", "instruction_adherence"):
        if after[protected] < before[protected]:
            failures.append(f"protected_regression:{protected}")
    if after["resource_use"] > before["resource_use"]:
        failures.append("resource_regression")
    if after["latency"] > before["latency"]:
        failures.append("latency_regression")
    if after["quality"] <= before["quality"]:
        failures.append("quality_not_improved")
    return {"passed": not failures, "failures": failures, "rollback_target": rollback_target}
