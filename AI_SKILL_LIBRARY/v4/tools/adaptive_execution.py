from __future__ import annotations


_BUDGETS = {"FAST": 0, "STANDARD": 2, "DEEP": 4}
_ALLOWED_SPECULATIVE_DATA = {"PUBLIC", "INTERNAL"}


def adaptive_budget(profile: str) -> int:
    return int(_BUDGETS.get(str(profile).upper(), 0))


def can_speculate(profile: str, *, quota_remaining: int | float, data_class: str) -> bool:
    if str(profile).upper() != "DEEP":
        return False
    if str(data_class).upper() not in _ALLOWED_SPECULATIVE_DATA:
        return False
    try:
        quota = float(quota_remaining)
    except (TypeError, ValueError):
        return False
    return quota > 0


def deterministic_early_exit(maker: dict, checker: dict, *, required_evidence: int = 1) -> bool:
    if not isinstance(maker, dict) or not isinstance(checker, dict):
        return False
    if maker.get("ok") is not True or checker.get("ok") is not True:
        return False
    maker_family = str(maker.get("family") or "").strip().lower()
    checker_family = str(checker.get("family") or "").strip().lower()
    if not maker_family or not checker_family or maker_family == checker_family:
        return False
    evidence = maker.get("evidence", [])
    if not isinstance(evidence, list):
        return False
    try:
        minimum = max(0, int(required_evidence))
    except (TypeError, ValueError):
        return False
    return len([item for item in evidence if item]) >= minimum
