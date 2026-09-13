from money_ecosystem.worker import runtime


def test_reference_probe_is_local_only():
    assert runtime._COMFYUI_BASE == "http://127.0.0.1:8188"


def test_reference_probe_reports_missing_ipadapter(monkeypatch):
    monkeypatch.setattr(runtime, "_fetch_json", lambda url, timeout=1.5: {"CheckpointLoaderSimple": {}})
    result = runtime._probe_comfyui_reference()
    assert result["available"] is False
    assert "IPAdapter" in result["missing"]
