from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml

ROOT = Path(__file__).resolve().parents[3]
ADAPTERS_PATH = ROOT / "AI_SKILL_LIBRARY/v4/runtime/client_adapters.yaml"

_DATA_CLASSES = {"PUBLIC", "INTERNAL", "CONFIDENTIAL", "SECRET"}
_FRESHNESS = {"none", "normal", "current", "live"}
_ACTIONS = {
    "informational",
    "ordinary_research",
    "artifact_creation",
    "project_context",
    "external_tool",
    "live_or_trading",
    "deployment_or_runtime_claim",
    "credential_sensitive",
    "financial",
    "destructive",
    "permission_change",
}
_DEEP_ACTIONS = {
    "live_or_trading",
    "deployment_or_runtime_claim",
    "credential_sensitive",
    "financial",
    "destructive",
    "permission_change",
}
_STANDARD_ACTIONS = {"ordinary_research", "artifact_creation", "project_context", "external_tool"}
_HIGH_IMPACT = set(_DEEP_ACTIONS)

_DEEP_TERMS = {
    "live_or_trading": (" live", "realtime", "real-time", "trading", "giao dịch", "market entry", "tìm entry", "quét giá", "giá hiện tại"),
    "deployment_or_runtime_claim": ("deploy", "production", "runtime", "triển khai"),
    "credential_sensitive": ("credential", "api key", "private key", "mật khẩu", "secret"),
    "financial": ("thanh toán", "chuyển tiền", "withdraw", "rút tiền", "financial action", "wallet signing"),
    "destructive": ("xóa dữ liệu", "delete production", "destroy", "destructive"),
    "permission_change": ("permission", "phân quyền", "cấp quyền", "revoke scope"),
}
_STANDARD_TERMS = {
    "ordinary_research": ("nghiên cứu", "tìm nguồn", "research"),
    "artifact_creation": ("tạo file", "tạo báo cáo", "artifact", "docx", "pdf", "pptx", "spreadsheet"),
    "project_context": ("project", "dự án", "repo", "repository"),
    "external_tool": ("dùng công cụ", "tool", "connector", "plugin"),
}


def _load_adapters() -> dict[str, dict[str, Any]]:
    data = yaml.safe_load(ADAPTERS_PATH.read_text(encoding="utf-8"))
    rows = data.get("adapters", {}) if isinstance(data, dict) else {}
    if not isinstance(rows, dict):
        raise ValueError("client adapter registry must be a mapping")
    return {str(key): dict(value) for key, value in rows.items() if isinstance(value, dict)}


def _bounded_string_list(value: Any, *, max_items: int = 32, max_chars: int = 80) -> list[str]:
    if value is None:
        return []
    if not isinstance(value, list) or len(value) > max_items:
        raise ValueError("invalid_string_list")
    result: list[str] = []
    seen: set[str] = set()
    for item in value:
        if not isinstance(item, str):
            raise ValueError("invalid_string_list_item")
        item = item.strip()
        if not item or len(item) > max_chars:
            raise ValueError("invalid_string_list_item")
        if item not in seen:
            seen.add(item)
            result.append(item)
    return result


def _infer_action(text: str, freshness: str, tool_classes: list[str]) -> str:
    lowered = f" {text.casefold()}"
    if freshness == "live":
        return "live_or_trading"
    for action, terms in _DEEP_TERMS.items():
        if any(term in lowered for term in terms):
            return action
    if "artifact_creation" in tool_classes:
        return "artifact_creation"
    if tool_classes:
        return "external_tool"
    for action, terms in _STANDARD_TERMS.items():
        if any(term in lowered for term in terms):
            return action
    return "informational"


def normalize_request(payload: dict, adapter_id: str) -> dict:
    if not isinstance(payload, dict):
        raise ValueError("request_must_be_object")
    adapters = _load_adapters()
    adapter_id = str(adapter_id or "").strip().lower()
    adapter = adapters.get(adapter_id)
    if not adapter:
        raise ValueError("unknown_adapter")

    text = payload.get("text")
    if not isinstance(text, str) or not text.strip() or len(text) > 20_000:
        raise ValueError("invalid_text")
    request_id = payload.get("request_id")
    session_id = payload.get("session_id")
    if not isinstance(request_id, str) or not request_id.strip() or len(request_id) > 160:
        raise ValueError("invalid_request_id")
    if not isinstance(session_id, str) or not session_id.strip() or len(session_id) > 160:
        raise ValueError("invalid_session_id")

    freshness = str(payload.get("freshness") or "none").strip().lower()
    if freshness not in _FRESHNESS:
        freshness = "current"

    raw_data_class = str(payload.get("data_class") or "PUBLIC").strip().upper()
    data_class = raw_data_class if raw_data_class in _DATA_CLASSES else "SECRET"

    declared_capabilities = _bounded_string_list(payload.get("declared_capabilities"))
    tool_classes = _bounded_string_list(payload.get("tool_classes"))

    explicit_action = str(payload.get("requested_action_class") or "").strip().lower()
    action = explicit_action if explicit_action in _ACTIONS else _infer_action(text, freshness, tool_classes)

    project_hint = payload.get("project_hint")
    if project_hint is not None:
        if not isinstance(project_hint, str) or len(project_hint) > 160:
            raise ValueError("invalid_project_hint")
        project_hint = project_hint.strip() or None

    return {
        "client_id": adapter_id,
        "adapter_version": str(adapter.get("adapter_version") or "1.0"),
        "session_id": session_id.strip(),
        "request_id": request_id.strip(),
        "text": text.strip(),
        "project_hint": project_hint,
        "freshness": freshness,
        "declared_capabilities": declared_capabilities,
        "tool_classes": tool_classes,
        "data_class": data_class,
        "requested_action_class": action,
    }


def classify_entry(normalized: dict) -> dict:
    if not isinstance(normalized, dict):
        raise ValueError("normalized_request_required")
    action = str(normalized.get("requested_action_class") or "informational")
    data_class = str(normalized.get("data_class") or "SECRET").upper()
    freshness = str(normalized.get("freshness") or "none").lower()

    high_impact = action in _HIGH_IMPACT or data_class == "SECRET"
    if high_impact or action in _DEEP_ACTIONS or freshness == "live":
        profile = "DEEP"
    elif action in _STANDARD_ACTIONS or freshness == "current":
        profile = "STANDARD"
    else:
        profile = "FAST"

    requires_online = profile != "FAST"
    safe_degraded = not high_impact and action not in _DEEP_ACTIONS and data_class != "SECRET"
    reason = action
    if data_class == "SECRET":
        reason = "secret_or_unknown_data_class"

    return {
        "profile": profile,
        "high_impact": high_impact,
        "requires_online_brain": requires_online,
        "safe_degraded_allowed": safe_degraded,
        "reason": reason,
    }


def scope_allows(adapter: dict, required_scope: str) -> bool:
    if not isinstance(adapter, dict) or not isinstance(required_scope, str) or not required_scope:
        return False
    scopes = adapter.get("scopes", [])
    return isinstance(scopes, list) and required_scope in scopes
