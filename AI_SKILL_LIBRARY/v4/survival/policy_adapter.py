"""Survival Plane policy adapter (Tasks 1-2).

Evaluates an input document against the survival policy and fails closed for
LOCAL_ONLY placement violations, paid paths, and unverified providers.
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

import yaml

_POLICY_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "policy.yaml")

_DEFAULT_POLICY: Dict[str, Any] = {
    "version": 1,
    "name": "survival_policy",
    "fail_closed": True,
    "authority": {
        "routing": False,
        "reasoning": False,
        "scheduling": False,
        "merge": False,
        "deployment": False,
        "trading": False,
    },
    "placement": {"allowed": ["LOCAL_ONLY"], "deny_remote": True},
    "paid_paths": {
        "deny": True,
        "markers": [
            "paid",
            "billing",
            "invoice",
            "charge",
            "subscription",
            "premium",
        ],
    },
    "providers": {"verified": ["local", "local_vault"], "deny_unverified": True},
    "secrets": {
        "allow_plaintext_serialization": False,
        "log_values": False,
        "persist_values": False,
    },
}


def load_policy(path: Optional[str] = None) -> Dict[str, Any]:
    """Load the YAML policy, falling back to the embedded fail-closed default."""
    target = path or _POLICY_PATH
    try:
        with open(target, "r", encoding="utf-8") as handle:
            loaded = yaml.safe_load(handle)
    except (OSError, yaml.YAMLError):
        return dict(_DEFAULT_POLICY)
    if not isinstance(loaded, dict):
        return dict(_DEFAULT_POLICY)
    return loaded


@dataclass(frozen=True)
class Decision:
    allow: bool
    reasons: List[str] = field(default_factory=list)


def _as_list(value: Any) -> List[str]:
    if value is None:
        return []
    if isinstance(value, str):
        return [value]
    if isinstance(value, (list, tuple, set)):
        return [str(item) for item in value]
    return [str(value)]


def _collect_strings(value: Any) -> List[str]:
    found: List[str] = []
    if isinstance(value, str):
        found.append(value)
    elif isinstance(value, dict):
        for key, item in value.items():
            found.append(str(key))
            found.extend(_collect_strings(item))
    elif isinstance(value, (list, tuple, set)):
        for item in value:
            found.extend(_collect_strings(item))
    return found


def evaluate_policy(input_doc: Any, policy: Optional[Dict[str, Any]] = None) -> Decision:
    """Evaluate an input document against the survival policy.

    Fails closed: any violation yields allow=False with explicit reasons.
    """
    active = policy if isinstance(policy, dict) else load_policy()
    reasons: List[str] = []

    if not isinstance(input_doc, dict):
        return Decision(allow=False, reasons=["invalid_input_document"])

    placement_cfg = active.get("placement") or {}
    allowed_placement = {item.upper() for item in _as_list(placement_cfg.get("allowed"))}
    if not allowed_placement:
        allowed_placement = {"LOCAL_ONLY"}

    placement = input_doc.get("placement")
    if placement is None:
        reasons.append("missing_placement")
    else:
        placement_value = str(placement).upper()
        if placement_value not in allowed_placement:
            reasons.append("placement_not_local_only")
        if placement_cfg.get("deny_remote", True) and placement_value != "LOCAL_ONLY":
            reasons.append("remote_placement_denied")

    paid_cfg = active.get("paid_paths") or {}
    if paid_cfg.get("deny", True):
        markers = [m.lower() for m in _as_list(paid_cfg.get("markers"))]
        if not markers:
            markers = ["paid", "billing", "invoice", "charge", "subscription", "premium"]
        haystack = " ".join(_collect_strings(input_doc)).lower()
        for marker in markers:
            if marker and marker in haystack:
                reasons.append("paid_path_denied")
                break

    provider_cfg = active.get("providers") or {}
    if provider_cfg.get("deny_unverified", True):
        verified = {p.lower() for p in _as_list(provider_cfg.get("verified"))}
        if not verified:
            verified = {"local", "local_vault"}
        provider = input_doc.get("provider")
        if provider is None:
            reasons.append("missing_provider")
        elif str(provider).lower() not in verified:
            reasons.append("unverified_provider")

    authority_cfg = active.get("authority") or {}
    for key in ("routing", "reasoning", "scheduling", "merge", "deployment", "trading"):
        if authority_cfg.get(key, False):
            reasons.append("authority_escalation_%s" % key)

    if reasons:
        return Decision(allow=False, reasons=reasons)
    return Decision(allow=True, reasons=[])
