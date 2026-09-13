import json
import time
from dataclasses import dataclass
from urllib.error import URLError
from urllib.request import Request, urlopen


class ComfyUIError(RuntimeError):
    pass


class DependencyMissing(ComfyUIError):
    pass


@dataclass(frozen=True)
class RenderArtifact:
    filename: str
    subfolder: str = ""
    type: str = "output"


def _enum_options(node_info):
    out = {}
    required = node_info.get("input", {}).get("required", {}) if isinstance(node_info, dict) else {}
    if not isinstance(required, dict):
        return out
    for key, spec in required.items():
        if isinstance(spec, list) and spec and isinstance(spec[0], list):
            values = [item for item in spec[0] if isinstance(item, str)]
            if values:
                out[str(key)] = values[:50]
    return out


class ComfyUIAdapter:
    def __init__(self, base_url="http://127.0.0.1:8188", timeout=10, max_polls=120, poll_seconds=1):
        if base_url != "http://127.0.0.1:8188":
            raise ValueError("ComfyUI endpoint must be local")
        self.base_url = base_url
        self.timeout = timeout
        self.max_polls = max_polls
        self.poll_seconds = poll_seconds

    def _json(self, path, method="GET", body=None):
        data = None if body is None else json.dumps(body).encode()
        req = Request(
            self.base_url + path,
            data=data,
            method=method,
            headers={"Content-Type": "application/json"},
        )
        try:
            with urlopen(req, timeout=self.timeout) as response:
                return json.loads(response.read().decode())
        except (URLError, OSError, ValueError) as exc:
            raise ComfyUIError(str(exc)) from exc

    def preflight(self):
        stats = self._json("/system_stats")
        objects = self._json("/object_info")
        required = [
            "CheckpointLoaderSimple",
            "CLIPTextEncode",
            "EmptyLatentImage",
            "KSampler",
            "VAEDecode",
            "SaveImage",
            "LoadImage",
        ]
        missing = [name for name in required if name not in objects]
        refs = sorted(name for name in objects if "ipadapter" in name.lower())
        if not refs:
            missing.append("IPAdapter reference-conditioning nodes")

        checkpoints = _enum_options(objects.get("CheckpointLoaderSimple", {})).get("ckpt_name", [])
        if "CheckpointLoaderSimple" in objects and not checkpoints:
            missing.append("SD checkpoint")

        if missing:
            raise DependencyMissing(", ".join(missing))

        return {
            "stats": stats,
            "reference_nodes": refs,
            "checkpoints": checkpoints[:20],
            "reference_options": {
                name: _enum_options(objects.get(name, {}))
                for name in refs[:20]
                if _enum_options(objects.get(name, {}))
            },
        }

    def submit(self, workflow):
        out = self._json("/prompt", "POST", {"prompt": workflow})
        prompt_id = out.get("prompt_id")
        if not prompt_id:
            raise ComfyUIError("ComfyUI did not return prompt_id")
        return prompt_id

    def wait(self, prompt_id):
        for _ in range(self.max_polls):
            history = self._json("/history/" + prompt_id)
            record = history.get(prompt_id)
            if record:
                status = record.get("status", {})
                if status.get("status_str") == "error":
                    raise ComfyUIError(str(status))
                for node in record.get("outputs", {}).values():
                    images = node.get("images", [])
                    if images:
                        image = images[0]
                        return RenderArtifact(
                            image["filename"],
                            image.get("subfolder", ""),
                            image.get("type", "output"),
                        )
            time.sleep(self.poll_seconds)
        raise ComfyUIError("ComfyUI render timed out")
