from __future__ import annotations

import argparse
from pathlib import Path

import yaml

PROTECTED_CLASSES = {
    "live_or_trading",
    "deployment_or_runtime_claim",
    "credential_sensitive",
    "financial",
    "destructive",
    "permission_change",
}
ALLOWED_AUTONOMOUS_PROMOTION = {"A", "B"}


def _load_yaml(path: Path) -> dict:
    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError(f"mapping_required:{path}")
    return data


def validate(root: Path) -> list[str]:
    root = root.resolve()
    errors: list[str] = []
    registry = _load_yaml(root / "AI_SKILL_LIBRARY/v4/adapters/registry.yaml")
    policy = _load_yaml(root / "AI_SKILL_LIBRARY/v4/stable/universal_fabric.yaml")

    if registry.get("authority") is not False:
        errors.append("adapter_registry_must_not_be_authority")
    adapters = registry.get("adapters")
    if not isinstance(adapters, list) or not adapters:
        errors.append("adapter_registry_requires_adapters")
        adapters = []

    ids: set[str] = set()
    bindings: set[str] = set()
    for row in adapters:
        if not isinstance(row, dict):
            errors.append("adapter_row_must_be_mapping")
            continue
        adapter_id = str(row.get("id") or "").strip()
        binding = str(row.get("token_binding") or "").strip()
        scopes = row.get("scopes")
        if not adapter_id:
            errors.append("adapter_id_required")
        elif adapter_id in ids:
            errors.append(f"duplicate_adapter_id:{adapter_id}")
        ids.add(adapter_id)
        if not binding:
            errors.append(f"token_binding_required:{adapter_id or 'unknown'}")
        elif binding in bindings:
            errors.append(f"duplicate_token_binding:{binding}")
        bindings.add(binding)
        if not isinstance(scopes, list) or "brain.route" not in scopes:
            errors.append(f"brain_route_scope_required:{adapter_id or 'unknown'}")
        if row.get("routing_authority") is not False:
            errors.append(f"adapter_routing_authority_forbidden:{adapter_id or 'unknown'}")
        if row.get("reasoning_authority") is not False:
            errors.append(f"adapter_reasoning_authority_forbidden:{adapter_id or 'unknown'}")

    if policy.get("authority") != "GITHUB_BRAIN_V4":
        errors.append("universal_fabric_authority_must_be_github_brain_v4")
    if policy.get("adapter_authority") is not False:
        errors.append("adapter_authority_must_be_false")

    routing = policy.get("routing") if isinstance(policy.get("routing"), dict) else {}
    fast = routing.get("FAST") if isinstance(routing.get("FAST"), dict) else {}
    if fast.get("online_brain_required") is not False:
        errors.append("fast_online_brain_required_must_be_false")
    if fast.get("external_routing_calls") != 0:
        errors.append("fast_external_routing_calls_must_be_zero")
    if fast.get("hot_snapshot_required") is not True:
        errors.append("fast_hot_snapshot_required")
    if fast.get("synchronous_shared_state") is not False:
        errors.append("fast_synchronous_shared_state_forbidden")

    degraded = policy.get("degraded") if isinstance(policy.get("degraded"), dict) else {}
    fail_closed = set(degraded.get("fail_closed_classes") or [])
    missing = sorted(PROTECTED_CLASSES - fail_closed)
    if missing:
        errors.append("protected_degraded_classes_missing:" + ",".join(missing))

    shared_state = policy.get("shared_state") if isinstance(policy.get("shared_state"), dict) else {}
    if shared_state.get("canonical_authority") != "github":
        errors.append("shared_state_canonical_authority_must_be_github")
    if shared_state.get("runtime_authority") is not False:
        errors.append("runtime_state_authority_forbidden")
    if shared_state.get("raw_chat_sync") is not False:
        errors.append("raw_chat_sync_forbidden")
    if shared_state.get("secrets_allowed") is not False:
        errors.append("shared_state_secrets_forbidden")

    learning = policy.get("learning") if isinstance(policy.get("learning"), dict) else {}
    autonomous = set(str(x) for x in (learning.get("autonomous_promotion_classes") or []))
    approvals = set(str(x) for x in (learning.get("approval_required_classes") or []))
    if not autonomous.issubset(ALLOWED_AUTONOMOUS_PROMOTION):
        errors.append("autonomous_promotion_exceeds_low_risk_classes")
    if not {"C", "D"}.issubset(approvals):
        errors.append("high_risk_promotion_requires_approval")
    if learning.get("permission_widening") is not False:
        errors.append("permission_widening_by_learning_forbidden")

    future = registry.get("future_adapter_contract") if isinstance(registry.get("future_adapter_contract"), dict) else {}
    if future.get("brain_core_change_required") is not False:
        errors.append("future_adapter_must_not_require_brain_core_change")
    if future.get("default_state") != "disabled":
        errors.append("future_adapter_default_state_must_be_disabled")

    return errors


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", default=".")
    args = parser.parse_args()
    root = Path(args.root)
    try:
        errors = validate(root)
    except (OSError, ValueError, yaml.YAMLError) as exc:
        print(f"[ERROR] {exc}")
        return 1
    for error in errors:
        print(f"[ERROR] {error}")
    if errors:
        print(f"UNIVERSAL_FABRIC_VALIDATE=FAIL errors={len(errors)}")
        return 1
    registry = _load_yaml(root.resolve() / "AI_SKILL_LIBRARY/v4/adapters/registry.yaml")
    print(f"UNIVERSAL_FABRIC_VALIDATE=PASS adapters={len(registry['adapters'])}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
