from __future__ import annotations

from typing import Any


def _report(kind: str, failures: list[str], evidence: list[str] | None = None) -> dict[str, Any]:
    unique = sorted(set(failures))
    return {"verifier": kind, "passed": not unique, "failures": unique, "evidence_refs": evidence or []}


def verify_output(kind: str, output: dict[str, Any]) -> dict[str, Any]:
    kind = str(kind).upper()
    if not isinstance(output, dict):
        return _report(kind, ["output_schema_invalid"])
    failures: list[str] = []
    evidence = output.get("evidence_refs", [])
    evidence = evidence if isinstance(evidence, list) else []

    if kind == "CODING":
        checks = output.get("checks", {})
        if not all(checks.get(name) == "pass" for name in ("compile", "tests", "static_analysis")):
            failures.append("coding_checks_failed")
        if not evidence:
            failures.append("missing_check_evidence")
    elif kind == "MATH":
        answer, expected = output.get("answer"), output.get("expected")
        tolerance = output.get("tolerance", 0)
        if not all(isinstance(x, (int, float)) and not isinstance(x, bool) for x in (answer, expected, tolerance)):
            failures.append("numeric_evidence_invalid")
        elif abs(answer - expected) > tolerance:
            failures.append("numeric_mismatch")
    elif kind == "STRUCTURED_OUTPUT":
        data, required = output.get("data"), output.get("required_fields")
        if not isinstance(data, dict) or not isinstance(required, list) or any(field not in data for field in required):
            failures.append("schema_validation_failed")
    elif kind == "RESEARCH":
        claims = output.get("claims")
        if not isinstance(claims, list) or not claims:
            failures.append("claims_missing")
        else:
            for claim in claims:
                if not isinstance(claim, dict) or not claim.get("source_refs"):
                    failures.append("claim_source_missing")
                if not isinstance(claim, dict) or not claim.get("freshness"):
                    failures.append("claim_freshness_missing")
    elif kind == "VIETNAMESE":
        answer = output.get("answer", "")
        if not isinstance(answer, str) or not any(ch in answer.lower() for ch in "ăâđêôơưáàảãạéèẻẽẹíìỉĩịóòỏõọúùủũụýỳỷỹỵ"):
            failures.append("vietnamese_language_check_failed")
        if not output.get("instruction_checks") or not all(output["instruction_checks"]):
            failures.append("instruction_check_failed")
        if not output.get("factual_checks") or not all(output["factual_checks"]):
            failures.append("factual_check_failed")
    elif kind == "TRADING_RESEARCH":
        if output.get("data_fresh") is not True:
            failures.append("market_data_stale_or_unknown")
        if not output.get("source_refs"):
            failures.append("market_source_missing")
        if not output.get("risk_evidence"):
            failures.append("risk_evidence_missing")
    elif kind == "CREATIVE":
        constraints = output.get("constraints")
        if not isinstance(constraints, dict) or not constraints or not all(value is True for value in constraints.values()):
            failures.append("creative_constraint_failed")
    else:
        failures.append("unsupported_verifier")
    return _report(kind, failures, evidence)
