from __future__ import annotations

import json
import re
from typing import Any, Mapping


class ControlPlaneError(ValueError):
    pass


_SAFE = re.compile(r"[^A-Za-z0-9._-]+")


def _component(value: str) -> str:
    cleaned = _SAFE.sub("_", str(value).strip()).strip("._")
    if not cleaned:
        raise ControlPlaneError("empty control-plane path component")
    return cleaned


def attempt_root(project_id: str, job_id: str, attempt_id: str) -> str:
    return (
        "render_gateway/jobs/"
        f"{_component(project_id)}/{_component(job_id)}/{_component(attempt_id)}"
    )


def attempt_path(project_id: str, job_id: str, attempt_id: str) -> str:
    return attempt_root(project_id, job_id, attempt_id) + "/request.json"


def signed_path(project_id: str, job_id: str, attempt_id: str) -> str:
    return attempt_root(project_id, job_id, attempt_id) + "/signed.json"


def result_path(project_id: str, job_id: str, attempt_id: str) -> str:
    return attempt_root(project_id, job_id, attempt_id) + "/result.json"


def _canonical(value: Mapping[str, Any]) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def assert_same_attempt(original: Mapping[str, Any], revised: Mapping[str, Any]) -> None:
    original_attempt = str(original.get("attempt_id", "")).strip()
    revised_attempt = str(revised.get("attempt_id", "")).strip()
    if not original_attempt or not revised_attempt:
        raise ControlPlaneError("attempt_id is required")
    if original_attempt != revised_attempt:
        return
    if _canonical(original) != _canonical(revised):
        raise ControlPlaneError(
            "signed attempt payload is immutable; create a new attempt_id for revisions"
        )


def reject_binary_fields(value: Any) -> None:
    if isinstance(value, (bytes, bytearray, memoryview)):
        raise ControlPlaneError("binary payloads are forbidden in GitHub control manifests")
    if isinstance(value, Mapping):
        for key, child in value.items():
            key_text = str(key).lower()
            if key_text in {"base64", "binary", "blob", "file_bytes", "raw_bytes"}:
                raise ControlPlaneError("binary payload fields are forbidden in control manifests")
            reject_binary_fields(child)
    elif isinstance(value, (list, tuple)):
        for child in value:
            reject_binary_fields(child)
