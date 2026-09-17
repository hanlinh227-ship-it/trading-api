#!/usr/bin/env python3
"""Validate the Brain Expansion adapter registry against canonical invariants.

Fails closed if any expansion candidate claims routing, reasoning, memory,
model-selection or execution authority; if a reference-only candidate becomes
executable; if an executable dependency appears without a verified licence and a
pinned commit; or if an adapter reports itself enabled without runtime evidence.
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from brain_expansion_adapters import (  # noqa: E402
    AUTO_ACTIVATION_CONDITIONS,
    REFERENCE_ONLY,
    RUNTIME_ADAPTERS,
    activation_state,
    auto_activation_policy,
    boot_eligibility,
    evaluate_eligibility,
    load_adapter_registry,
    required_conditions,
    stable_path_smoke,
    validate_registry,
)


def main(argv: list[str] | None = None) -> int:
    root = Path(argv[0]).resolve() if argv else None
    registry = load_adapter_registry(root)
    errors = validate_registry(registry, root)

    smoke = stable_path_smoke(registry=registry, disabled=list(RUNTIME_ADAPTERS), root=root)
    if not smoke["stable_path_ok"]:
        errors.append(f"stable path requires expansion adapters: {smoke['required_adapters']}")

    # Each runtime adapter must also disable on its own.
    for adapter_id in RUNTIME_ADAPTERS:
        single = stable_path_smoke(registry=registry, disabled=[adapter_id], root=root)
        if not single["stable_path_ok"]:
            errors.append(f"{adapter_id}: stable path breaks when this adapter alone is disabled")

    candidates = registry.get("candidates") or {}
    states = {name: activation_state(record) for name, record in candidates.items()}
    for name in REFERENCE_ONLY:
        if states.get(name) != "reference_only":
            errors.append(f"{name}: must report reference_only, got {states.get(name)!r}")

    # Auto-activation must stay AUTO_ACTIVATE_WHEN_VERIFIED and fail closed.
    policy = auto_activation_policy(registry)
    if policy["mode"] != "AUTO_ACTIVATE_WHEN_VERIFIED":
        errors.append(f"auto-activation mode must be AUTO_ACTIVATE_WHEN_VERIFIED, got {policy['mode']!r}")
    for flag in ("always_on", "paid_dependency_auto_install", "billing_auto_enable", "fast_path_synchronous_probe"):
        if policy[flag]:
            errors.append(f"auto-activation must not set {flag}")
    for flag in ("fail_closed", "unknown_is_failure"):
        if not policy[flag]:
            errors.append(f"auto-activation must set {flag}")

    for adapter_id in RUNTIME_ADAPTERS:
        record = candidates.get(adapter_id) or {}
        conditions = required_conditions(adapter_id, record)
        if not conditions:
            errors.append(f"{adapter_id}: must declare its required auto-activation conditions")
        unknown = set(conditions) - set(AUTO_ACTIVATION_CONDITIONS)
        if unknown:
            errors.append(f"{adapter_id}: unknown auto-activation conditions {sorted(unknown)}")
        # With nothing verified, every adapter must fail closed.
        closed = evaluate_eligibility(adapter_id, record, probes={})
        if closed["enabled"]:
            errors.append(f"{adapter_id}: must not enable when no condition is verified")

    # A boot sweep where every probe fails must leave the stable brain intact.
    boot = boot_eligibility(registry=registry, probe_fn=lambda _n: False, profile="STANDARD", root=root)
    if boot["enabled_adapters"]:
        errors.append(f"adapters enabled despite failing probes: {boot['enabled_adapters']}")
    if not boot["stable_path_ok"]:
        errors.append("stable path not ok during boot eligibility sweep")

    for line in errors:
        print(f"ERROR {line}")
    summary = " ".join(f"{name}={state}" for name, state in sorted(states.items()))
    print(f"BRAIN_EXPANSION_VALIDATE={'PASS' if not errors else 'FAIL'} errors={len(errors)} {summary}")
    return 1 if errors else 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
