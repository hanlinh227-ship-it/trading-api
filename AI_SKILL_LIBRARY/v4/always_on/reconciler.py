"""Pure deterministic desired-vs-observed reconciliation for always-on work.

Non-authoritative helper module. It performs no I/O, no network access, no
busy polling, no model selection, no routing, no scheduling, and no trade
authority. It only emits advisory actions for callers that own authority.
"""

from __future__ import annotations

from typing import Any, Dict, List, Mapping, Sequence

REQUEUE_EXPIRED_LEASE = "REQUEUE_EXPIRED_LEASE"
QUARANTINE_PROVIDER = "QUARANTINE_PROVIDER"
REQUEST_REPLICA_REPAIR = "REQUEST_REPLICA_REPAIR"
EXCLUDE_STALE_WORKER = "EXCLUDE_STALE_WORKER"

_ALLOWED_ACTIONS = frozenset(
    {
        REQUEUE_EXPIRED_LEASE,
        QUARANTINE_PROVIDER,
        REQUEST_REPLICA_REPAIR,
        EXCLUDE_STALE_WORKER,
    }
)


def _as_sequence(value: object) -> Sequence[Any]:
    if isinstance(value, (list, tuple)):
        return value
    return ()


def _as_mapping(value: object) -> Mapping[str, Any]:
    if isinstance(value, Mapping):
        return value
    return {}


def _text(value: object) -> str:
    if isinstance(value, str):
        return value.strip()
    return ""


def _positive_int(value: object) -> int:
    if isinstance(value, int) and not isinstance(value, bool) and value > 0:
        return value
    return 0


def _action(name: str, target: str, reason: str) -> Dict[str, str]:
    return {"action": name, "target": target, "reason": reason}


def reconcile(desired: object, observed: object) -> List[Dict[str, str]]:
    """Return a deterministic, deduplicated list of advisory actions.

    Inputs are read-only and never mutated. Malformed inputs yield no actions
    (fail closed). Duplicate desired or observed entries cannot produce
    duplicate actions.
    """
    desired_map = _as_mapping(desired)
    observed_map = _as_mapping(observed)

    actions: List[Dict[str, str]] = []
    seen: set = set()

    def emit(name: str, target: str, reason: str) -> None:
        if name not in _ALLOWED_ACTIONS or not target:
            return
        key = (name, target)
        if key in seen:
            return
        seen.add(key)
        actions.append(_action(name, target, reason))

    desired_leases = _as_sequence(desired_map.get("leases"))
    observed_leases = _as_sequence(observed_map.get("leases"))

    observed_lease_ids = set()
    for entry in observed_leases:
        lease = _as_mapping(entry)
        lease_id = _text(lease.get("id"))
        if lease_id:
            observed_lease_ids.add(lease_id)

    for entry in desired_leases:
        lease = _as_mapping(entry)
        lease_id = _text(lease.get("id"))
        if not lease_id:
            continue
        if lease_id not in observed_lease_ids:
            emit(REQUEUE_EXPIRED_LEASE, lease_id, "desired lease missing from observed state")

    for entry in observed_leases:
        lease = _as_mapping(entry)
        lease_id = _text(lease.get("id"))
        if not lease_id:
            continue
        if lease.get("expired") is True:
            emit(REQUEUE_EXPIRED_LEASE, lease_id, "observed lease expired")

    desired_providers = _as_sequence(desired_map.get("providers"))
    observed_providers = _as_sequence(observed_map.get("providers"))

    observed_provider_ids = set()
    for entry in observed_providers:
        provider = _as_mapping(entry)
        provider_id = _text(provider.get("id"))
        if provider_id:
            observed_provider_ids.add(provider_id)

    for entry in desired_providers:
        provider = _as_mapping(entry)
        provider_id = _text(provider.get("id"))
        if not provider_id:
            continue
        if provider_id not in observed_provider_ids:
            emit(QUARANTINE_PROVIDER, provider_id, "desired provider missing from observed state")

    for entry in observed_providers:
        provider = _as_mapping(entry)
        provider_id = _text(provider.get("id"))
        if not provider_id:
            continue
        if provider.get("healthy") is False:
            emit(QUARANTINE_PROVIDER, provider_id, "observed provider unhealthy")

    desired_replicas = _as_sequence(desired_map.get("replicas"))
    observed_replicas = _as_sequence(observed_map.get("replicas"))

    observed_replica_ids = set()
    for entry in observed_replicas:
        replica = _as_mapping(entry)
        replica_id = _text(replica.get("id"))
        if replica_id:
            observed_replica_ids.add(replica_id)

    for entry in desired_replicas:
        replica = _as_mapping(entry)
        replica_id = _text(replica.get("id"))
        if not replica_id:
            continue
        if replica_id not in observed_replica_ids:
            emit(REQUEST_REPLICA_REPAIR, replica_id, "desired replica missing from observed state")

    for entry in observed_replicas:
        replica = _as_mapping(entry)
        replica_id = _text(replica.get("id"))
        if not replica_id:
            continue
        if replica.get("healthy") is False:
            emit(REQUEST_REPLICA_REPAIR, replica_id, "observed replica unhealthy")

    desired_workers = _as_sequence(desired_map.get("workers"))
    observed_workers = _as_sequence(observed_map.get("workers"))

    observed_worker_ids = set()
    for entry in observed_workers:
        worker = _as_mapping(entry)
        worker_id = _text(worker.get("id"))
        if worker_id:
            observed_worker_ids.add(worker_id)

    for entry in desired_workers:
        worker = _as_mapping(entry)
        worker_id = _text(worker.get("id"))
        if not worker_id:
            continue
        if worker_id not in observed_worker_ids:
            emit(EXCLUDE_STALE_WORKER, worker_id, "desired worker missing from observed state")

    for entry in observed_workers:
        worker = _as_mapping(entry)
        worker_id = _text(worker.get("id"))
        if not worker_id:
            continue
        if worker.get("stale") is True:
            emit(EXCLUDE_STALE_WORKER, worker_id, "observed worker stale")
        elif _positive_int(worker.get("heartbeat_age_seconds")) > 0 and worker.get("stale") is not False:
            if worker.get("stale") is True:
                emit(EXCLUDE_STALE_WORKER, worker_id, "observed worker stale")

    return actions
