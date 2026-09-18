from __future__ import annotations

import argparse
import json
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
PRINCIPAL_TYPES = {"user", "internal"}

# The Federated Free Storage Mesh is persistence, not authority. The fabric
# names it as a subordinate subsystem, and this validator's job is to *reject* a
# storage authority claim rather than merely decline to grant one: a policy that
# says "storage_authority: true" must fail here, not be quietly ignored.
STORAGE_POLICY_PATH = "AI_SKILL_LIBRARY/v4/storage/policy.yaml"
STORAGE_PROVIDERS_PATH = "AI_SKILL_LIBRARY/v4/storage/providers.yaml"
LEARNING_POLICY_PATH = "AI_SKILL_LIBRARY/v4/learning/policy.yaml"
CHECKPOINT_PATH = "AI_SKILL_LIBRARY/checkpoint.json"

# Checked for presence rather than assumed, so that deleting a declaration is
# not a way to stop declaring "not me".
REQUIRED_STORAGE_AUTHORITY_KEYS = {
    "storage_authority",
    "routing_authority",
    "reasoning_authority",
    "model_selection_authority",
    "admission_authority",
    "scheduling_authority",
    "merge_authority",
    "trading_authority",
}
# Pointers only. Each must exist in the checkpoint and resolve to a real file;
# none of them moves authority anywhere.
CHECKPOINT_STORAGE_POINTERS = {
    "storage_mesh_policy_path": STORAGE_POLICY_PATH,
    "storage_mesh_provider_registry_path": STORAGE_PROVIDERS_PATH,
    "storage_provider_schema_path": "AI_SKILL_LIBRARY/v4/schemas/storage_provider.schema.json",
    "storage_object_manifest_schema_path":
        "AI_SKILL_LIBRARY/v4/schemas/storage_object_manifest.schema.json",
    "storage_mesh_validator_path": "AI_SKILL_LIBRARY/v4/storage/mesh_validator.py",
}
# The fabric block's pointers and the checkpoint's must name the same files.
FABRIC_TO_CHECKPOINT_POINTER = {
    "policy": "storage_mesh_policy_path",
    "providers": "storage_mesh_provider_registry_path",
    "provider_schema": "storage_provider_schema_path",
    "object_manifest_schema": "storage_object_manifest_schema_path",
}
# Learning may ask for a storage *class*. Everything else about where its
# outputs land belongs to the storage mesh's own subordinate machinery.
LEARNING_STORAGE_PERMISSIONS = {
    "may_select_provider",
    "may_override_placement_policy",
    "may_bypass_privacy",
    "may_bypass_retention",
    "may_force_replication",
    "may_widen_cloud_eligibility",
}


def _authority_claims(node, prefix: str = "", exempt: frozenset[str] = frozenset()):
    """Yield "path=value" for every authority key that is not False.

    Driven by the document rather than by a fixed key list, so an authority key
    added to these files in future is rejected by default instead of being
    silently unchecked. A mapping under an authority key is a container of
    declarations, so the walk descends into it and judges each leaf.
    """
    if isinstance(node, dict):
        items = node.items()
    elif isinstance(node, list):
        items = ((str(i), v) for i, v in enumerate(node))
    else:
        return
    for key, value in items:
        path = f"{prefix}.{key}" if prefix else str(key)
        if isinstance(value, (dict, list)):
            yield from _authority_claims(value, path, exempt)
            continue
        key = str(key)
        if key in exempt:
            continue
        if (key == "authority" or key.endswith("_authority")) and value is not False:
            yield f"{path}:{key}"


def _load_json(path: Path) -> dict:
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError(f"mapping_required:{path}")
    return data


def _validate_subordinate_storage(root: Path, policy: dict) -> list[str]:
    """Storage gains nothing: pointers resolve, and every claim is rejected."""
    errors: list[str] = []
    subsystems = policy.get("subordinate_subsystems")
    block = subsystems.get("federated_free_storage_mesh") if isinstance(subsystems, dict) else None
    if not isinstance(block, dict):
        return ["universal_fabric_storage_subsystem_required"]

    if block.get("role") != "subordinate_persistence_and_placement":
        errors.append("universal_fabric_storage_role_must_be_subordinate")
    if block.get("canonical_authority") != "github":
        errors.append("universal_fabric_storage_canonical_authority_must_be_github")
    if block.get("second_portable_state_abstraction") is not False:
        errors.append("universal_fabric_storage_second_state_abstraction_forbidden")
    if block.get("learning_may_request_storage_classes") is not True:
        errors.append("universal_fabric_storage_learning_class_request_contract_required")
    for claim in _authority_claims(block, "storage", frozenset({"canonical_authority"})):
        errors.append(f"universal_fabric_storage_authority_claim_forbidden:{claim}")

    for key in FABRIC_TO_CHECKPOINT_POINTER:
        target = block.get(key)
        if not isinstance(target, str) or not target:
            errors.append(f"universal_fabric_storage_pointer_required:{key}")
        elif not (root / target).is_file():
            errors.append(f"universal_fabric_storage_pointer_unresolved:{key}")

    storage_policy = _load_yaml(root / STORAGE_POLICY_PATH)
    declared = storage_policy.get("authority")
    if not isinstance(declared, dict):
        errors.append("storage_policy_authority_block_required")
        declared = {}
    missing = sorted(REQUIRED_STORAGE_AUTHORITY_KEYS - set(declared))
    if missing:
        errors.append("storage_policy_authority_declarations_missing:" + ",".join(missing))
    for claim in _authority_claims(storage_policy, "storage_policy", frozenset({"canonical_authority"})):
        # canonical.authority *names* GITHUB_BRAIN_V4 rather than claiming
        # anything; it is checked by exact value just below. The exemption is by
        # exact path, so a nested authority key cannot hide under `canonical:`.
        if claim == "storage_policy.canonical.authority:authority":
            continue
        errors.append(f"storage_policy_authority_claim_forbidden:{claim}")
    canonical = storage_policy.get("canonical")
    canonical = canonical if isinstance(canonical, dict) else {}
    if canonical.get("authority") != "GITHUB_BRAIN_V4":
        errors.append("storage_canonical_authority_must_be_github_brain_v4")
    if canonical.get("routed_by") != "task_router":
        errors.append("storage_must_be_routed_by_task_router")
    if canonical.get("canonical_home") != "github":
        errors.append("storage_canonical_home_must_be_github")

    providers = _load_yaml(root / STORAGE_PROVIDERS_PATH)
    if providers.get("authority") is not False:
        errors.append("storage_provider_registry_must_not_be_authority")
    flags = providers.get("authority_flags")
    if not isinstance(flags, dict):
        errors.append("storage_provider_registry_authority_flags_required")
        flags = {}
    for claim in _authority_claims(
        {"authority_flags": flags}, "storage_providers", frozenset({"canonical_authority"})
    ):
        errors.append(f"storage_provider_registry_authority_claim_forbidden:{claim}")
    if providers.get("canonical_authority") != "GITHUB_BRAIN_V4":
        errors.append("storage_provider_registry_canonical_authority_must_be_github_brain_v4")

    errors += _validate_learning_storage_outputs(root, storage_policy, block)
    errors += _validate_checkpoint_storage_pointers(root, block)
    return errors


def _validate_learning_storage_outputs(root: Path, storage_policy: dict, block: dict) -> list[str]:
    """Learning may request a class. It may not pick a provider."""
    errors: list[str] = []
    learning_policy = _load_yaml(root / LEARNING_POLICY_PATH)
    if "storage_provider_selection_authority" not in learning_policy:
        errors.append("learning_storage_provider_selection_authority_declaration_required")
    if learning_policy.get("storage_provider_selection_authority", False) is not False:
        errors.append("learning_storage_provider_selection_authority_forbidden")
    if block.get("learning_storage_provider_selection_authority", False) is not False:
        errors.append("learning_storage_provider_selection_authority_forbidden")

    outputs = learning_policy.get("storage_outputs")
    if not isinstance(outputs, dict):
        return errors + ["learning_storage_output_contract_required"]
    for key in sorted(LEARNING_STORAGE_PERMISSIONS):
        if key not in outputs:
            errors.append(f"learning_storage_permission_declaration_required:{key}")
        elif outputs[key] is not False:
            errors.append(f"learning_storage_permission_forbidden:{key}")
    for key, value in outputs.items():
        if key == "may_request_storage_classes" or key in LEARNING_STORAGE_PERMISSIONS:
            continue
        if value is not False:
            errors.append(f"learning_storage_permission_forbidden:{key}")

    requested = outputs.get("may_request_storage_classes")
    if not isinstance(requested, list) or not requested:
        errors.append("learning_requested_storage_class_list_required")
        requested = []
    defined = storage_policy.get("criticality")
    defined = set(defined) if isinstance(defined, dict) else set()
    for name in requested:
        if name not in defined:
            errors.append(f"learning_requested_undefined_storage_class:{name}")
    return errors


def _validate_checkpoint_storage_pointers(root: Path, block: dict) -> list[str]:
    """The checkpoint adds pointers only - it does not move authority."""
    errors: list[str] = []
    checkpoint = _load_json(root / CHECKPOINT_PATH)
    for key, expected in CHECKPOINT_STORAGE_POINTERS.items():
        value = checkpoint.get(key)
        if key not in checkpoint:
            errors.append(f"checkpoint_storage_pointer_missing:{key}")
            continue
        if not isinstance(value, str) or not value:
            errors.append(f"checkpoint_storage_pointer_invalid:{key}")
            continue
        if value != expected:
            errors.append(f"checkpoint_storage_pointer_unexpected_target:{key}")
        if not (root / value).is_file():
            errors.append(f"checkpoint_storage_pointer_unresolved:{key}")
    for fabric_key, checkpoint_key in FABRIC_TO_CHECKPOINT_POINTER.items():
        if block.get(fabric_key) != checkpoint.get(checkpoint_key):
            errors.append(f"checkpoint_storage_pointer_disagrees_with_fabric:{checkpoint_key}")
    for key, value in checkpoint.items():
        if "storage" not in key:
            continue
        if not key.endswith("_path") or not isinstance(value, str):
            errors.append(f"checkpoint_storage_entry_must_be_a_pointer:{key}")
    for claim in _authority_claims(checkpoint, "checkpoint"):
        errors.append(f"checkpoint_authority_claim_forbidden:{claim}")
    return errors


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
    user_ids: set[str] = set()
    internal_ids: set[str] = set()
    for row in adapters:
        if not isinstance(row, dict):
            errors.append("adapter_row_must_be_mapping")
            continue
        adapter_id = str(row.get("id") or "").strip()
        principal_type = str(row.get("principal_type") or "user").strip().lower()
        binding = str(row.get("token_binding") or "").strip()
        scopes = row.get("scopes")
        if not adapter_id:
            errors.append("adapter_id_required")
        elif adapter_id in ids:
            errors.append(f"duplicate_adapter_id:{adapter_id}")
        ids.add(adapter_id)
        if principal_type not in PRINCIPAL_TYPES:
            errors.append(f"invalid_principal_type:{adapter_id or 'unknown'}")
        elif principal_type == "user":
            user_ids.add(adapter_id)
        else:
            internal_ids.add(adapter_id)
        if not binding:
            errors.append(f"token_binding_required:{adapter_id or 'unknown'}")
        elif binding in bindings:
            errors.append(f"duplicate_token_binding:{binding}")
        bindings.add(binding)
        if not isinstance(scopes, list) or not scopes:
            errors.append(f"scopes_required:{adapter_id or 'unknown'}")
            scopes = []
        if principal_type == "user" and "brain.route" not in scopes:
            errors.append(f"brain_route_scope_required:{adapter_id or 'unknown'}")
        if principal_type == "internal" and "brain.route" in scopes:
            errors.append(f"internal_route_scope_forbidden:{adapter_id or 'unknown'}")
        if row.get("routing_authority") is not False:
            errors.append(f"adapter_routing_authority_forbidden:{adapter_id or 'unknown'}")
        if row.get("reasoning_authority") is not False:
            errors.append(f"adapter_reasoning_authority_forbidden:{adapter_id or 'unknown'}")

    if user_ids != {"chatgpt", "claude", "gemini"}:
        errors.append("initial_user_adapter_set_must_be_chatgpt_claude_gemini")
    if internal_ids and internal_ids != {"evergreen"}:
        errors.append("unexpected_internal_principal")

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

    errors += _validate_subordinate_storage(root, policy)

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
