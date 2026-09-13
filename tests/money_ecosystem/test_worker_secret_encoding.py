from money_ecosystem.worker.runner import _load_secret


def test_load_secret_accepts_powershell_utf8_bom(tmp_path):
    secret_text = "test-secret-32-bytes-minimum-value!!"
    secret_file = tmp_path / "worker_secret.txt"
    secret_file.write_bytes(b"\xef\xbb\xbf" + secret_text.encode("utf-8"))

    assert _load_secret(secret_file) == secret_text.encode("utf-8")
