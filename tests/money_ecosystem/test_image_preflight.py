from money_ecosystem.worker import image_preflight

def test_preflight_endpoint_is_local_only():
    assert image_preflight.COMFY_URL == "http://127.0.0.1:8188"

def test_preflight_never_enables_paid_services():
    # Source-level invariant: preflight result defaults to zero-paid mode and has no cloud endpoint.
    import inspect
    source=inspect.getsource(image_preflight.run_preflight)
    assert '"zero_paid_services":True' in source
    assert "https://" not in source
