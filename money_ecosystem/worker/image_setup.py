from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import urllib.request
from typing import Iterable


IPADAPTER_REPO_URL = "https://github.com/cubiq/ComfyUI_IPAdapter_plus.git"
IPADAPTER_REPO_COMMIT = "a0f451a5113cf9becb0847b92884cb10cbdec0ef"
MIN_FREE_BYTES = 9 * 1024**3
MAX_DISCOVERY_ENTRIES = 25000

_FILES = (
    {
        "name": "v1-5-pruned-emaonly.safetensors",
        "relative_path": "models/checkpoints/v1-5-pruned-emaonly.safetensors",
        "url": "https://huggingface.co/stable-diffusion-v1-5/stable-diffusion-v1-5/resolve/main/v1-5-pruned-emaonly.safetensors?download=true",
        "sha256": "6ce0161689b3853acaa03779ec93eafe75a02f4ced659bee03f50797806fa2fa",
    },
    {
        "name": "ip-adapter-plus_sd15.safetensors",
        "relative_path": "models/ipadapter/ip-adapter-plus_sd15.safetensors",
        "url": "https://huggingface.co/h94/IP-Adapter/resolve/main/models/ip-adapter-plus_sd15.safetensors?download=true",
        "sha256": "a1c250be40455cc61a43da1201ec3f1edaea71214865fb47f57927e06cbe4996",
    },
    {
        "name": "CLIP-ViT-H-14-laion2B-s32B-b79K.safetensors",
        "relative_path": "models/clip_vision/CLIP-ViT-H-14-laion2B-s32B-b79K.safetensors",
        "url": "https://huggingface.co/h94/IP-Adapter/resolve/main/models/image_encoder/model.safetensors?download=true",
        "sha256": "6ca9667da1ca9e0b0f75e46bb030f7e011f44f86cbfb8d5a36590fcd7507b030",
    },
)


class ImageSetupError(RuntimeError):
    pass


def _is_comfyui_root(root: Path) -> bool:
    return (root / "models").is_dir() and (root / "custom_nodes").is_dir()


def _is_comfyui_data_root(root: Path) -> bool:
    return root.is_dir() and (root / "models").is_dir()


def _default_candidates() -> list[Path]:
    home = Path.home()
    out = [
        home / "Documents" / "ComfyUI",
        home / "ComfyUI",
        Path("C:/ComfyUI"),
        Path("C:/AI/ComfyUI"),
    ]
    for env_name in ("APPDATA", "LOCALAPPDATA"):
        value = os.environ.get(env_name)
        if value:
            base = Path(value)
            out.extend(
                [
                    base / "ComfyUI",
                    base / "Programs" / "ComfyUI",
                    base / "comfyui-electron" / "ComfyUI",
                    base / "ComfyUI" / "app" / "ComfyUI",
                    base / "ComfyUI" / "resources" / "ComfyUI",
                ]
            )
    seen: set[str] = set()
    unique: list[Path] = []
    for candidate in out:
        key = str(candidate).lower()
        if key not in seen:
            seen.add(key)
            unique.append(candidate)
    return unique


def _desktop_config_candidates() -> list[Path]:
    out: list[Path] = []
    appdata = os.environ.get("APPDATA")
    if appdata:
        base = Path(appdata)
        for app_name in ("ComfyUI", "Comfy Desktop", "comfyui-desktop-2"):
            out.extend(
                [
                    base / app_name / "config.json",
                    base / app_name / "extra_models_config.yaml",
                    base / app_name / "extra_model_paths.yaml",
                ]
            )
    return out


def _normalize_config_path(value: str) -> Path:
    expanded = os.path.expandvars(value.strip().strip('"\''))
    return Path(expanded).expanduser()


def _paths_from_json_config(path: Path) -> list[Path]:
    try:
        data = json.loads(path.read_text(encoding="utf-8-sig"))
    except (OSError, ValueError):
        return []
    found: list[Path] = []

    def walk(value):
        if isinstance(value, dict):
            for key, child in value.items():
                if key in {"basePath", "base_path", "installPath"} and isinstance(child, str) and child.strip():
                    found.append(_normalize_config_path(child))
                walk(child)
        elif isinstance(value, list):
            for child in value:
                walk(child)

    walk(data)
    return found


def _paths_from_yaml_config(path: Path) -> list[Path]:
    try:
        text = path.read_text(encoding="utf-8-sig")
    except OSError:
        return []
    found: list[Path] = []
    for match in re.finditer(r"(?mi)^\s*base_path\s*:\s*(.+?)\s*$", text):
        raw = match.group(1).split("#", 1)[0].strip()
        if raw:
            found.append(_normalize_config_path(raw))
    return found


def find_comfyui_root_from_desktop_config(config_files: Iterable[Path] | None = None) -> Path | None:
    files = list(config_files) if config_files is not None else _desktop_config_candidates()
    for config_file in files:
        path = Path(config_file)
        if not path.is_file():
            continue
        candidates = _paths_from_json_config(path) if path.suffix.lower() == ".json" else _paths_from_yaml_config(path)
        for candidate in candidates:
            try:
                root = candidate.resolve()
            except OSError:
                continue
            if _is_comfyui_data_root(root):
                return root
    return None


def _default_search_roots() -> list[Path]:
    roots = [Path.home() / "Documents", Path("C:/AI")]
    for env_name in ("APPDATA", "LOCALAPPDATA", "PROGRAMDATA"):
        value = os.environ.get(env_name)
        if value:
            roots.append(Path(value))
    seen: set[str] = set()
    unique: list[Path] = []
    for root in roots:
        key = str(root).lower()
        if key not in seen:
            seen.add(key)
            unique.append(root)
    return unique


def find_comfyui_root(candidates: Iterable[Path] | None = None) -> Path | None:
    for candidate in list(candidates) if candidates is not None else _default_candidates():
        root = Path(candidate).expanduser().resolve()
        if _is_comfyui_root(root):
            return root
    return None


def discover_comfyui_root(
    search_roots: Iterable[Path] | None = None,
    *,
    max_depth: int = 6,
    max_entries: int = MAX_DISCOVERY_ENTRIES,
) -> Path | None:
    roots = list(search_roots) if search_roots is not None else _default_search_roots()
    skipped_names = {
        ".git",
        "node_modules",
        "cache",
        "code cache",
        "gpucache",
        "temp",
        "tmp",
        "$recycle.bin",
    }
    examined = 0
    for search_root in roots:
        base = Path(search_root).expanduser()
        if not base.is_dir():
            continue
        try:
            base_resolved = base.resolve()
        except OSError:
            continue
        for current, dirs, _files in os.walk(base_resolved, topdown=True, followlinks=False):
            current_path = Path(current)
            try:
                relative = current_path.relative_to(base_resolved)
                depth = len(relative.parts)
            except ValueError:
                dirs[:] = []
                continue
            if depth > max_depth:
                dirs[:] = []
                continue
            dirs[:] = [name for name in dirs if name.lower() not in skipped_names]
            examined += 1
            if examined > max_entries:
                return None
            try:
                if _is_comfyui_root(current_path):
                    return current_path.resolve()
            except OSError:
                continue
    return None


def build_bootstrap_plan(comfyui_root: Path) -> dict:
    root = Path(comfyui_root).resolve()
    return {
        "comfyui_root": str(root),
        "zero_paid_services": True,
        "cloud_fallback": False,
        "node_repo": {
            "url": IPADAPTER_REPO_URL,
            "commit": IPADAPTER_REPO_COMMIT,
            "relative_path": "custom_nodes/ComfyUI_IPAdapter_plus",
        },
        "files": [dict(item) for item in _FILES],
    }


def _sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(8 * 1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def _download_verified(url: str, target: Path, expected_sha256: str) -> str:
    target.parent.mkdir(parents=True, exist_ok=True)
    if target.exists() and _sha256(target) == expected_sha256:
        return "present"

    part = target.with_name(target.name + ".part")
    if part.exists():
        part.unlink()
    request = urllib.request.Request(url, headers={"User-Agent": "CuriousBeyondWorker/1.0"})
    try:
        with urllib.request.urlopen(request, timeout=60) as response, part.open("wb") as out:
            shutil.copyfileobj(response, out, length=8 * 1024 * 1024)
    except Exception as exc:
        if part.exists():
            part.unlink()
        raise ImageSetupError(f"download failed for {target.name}: {exc}") from exc

    actual = _sha256(part)
    if actual != expected_sha256:
        part.unlink(missing_ok=True)
        raise ImageSetupError(f"SHA256 mismatch for {target.name}: expected {expected_sha256}, got {actual}")
    part.replace(target)
    return "downloaded"


def _run_git(args: list[str], cwd: Path | None = None) -> None:
    result = subprocess.run(
        ["git", *args],
        cwd=str(cwd) if cwd else None,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        check=False,
    )
    if result.returncode != 0:
        raise ImageSetupError(f"git {' '.join(args)} failed: {result.stdout.strip()}")


def _ensure_ipadapter_node(root: Path) -> str:
    custom_nodes = root / "custom_nodes"
    custom_nodes.mkdir(parents=True, exist_ok=True)
    node_dir = custom_nodes / "ComfyUI_IPAdapter_plus"
    if node_dir.exists() and not (node_dir / ".git").is_dir():
        raise ImageSetupError("ComfyUI_IPAdapter_plus exists but is not a git checkout; refusing to overwrite")
    if not node_dir.exists():
        _run_git(["clone", "--no-tags", IPADAPTER_REPO_URL, str(node_dir)])
        action = "cloned"
    else:
        action = "present"
    _run_git(["fetch", "--depth", "1", "origin", IPADAPTER_REPO_COMMIT], cwd=node_dir)
    _run_git(["checkout", "--detach", IPADAPTER_REPO_COMMIT], cwd=node_dir)
    return action


def bootstrap_reference_stack() -> dict:
    root = find_comfyui_root_from_desktop_config() or find_comfyui_root() or discover_comfyui_root()
    if root is None:
        searched = [str(path) for path in _default_search_roots()]
        configs = [str(path) for path in _desktop_config_candidates()]
        raise ImageSetupError(
            "ComfyUI data root not found after Desktop config lookup and bounded discovery; config candidates: "
            + ", ".join(configs)
            + "; searched roots: "
            + ", ".join(searched)
        )
    usage = shutil.disk_usage(root)
    if usage.free < MIN_FREE_BYTES:
        raise ImageSetupError(f"insufficient free disk space for reference stack: need at least {MIN_FREE_BYTES} bytes")

    plan = build_bootstrap_plan(root)
    node_action = _ensure_ipadapter_node(root)
    file_actions: dict[str, str] = {}
    for item in plan["files"]:
        target = root / item["relative_path"]
        file_actions[item["name"]] = _download_verified(item["url"], target, item["sha256"])

    return {
        "status": "INSTALLED",
        "comfyui_root": str(root),
        "zero_paid_services": True,
        "cloud_fallback": False,
        "node_action": node_action,
        "files": file_actions,
        "restart_required": True,
        "note": "Restart ComfyUI so custom nodes and model indexes are reloaded.",
    }
