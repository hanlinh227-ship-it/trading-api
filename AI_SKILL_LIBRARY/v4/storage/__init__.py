"""Federated Free Storage Mesh - canonical contracts.

A subordinate persistence and placement subsystem. It is not a Brain, a router,
a scheduler, a model mesh, a memory authority or a second portable storage
abstraction; it extends the existing ``ObjectStore`` interface declared in
``AI_SKILL_LIBRARY/v4/runtime/shared_state.yaml``, and GitHub remains canonical.

This module holds the canonical vocabularies and the paths to the documents
that define them. It performs no placement, opens no connection, reads no
credential and activates no provider account. The enums are mirrored here
rather than parsed on import so that callers get a stable import-time constant;
``tests/test_storage_mesh_contracts.py`` asserts they have not drifted from
``policy.yaml``, which is the authority for all four vocabularies.
"""

from __future__ import annotations

#: This package holds no authority of any kind. Denied by name rather than by
#: omission, so that a later document cannot acquire one by adding a key.
AUTHORITY = False
AUTHORITY_FLAGS = (
    "storage_authority",
    "routing_authority",
    "reasoning_authority",
    "model_selection_authority",
    "admission_authority",
    "scheduling_authority",
    "merge_authority",
    "trading_authority",
)

CANONICAL_AUTHORITY = "GITHUB_BRAIN_V4"
ROUTED_BY = "task_router"

#: The one portable state contract. The mesh extends this interface; it does
#: not replace it and does not stand up a parallel one.
PORTABLE_STATE_CONTRACT = "AI_SKILL_LIBRARY/v4/runtime/shared_state.yaml"
EXTENDS_INTERFACE = "ObjectStore"

POLICY_PATH = "AI_SKILL_LIBRARY/v4/storage/policy.yaml"
PROVIDERS_PATH = "AI_SKILL_LIBRARY/v4/storage/providers.yaml"
OBJECT_MANIFEST_SCHEMA_PATH = "AI_SKILL_LIBRARY/v4/schemas/storage_object_manifest.schema.json"
PROVIDER_SCHEMA_PATH = "AI_SKILL_LIBRARY/v4/schemas/storage_provider.schema.json"

PRIVACY_CLASSES = ("PUBLIC", "INTERNAL", "CONFIDENTIAL", "LOCAL_ONLY")
CRITICALITY_CLASSES = ("CRITICAL", "IMPORTANT", "REPRODUCIBLE", "EPHEMERAL")
STORAGE_TIERS = ("CANONICAL", "HOT", "WARM", "COLD", "HUMAN_BACKUP", "METADATA")

#: Spec S12. The mesh's own object lifecycle; it names no runtime, residency or
#: governance state belonging to another plane.
LIFECYCLE_STATES = (
    "RAW", "SANITIZED", "DEDUPED", "AGGREGATED", "COMPRESSED", "ARCHIVED", "EXPIRED",
)

#: Spec S10. There is no UNKNOWN: a provider nobody has probed is QUARANTINED,
#: which is the same fact stated so that it fails closed.
PROVIDER_HEALTH_STATES = (
    "FREE", "HEALTHY", "PRESSURED", "NEAR_FULL", "READ_ONLY", "QUARANTINED", "OFFLINE",
)

#: Spec S5. Capacity never overrides privacy; free capacity never overrides
#: integrity; latency never overrides the zero-cost policy.
PLACEMENT_ORDER = (
    "privacy",
    "integrity_criticality",
    "free_only_eligibility",
    "provider_health",
    "quota_headroom",
    "object_size",
    "access_frequency",
    "retention_class",
    "latency",
    "backend_choice",
)

#: Spec S11.
PAID_STORAGE_ALLOWED = False
OVERAGE_ALLOWED = False
UNKNOWN_COST_STATE = "QUARANTINE"
BILLABLE_SPILLOVER_UNVERIFIED = "NO_AUTONOMOUS_WRITE"
FREE_EXPIRY_UNKNOWN = "NO_AUTONOMOUS_WRITE"

#: The encryption contract is defined and implemented elsewhere. These
#: contracts declare the metadata fields only; no cryptography is invented,
#: chosen or performed in this package.
ENCRYPTION_IMPLEMENTED_HERE = False

__all__ = [
    "AUTHORITY", "AUTHORITY_FLAGS", "CANONICAL_AUTHORITY", "ROUTED_BY",
    "PORTABLE_STATE_CONTRACT", "EXTENDS_INTERFACE", "POLICY_PATH",
    "PROVIDERS_PATH", "OBJECT_MANIFEST_SCHEMA_PATH", "PROVIDER_SCHEMA_PATH",
    "PRIVACY_CLASSES", "CRITICALITY_CLASSES", "STORAGE_TIERS",
    "LIFECYCLE_STATES", "PROVIDER_HEALTH_STATES", "PLACEMENT_ORDER",
    "PAID_STORAGE_ALLOWED", "OVERAGE_ALLOWED", "UNKNOWN_COST_STATE",
    "BILLABLE_SPILLOVER_UNVERIFIED", "FREE_EXPIRY_UNKNOWN",
    "ENCRYPTION_IMPLEMENTED_HERE",
]
