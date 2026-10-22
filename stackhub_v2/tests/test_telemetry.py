from stackhub.telemetry import redact


def test_redact_masks_taskbounty_api_keys_recursively():
    value = {"Authorization": "Bearer tb_live_ABCDEFGHIJKLMNOPQRSTUVWXYZ123456", "nested": ["x", "tb_live_SECRETSECRETSECRET"]}
    text = str(redact(value))
    assert "tb_live_ABCDEFGHIJKLMNOPQRSTUVWXYZ123456" not in text
    assert "tb_live_SECRETSECRETSECRET" not in text
    assert "[REDACTED]" in text


def test_redact_masks_common_secret_fields():
    out = redact({"api_key": "secret", "private_key": "never", "safe": "ok"})
    assert out["api_key"] == "[REDACTED]"
    assert out["private_key"] == "[REDACTED]"
    assert out["safe"] == "ok"
