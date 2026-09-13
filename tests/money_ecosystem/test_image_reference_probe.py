from money_ecosystem.worker import runtime


def test_reference_probe_is_local_only():
    assert runtime._COMFYUI_BASE == "http://127.0.0.1:8188"


def test_reference_probe_reports_missing_ipadapter(monkeypatch):
    monkeypatch.setattr(runtime, "_fetch_json", lambda url, timeout=1.5: {"CheckpointLoaderSimple": {}})
    result = runtime._probe_comfyui_reference()
    assert result["available"] is False
    assert "IPAdapter" in result["missing"]


def test_reference_probe_reports_checkpoint_and_reference_nodes(monkeypatch):
    objects = {
        "CheckpointLoaderSimple": {
            "input": {"required": {"ckpt_name": [["model.safetensors"]]}}
        },
        "CLIPTextEncode": {},
        "EmptyLatentImage": {},
        "KSampler": {},
        "VAEDecode": {},
        "SaveImage": {},
        "LoadImage": {},
        "IPAdapterUnifiedLoader": {
            "input": {"required": {"preset": [["STANDARD (medium strength)"]]}}
        },
        "IPAdapterAdvanced": {},
    }
    monkeypatch.setattr(runtime, "_fetch_json", lambda url, timeout=1.5: objects)
    result = runtime._probe_comfyui_reference()
    assert result["available"] is True
    assert result["checkpoints"] == ["model.safetensors"]
    assert "IPAdapterUnifiedLoader" in result["reference_nodes"]
    assert "STANDARD (medium strength)" in result["reference_options"]["IPAdapterUnifiedLoader"]["preset"]
