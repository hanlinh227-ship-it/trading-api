from __future__ import annotations

import argparse
import json
from pathlib import Path
import shutil
import urllib.request

from . import image_setup

COMFYUI_STATS = "http://127.0.0.1:8188/system_stats"


class ManualSetupError(RuntimeError):
    pass


def _fetch_system_stats(timeout: float = 3.0) -> dict:
    try:
        with urllib.request.urlopen(COMFYUI_STATS, timeout=timeout) as response:
            return json.loads(response.read().decode("utf-8"))
    except Exception as exc:
        raise ManualSetupError(f"cannot read active ComfyUI system_stats: {exc}") from exc


def _flag_value(argv: list[str], flag: str) -> str | None:
    for i, raw in enumerate(argv):
        value = str(raw)
        if value == flag and i + 1 < len(argv):
            return str(argv[i + 1])
        prefix = flag + "="
        if value.startswith(prefix):
            return value[len(prefix):]
    return None


def root_from_system_stats(stats: dict) -> Path | None:
    argv = stats.get("system", {}).get("argv", [])
    if not isinstance(argv, list):
        return None
    argv = [str(x) for x in argv]

    base = _flag_value(argv, "--base-directory")
    if base:
        root = image_setup._nearest_data_root(Path(base))
        if root is not None:
            return root

    extra = _flag_value(argv, "--extra-model-paths-config")
    if extra:
        cfg = Path(extra).expanduser()
        if cfg.is_file():
            candidates = image_setup._paths_from_yaml_config(cfg)
            for candidate in candidates:
                root = image_setup._nearest_data_root(candidate)
                if root is not None:
                    return root

    user_dir = _flag_value(argv, "--user-directory")
    if user_dir:
        root = image_setup._nearest_data_root(Path(user_dir))
        if root is not None:
            return root

    for raw in argv:
        if raw.lower().endswith("main.py"):
            root = image_setup._nearest_data_root(Path(raw).parent)
            if root is not None:
                return root
    return None


def discover_active_root() -> Path:
    stats = _fetch_system_stats()
    root = root_from_system_stats(stats)
    if root is not None:
        return root
    root = (
        image_setup.find_comfyui_root_from_running_process()
        or image_setup.find_comfyui_root_from_desktop_config()
        or image_setup.find_comfyui_root()
        or image_setup.discover_comfyui_root()
    )
    if root is None:
        argv = stats.get("system", {}).get("argv", [])
        raise ManualSetupError(
            "active ComfyUI is reachable but its data root could not be resolved; argv="
            + json.dumps(argv, ensure_ascii=False)
        )
    return root


def install_to_root(root: Path) -> dict:
    root = Path(root).expanduser().resolve()
    if not (root / "models").is_dir():
        raise ManualSetupError(f"ComfyUI root must contain models/: {root}")
    usage = shutil.disk_usage(root)
    if usage.free < image_setup.MIN_FREE_BYTES:
        raise ManualSetupError(
            f"insufficient free disk space: need at least {image_setup.MIN_FREE_BYTES} bytes"
        )

    node_action = image_setup._ensure_ipadapter_node(root)
    file_actions: dict[str, str] = {}
    for item in image_setup._FILES:
        target = root / item["relative_path"]
        file_actions[item["name"]] = image_setup._download_verified(
            item["url"], target, item["sha256"]
        )

    return {
        "status": "INSTALLED",
        "comfyui_root": str(root),
        "node_action": node_action,
        "files": file_actions,
        "restart_required": True,
        "zero_paid_services": True,
        "cloud_fallback": False,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Direct local ComfyUI reference-stack installer")
    parser.add_argument("--root", help="Explicit ComfyUI data root containing models/")
    args = parser.parse_args(argv)
    try:
        root = Path(args.root) if args.root else discover_active_root()
        print(f"ComfyUI root: {root}", flush=True)
        result = install_to_root(root)
        print(json.dumps(result, indent=2, ensure_ascii=False), flush=True)
        print("INSTALL COMPLETE. Restart ComfyUI before reference preflight.", flush=True)
        return 0
    except Exception as exc:
        print(f"INSTALL BLOCKED: {type(exc).__name__}: {exc}", flush=True)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
