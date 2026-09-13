from __future__ import annotations

import importlib.util
from pathlib import Path
import shutil
import sys
import urllib.error
import urllib.request
from typing import Any

from .allowlist import validate_job_request


def _probe_comfyui() -> dict[str, Any]:
    url = "http://127.0.0.1:8188/system_stats"
    try:
        with urllib.request.urlopen(url, timeout=1.5) as response:
            return {"available": response.status == 200, "endpoint": url}
    except (urllib.error.URLError, TimeoutError, OSError):
        return {"available": False, "endpoint": url}


def _probe_capabilities(targets: list[str]) -> dict[str, Any]:
    capabilities: dict[str, Any] = {}
    for target in targets:
        if target == "python":
            capabilities[target] = {
                "available": True,
                "version": sys.version.split()[0],
            }
        elif target == "ffmpeg":
            capabilities[target] = {
                "available": shutil.which("ffmpeg") is not None,
            }
        elif target == "whisper":
            capabilities[target] = {
                "available": importlib.util.find_spec("whisper") is not None,
            }
        elif target == "kokoro":
            capabilities[target] = {
                "available": importlib.util.find_spec("kokoro") is not None,
            }
        elif target == "comfyui":
            capabilities[target] = _probe_comfyui()
        else:
            capabilities[target] = {
                "available": False,
                "reason": "unsupported probe target",
            }
    return capabilities


def execute_job(job: dict[str, Any], workspace_root: Path | str) -> dict[str, Any]:
    job = validate_job_request(job)
    job_type = job["job_type"]

    if job_type == "MEDIA_PROBE":
        targets = job["args"].get("targets") or [
            "python",
            "ffmpeg",
            "whisper",
            "kokoro",
            "comfyui",
        ]
        if not isinstance(targets, list) or not all(
            isinstance(item, str) for item in targets
        ):
            return {
                "status": "BLOCKED",
                "message": "Probe targets must be a list of strings",
                "artifact_manifest": {},
            }
        capabilities = _probe_capabilities(targets)
        all_available = (
            all(item.get("available") is True for item in capabilities.values())
            if capabilities
            else True
        )
        return {
            "status": "SUCCESS" if all_available else "DEGRADED",
            "message": "Media capability probe completed",
            "artifact_manifest": {"capabilities": capabilities},
        }

    return {
        "status": "BLOCKED",
        "message": (
            f"{job_type} is not enabled until its dedicated renderer adapter "
            "passes verification"
        ),
        "artifact_manifest": {},
    }
