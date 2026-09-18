"""Federated Free Storage Mesh - registry-aware contract validation.

The two JSON Schemas in ``AI_SKILL_LIBRARY/v4/schemas`` do most of the work, but
a JSON Schema validates one document in isolation. It cannot open
``providers.yaml``, it cannot compare two numbers in the same document, and it
cannot compare a timestamp to now. Those three blind spots were exactly where
the holes were:

* a manifest could name ``some_random_untrusted_host`` as its primary backend,
  because the schema checked the *shape* of a backend id and never its
  *identity*, and could name a registry row that had been admitted for nothing;
* a provider row could be quota_used 999999 of quota_total 100, or carry a
  ``free_expiry_at`` that passed months ago, and still be a fully autonomous
  writer.

This module closes them. It is the manifest-side half of provider admission:
every backend a manifest names is resolved to its registry row, and that row's
admission state - verified free tier, writable health, permitted privacy class,
permitted tier, bulk-object role, quota headroom - decides whether the placement
is admissible. Spec S5 is honoured in order: privacy is evaluated before
capacity and a capacity result never overturns a privacy one.

It is read-only and pure. It opens no connection, activates no provider account,
touches no credential, creates nothing and writes nothing - it reads the two
canonical YAML documents and returns a list of strings. It holds no authority;
GITHUB_BRAIN_V4 remains canonical and ``policy.yaml`` remains the authority for
every vocabulary named here.

Every function returns ``[]`` for an admissible document and a list of
human-readable violations otherwise. Nothing raises for a policy violation,
because a validator that raises encourages a caller to wrap it in a bare
``except`` and continue.
"""

from __future__ import annotations

import datetime as _datetime
from pathlib import Path

import yaml

#: This module holds no authority of any kind, matching the rest of the lane.
AUTHORITY = False
CANONICAL_AUTHORITY = "GITHUB_BRAIN_V4"

_HERE = Path(__file__).resolve().parent
POLICY_PATH = _HERE / "policy.yaml"
PROVIDERS_PATH = _HERE / "providers.yaml"

#: Spec S6 / policy.yaml ``tiers.*.bulk_object_data_allowed``. CANONICAL lives on
#: GitHub and METADATA is an index; both hold pointers, not payloads. The same
#: number bounds the metadata service in storage_provider.schema.json and the two
#: bulk tiers in storage_object_manifest.schema.json, so the three cannot drift.
BULK_OBJECT_THRESHOLD_BYTES = 1048576

#: Spec S6: the tiers whose whole definition excludes bulk object data.
NON_BULK_TIERS = frozenset({"CANONICAL", "METADATA"})

#: Spec S10. PRESSURED is writable - it is the warning state, not the stop
#: state. NEAR_FULL is not: it sits at or past the 0.92 hard limit, and S10 says
#: no provider should be driven to 100% while another eligible target exists.
WRITABLE_HEALTH_STATES = frozenset({"FREE", "HEALTHY", "PRESSURED"})

#: Spec S16/S20. The only two free_status values that runtime account evidence
#: can produce, and therefore the only two that mean "admitted".
VERIFIED_FREE_STATUSES = frozenset({"VERIFIED_FREE", "VERIFIED_RECURRING_FREE"})


def _read_yaml(path):
    return yaml.safe_load(Path(path).read_text(encoding="utf-8"))


def load_policy(path=None):
    """Read policy.yaml. Read-only; the caller receives a plain mapping."""
    return _read_yaml(path or POLICY_PATH)


def load_providers(path=None):
    """Read the provider registry rows. Registry membership is not admission."""
    return list((_read_yaml(path or PROVIDERS_PATH) or {}).get("providers") or [])


def _parse_instant(value):
    """Parse an RFC 3339 instant into an aware datetime, or None."""
    if not isinstance(value, str):
        return None
    text = value.replace("Z", "+00:00")
    try:
        parsed = _datetime.datetime.fromisoformat(text)
    except ValueError:
        return None
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=_datetime.timezone.utc)
    return parsed


def _now(now):
    if now is None:
        return _datetime.datetime.now(_datetime.timezone.utc)
    parsed = _parse_instant(now) if isinstance(now, str) else now
    if parsed is None:
        return _datetime.datetime.now(_datetime.timezone.utc)
    return parsed


def _wants_write(row):
    return bool(row.get("autonomous_write_allowed")) or bool(row.get("write_enabled"))


def validate_provider_row(row, *, now=None):
    """Check one registry row for the incoherences a JSON Schema cannot see.

    Two numbers in the same document and one timestamp against the clock. Both
    fail closed: an incoherent quota and an expired free tier remove the right
    to write, they do not merely annotate it.
    """
    problems = []
    provider_id = row.get("provider_id", "<unnamed>")
    total = row.get("quota_total")
    used = row.get("quota_used")
    reserved = row.get("quota_reserved")

    # Two numbers in one document. Incoherent regardless of write intent: a
    # registry that records an impossible fact is not recording a fact.
    if isinstance(total, int) and isinstance(used, int) and used > total:
        problems.append(
            f"{provider_id}: quota_used {used} exceeds quota_total {total}; "
            "no headroom can be computed from an impossible pair")
    if (isinstance(total, int) and isinstance(used, int)
            and isinstance(reserved, int) and used + reserved > total):
        problems.append(
            f"{provider_id}: quota_used plus quota_reserved exceeds quota_total")

    # Spec S11: a free tier with a date already behind us is not a free tier.
    # The schema could only reach the null case; a past date needs a clock.
    expiry = _parse_instant(row.get("free_expiry_at"))
    if expiry is not None and expiry <= _now(now) and _wants_write(row):
        problems.append(
            f"{provider_id}: free tier expired at {row['free_expiry_at']}; "
            "writes must be withdrawn, not merely noted")

    # Spec S10: health and the write flags must agree. The schema pins this too;
    # it is repeated here so a row reaching the validator by another path (an
    # unvalidated runtime snapshot, say) is still caught.
    health = row.get("health")
    if health not in WRITABLE_HEALTH_STATES and _wants_write(row):
        problems.append(
            f"{provider_id}: health {health} is not a writable state")

    if row.get("autonomous_write_allowed") and not row.get("write_enabled"):
        problems.append(
            f"{provider_id}: autonomous_write_allowed without write_enabled")

    if row.get("external") and _wants_write(row):
        if row.get("free_status") not in VERIFIED_FREE_STATUSES:
            problems.append(
                f"{provider_id}: free_status {row.get('free_status')} is not "
                "verified free; writes are not admitted")
        if total is None or used is None:
            problems.append(
                f"{provider_id}: quota is unknowable (quota_total or quota_used "
                "is null) and no capacity limit can be honoured")

    # A health claim needs a probe behind it - local rows included.
    if health != "QUARANTINED" and row.get("last_probe_at") is None:
        problems.append(
            f"{provider_id}: health {health} claimed with last_probe_at null; "
            "an unprobed provider is QUARANTINED")

    return problems


def _resolve(backend_id, by_id):
    return by_id.get(backend_id)


def _placement_problems(manifest, row, backend_id, role, policy, require_writable):
    """Spec S5 order: privacy, then integrity, then eligibility, then capacity."""
    problems = []
    provider_id = row.get("provider_id", backend_id)
    label = f"{role} backend {provider_id}"
    privacy_class = manifest.get("privacy_class")
    tier = manifest.get("storage_tier")
    size = manifest.get("size_bytes")
    external = bool(row.get("external"))

    # 1. Privacy. Evaluated first and never overturned by anything below it.
    if external and privacy_class == "LOCAL_ONLY":
        problems.append(f"{label}: privacy class LOCAL_ONLY may not leave owned storage")
    if privacy_class not in (row.get("privacy_classes_allowed") or []):
        problems.append(
            f"{label}: privacy class {privacy_class} is not admitted on this "
            "provider")
    if external and privacy_class in (row.get("encryption_required_classes") or []):
        if manifest.get("encryption_state") != "CLIENT_SIDE_ENCRYPTED" or not manifest.get("encryption"):
            problems.append(
                f"{label}: privacy class {privacy_class} requires client-side "
                "encryption metadata on this provider")

    # The policy gate the manifest schema could not read. INTERNAL is
    # verified_only and CONFIDENTIAL is encrypted_verified_only; PUBLIC is
    # "any admitted free backend whose terms and health are verified" (Spec S4),
    # so every external residency needs a verified row, not merely a listed one.
    if external:
        eligibility = ((policy or {}).get("privacy") or {}).get(privacy_class) or {}
        if eligibility.get("external_backends_allowed") is False:
            problems.append(
                f"{label}: policy forbids external backends for {privacy_class}")
        elif row.get("free_status") not in VERIFIED_FREE_STATUSES:
            problems.append(
                f"{label}: privacy class {privacy_class} requires a verified "
                f"provider; free_status is {row.get('free_status')}")

    # 2. Role and tier. A metadata service is not a bulk backend whatever the
    # placement logic would prefer.
    if tier not in (row.get("tiers_allowed") or []):
        problems.append(f"{label}: does not serve storage tier {tier}")
    if row.get("bulk_object_backend_allowed") is not True:
        if isinstance(size, int) and size > BULK_OBJECT_THRESHOLD_BYTES:
            problems.append(
                f"{label}: is not a bulk object backend and cannot hold "
                f"{size} bytes")
        if tier not in NON_BULK_TIERS:
            problems.append(
                f"{label}: is not a bulk object backend, so tier {tier} is not "
                "admissible on it")
    if tier in NON_BULK_TIERS and isinstance(size, int) and size > BULK_OBJECT_THRESHOLD_BYTES:
        problems.append(
            f"{label}: tier {tier} carries no bulk object data ({size} bytes)")

    limits = row.get("object_size_limits") or {}
    max_bytes = limits.get("max_object_bytes")
    if isinstance(max_bytes, int) and isinstance(size, int) and size > max_bytes:
        problems.append(f"{label}: object exceeds the provider's max_object_bytes")

    # 3. Capacity and write admission. Last, so it can only narrow.
    if require_writable:
        if not row.get("write_enabled"):
            problems.append(f"{label}: is not write-enabled")
        if row.get("health") not in WRITABLE_HEALTH_STATES:
            problems.append(
                f"{label}: health {row.get('health')} is not a writable state")
        total = row.get("quota_total")
        used = row.get("quota_used") or 0
        if external and total is None:
            problems.append(f"{label}: quota is unknowable; no write is admissible")
        elif isinstance(total, int) and isinstance(size, int) and used + size > total:
            problems.append(f"{label}: placement would exceed the verified quota")

    return problems


def validate_manifest_placement(manifest, providers=None, *, policy=None,
                                require_writable=True, now=None):
    """Resolve every backend a manifest names against the provider registry.

    This is the linkage the manifest schema cannot express. The schema decides
    that a backend id is one of the registry's keys; this decides whether that
    row was actually admitted for this object's privacy class, tier and size,
    and - when ``require_writable`` is set, which is the placement case - whether
    it is in a state that may receive a byte at all.

    ``require_writable=False`` answers the narrower question "is this an
    admissible residency for an object already stored", which is the form used
    when reading or re-verifying rather than placing.
    """
    rows = load_providers() if providers is None else list(providers)
    policy = load_policy() if policy is None else policy
    by_id = {row.get("provider_id"): row for row in rows}
    problems = []

    primary = manifest.get("primary_backend")
    replicas = list(manifest.get("replica_backends") or [])

    for role, backend_id in [("primary", primary)] + [("replica", r) for r in replicas]:
        if backend_id is None:
            problems.append(f"{role} backend is absent")
            continue
        row = _resolve(backend_id, by_id)
        if row is None:
            problems.append(
                f"{role} backend {backend_id!r} is not a row in the provider "
                "registry; a manifest may only name an admitted backend")
            continue
        problems.extend(_placement_problems(
            manifest, row, backend_id, role, policy, require_writable))
        problems.extend(validate_provider_row(row, now=now))

    if primary is not None and primary in replicas:
        problems.append(
            f"primary backend {primary} is also listed as a replica; a replica "
            "is an independent copy (Spec S9)")

    return problems


def validate_registry(providers=None, *, now=None):
    """Check every shipped registry row. Read-only, same as everything here."""
    rows = load_providers() if providers is None else list(providers)
    problems = []
    for row in rows:
        problems.extend(validate_provider_row(row, now=now))
    return problems


__all__ = [
    "AUTHORITY", "CANONICAL_AUTHORITY", "BULK_OBJECT_THRESHOLD_BYTES",
    "NON_BULK_TIERS", "WRITABLE_HEALTH_STATES", "VERIFIED_FREE_STATUSES",
    "load_policy", "load_providers", "validate_provider_row",
    "validate_manifest_placement", "validate_registry",
]
