from __future__ import annotations

from pathlib import Path
from typing import Any

_ALLOWED_JOB_TYPES = {
    "IMAGE_RENDER",
    "VIDEO_RENDER",
    "VOICE_RENDER",
    "FINAL_RENDER",
    "MEDIA_PROBE",
}
_FORBIDDEN_KEYS = {
    "command",
    "cmd",
    "shell",
    "powershell",
    "script",
    "argv",
    "executable",
}


def ensure_safe_path(root: Path, candidate: Path | str) -> Path:
    root_resolved = Path(root).resolve()
    candidate_resolved = Path(candidate).resolve()
    try:
        candidate_resolved.relative_to(root_resolved)
    except ValueError as exc:
        raise ValueError("Path is outside worker root") from exc
    return candidate_resolved


def _reject_shell_fields(value: Any) -> None:
    if isinstance(value, dict):
        for key, child in value.items():
            if str(key).lower() in _FORBIDDEN_KEYS:
                raise ValueError("Arbitrary shell execution is forbidden")
            _reject_shell_fields(child)
    elif isinstance(value, list):
        for child in value:
            _reject_shell_fields(child)


def validate_job_request(payload: dict[str, Any]) -> dict[str, Any]:
    job_id = payload.get("job_id")
    job_type = payload.get("job_type")
    created_at = payload.get("created_at")
    args = payload.get("args", {})

    if not isinstance(job_id, str) or not job_id.strip():
        raise ValueError("job_id is required")
    if job_type not in _ALLOWED_JOB_TYPES:
        raise ValueError(f"Unsupported job type: {job_type}")
    if not isinstance(created_at, str) or not created_at.strip():
        raise ValueError("created_at is required")
    if not isinstance(args, dict):
        raise ValueError("args must be an object")
    _reject_shell_fields(args)

    return {
        "job_id": job_id,
        "job_type": job_type,
        "created_at": created_at,
        "args": args,
    }
