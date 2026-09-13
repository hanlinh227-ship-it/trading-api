from __future__ import annotations

import importlib.util
import json
from pathlib import Path
import shutil
import sys
import urllib.error
import urllib.request
from typing import Any

from .allowlist import validate_job_request

_COMFYUI_BASE = "http://127.0.0.1:8188"


def _fetch_json(url: str, timeout: float = 1.5) -> dict[str, Any]:
    with urllib.request.urlopen(url, timeout=timeout) as response:
        return json.loads(response.read().decode("utf-8"))


def _probe_comfyui() -> dict[str, Any]:
    url = _COMFYUI_BASE + "/system_stats"
    try:
        with urllib.request.urlopen(url, timeout=1.5) as response:
            return {"available": response.status == 200, "endpoint": url}
    except (urllib.error.URLError, TimeoutError, OSError):
        return {"available": False, "endpoint": url}


def _probe_comfyui_reference() -> dict[str, Any]:
    url = _COMFYUI_BASE + "/object_info"
    try:
        objects = _fetch_json(url)
    except (urllib.error.URLError, TimeoutError, OSError, ValueError) as exc:
        return {
            "available": False,
            "endpoint": url,
            "missing": ["ComfyUI object_info"],
            "reason": str(exc),
        }

    required_base = {
        "CheckpointLoaderSimple",
        "CLIPTextEncode",
        "EmptyLatentImage",
        "KSampler",
        "VAEDecode",
        "SaveImage",
    }
    missing = sorted(name for name in required_base if name not in objects)
    reference_nodes = sorted(
        name for name in objects if "ipadapter" in name.lower()
    )
    if not reference_nodes:
        missing.append("IPAdapter")

    return {
        "available": not missing,
        "endpoint": url,
        "missing": missing,
        "reference_nodes": reference_nodes[:20],
    }


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
        elif target == "comfyui_reference":
            capabilities[target] = _probe_comfyui_reference()
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
