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
    REFERENCE_ONLY,
    RUNTIME_ADAPTERS,
    activation_state,
    load_adapter_registry,
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

    for line in errors:
        print(f"ERROR {line}")
    summary = " ".join(f"{name}={state}" for name, state in sorted(states.items()))
    print(f"BRAIN_EXPANSION_VALIDATE={'PASS' if not errors else 'FAIL'} errors={len(errors)} {summary}")
    return 1 if errors else 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
