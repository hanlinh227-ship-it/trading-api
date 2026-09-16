from __future__ import annotations

from copy import deepcopy
from typing import Any

_ALLOWED_LICENSES = {"MIT", "Apache-2.0", "BSD-2-Clause", "BSD-3-Clause", "CC0-1.0", "Unlicense"}
_ACTIVE_MAINTENANCE = {"active", "maintained", "supported"}


def _strings(value: Any) -> list[str]:
    if not isinstance(value, list):
        return []
    out: list[str] = []
    seen: set[str] = set()
    for item in value:
        text = str(item or "").strip()
        if text and text not in seen:
            seen.add(text)
            out.append(text)
    return out


def normalize_source(row: dict) -> dict:
    if not isinstance(row, dict):
        raise ValueError("source_must_be_object")
    required = ("source_id", "source_type", "location", "pinned_revision", "license", "maintenance_status", "capabilities")
    missing = [key for key in required if row.get(key) in (None, "")]
    if missing:
        raise ValueError("missing_source_fields:" + ",".join(sorted(missing)))
    source = deepcopy(row)
    source_id = str(source["source_id"]).strip()
    source_type = str(source["source_type"]).strip().lower()
    location = str(source["location"]).strip()
    revision = str(source["pinned_revision"]).strip()
    license_name = str(source["license"]).strip()
    maintenance = str(source["maintenance_status"]).strip().lower()
    capabilities = _strings(source.get("capabilities"))
    if not source_id or not location or not revision or not capabilities:
        raise ValueError("invalid_source_metadata")

    block_reasons: list[str] = []
    if license_name not in _ALLOWED_LICENSES:
        block_reasons.append("license")
    if maintenance not in _ACTIVE_MAINTENANCE:
        block_reasons.append("maintenance")
    if source.get("critical_security_risk") is True:
        block_reasons.append("security")
    if source.get("hidden_permission_expansion") is True:
        block_reasons.append("permission_expansion")

    if block_reasons:
        state = "blocked"
    elif source.get("stale") is True:
        state = "stale"
    elif source.get("approved") is True:
        state = "active"
    else:
        state = "candidate"

    return {
        "source_id": source_id,
        "source_type": source_type,
        "location": location,
        "pinned_revision": revision,
        "license": license_name,
        "maintenance_status": maintenance,
        "approved": source.get("approved") is True,
        "capabilities": capabilities,
        "state": state,
        "block_reasons": sorted(set(block_reasons)),
        "routing_authority": False,
        "reasoning_authority": False,
        "stable_write": False,
    }


def capability_diff(active: dict, upstream: dict) -> dict[str, str]:
    active_caps = active.get("capabilities", {}) if isinstance(active, dict) else {}
    if isinstance(active_caps, list):
        active_caps = {str(cap): {} for cap in active_caps}
    if not isinstance(active_caps, dict):
        active_caps = {}
    upstream_caps = _strings(upstream.get("capabilities", [])) if isinstance(upstream, dict) else []
    conflicts = set(_strings(upstream.get("conflicts", []))) if isinstance(upstream, dict) else set()
    security_blocked = set(_strings(upstream.get("security_blocked", []))) if isinstance(upstream, dict) else set()
    already = set(_strings(upstream.get("already_assimilated", []))) if isinstance(upstream, dict) else set()
    stale = set(_strings(upstream.get("stale_capabilities", []))) if isinstance(upstream, dict) else set()
    license_blocked = set(_strings(upstream.get("license_blocked", []))) if isinstance(upstream, dict) else set()

    result: dict[str, str] = {}
    for capability in upstream_caps:
        if capability in security_blocked:
            result[capability] = "blocked_security"
        elif capability in license_blocked:
            result[capability] = "blocked_license"
        elif capability in conflicts:
            result[capability] = "conflict"
        elif capability in stale:
            result[capability] = "stale"
        elif capability in already:
            result[capability] = "already_assimilated"
        elif capability in active_caps:
            result[capability] = "strengthen_existing"
        else:
            result[capability] = "distinct_candidate"
    return result
