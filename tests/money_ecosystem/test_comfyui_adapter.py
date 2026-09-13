import pytest
from money_ecosystem.worker.comfyui_adapter import ComfyUIAdapter

def test_adapter_rejects_nonlocal_endpoint():
    with pytest.raises(ValueError): ComfyUIAdapter("https://example.com")

def test_adapter_uses_bounded_polling():
    a=ComfyUIAdapter(max_polls=3,poll_seconds=0)
    assert a.max_polls==3 and a.base_url=="http://127.0.0.1:8188"
