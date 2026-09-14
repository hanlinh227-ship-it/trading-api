from pathlib import Path

import pytest
from money_ecosystem.worker.comfyui_adapter import ComfyUIAdapter, DependencyMissing, RenderArtifact


def test_adapter_rejects_nonlocal_endpoint():
    with pytest.raises(ValueError):
        ComfyUIAdapter("https://example.com")


def test_adapter_uses_bounded_polling():
    a = ComfyUIAdapter(max_polls=3, poll_seconds=0)
    assert a.max_polls == 3 and a.base_url == "http://127.0.0.1:8188"


def test_preflight_requires_load_image_and_checkpoint_options(monkeypatch):
    a = ComfyUIAdapter()
    objects = {
        "CheckpointLoaderSimple": {"input": {"required": {"ckpt_name": [["model.safetensors"]]}}},
        "CLIPTextEncode": {},
        "EmptyLatentImage": {},
        "KSampler": {},
        "VAEDecode": {},
        "SaveImage": {},
        "IPAdapterUnifiedLoader": {},
    }

    def fake_json(path, method="GET", body=None):
        if path == "/system_stats":
            return {"system": {}}
        if path == "/object_info":
            return objects
        raise AssertionError(path)

    monkeypatch.setattr(a, "_json", fake_json)
    with pytest.raises(DependencyMissing) as exc:
        a.preflight()
    assert "LoadImage" in str(exc.value)


def test_preflight_returns_checkpoint_and_reference_nodes(monkeypatch):
    a = ComfyUIAdapter()
    objects = {
        "CheckpointLoaderSimple": {"input": {"required": {"ckpt_name": [["model.safetensors"]]}}},
        "CLIPTextEncode": {},
        "EmptyLatentImage": {},
        "KSampler": {},
        "VAEDecode": {},
        "SaveImage": {},
        "LoadImage": {},
        "IPAdapterUnifiedLoader": {},
    }
    monkeypatch.setattr(a, "_json", lambda path, method="GET", body=None: {"ok": True} if path == "/system_stats" else objects)
    result = a.preflight()
    assert result["checkpoints"] == ["model.safetensors"]
    assert "IPAdapterUnifiedLoader" in result["reference_nodes"]


def test_discovers_active_input_directory_from_system_stats(monkeypatch):
    a = ComfyUIAdapter()
    stats = {
        "system": {
            "argv": [
                "main.py",
                "--input-directory",
                r"D:\\Comfy-Desktop\\ComfyUI-Shared\\input",
                "--output-directory",
                r"D:\\Comfy-Desktop\\ComfyUI-Shared\\output",
            ]
        }
    }
    monkeypatch.setattr(a, "_json", lambda path, method="GET", body=None: stats)
    assert str(a.input_directory()).replace("\\", "/").endswith("ComfyUI-Shared/input")


def test_fetch_artifact_writes_exact_bytes(monkeypatch, tmp_path):
    a = ComfyUIAdapter()
    seen = {}

    def fake_bytes(path):
        seen["path"] = path
        return b"png-data"

    monkeypatch.setattr(a, "_bytes", fake_bytes)
    target = tmp_path / "scene_01.png"
    result = a.fetch_artifact(RenderArtifact("image 01.png", "batch/a", "output"), target)
    assert result == target
    assert target.read_bytes() == b"png-data"
    assert seen["path"].startswith("/view?")
    assert "image+01.png" in seen["path"] or "image%2001.png" in seen["path"]
