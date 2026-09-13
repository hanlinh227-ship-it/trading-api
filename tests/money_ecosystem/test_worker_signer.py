import json

from money_ecosystem.worker.protocol import verify_envelope
from money_ecosystem.worker.signer import sign_request_file


SECRET = b"test-secret-32-bytes-minimum-value!!"


def test_sign_request_file_produces_worker_compatible_envelope(tmp_path):
    request_path = tmp_path / "request.json"
    output_path = tmp_path / "signed" / "current.json"
    payload = {
        "job_id": "probe-e2e-001",
        "job_type": "MEDIA_PROBE",
        "created_at": "2026-09-14T02:40:00+07:00",
        "args": {"targets": ["python", "ffmpeg", "whisper", "kokoro", "comfyui"]},
    }
    request_path.write_text(json.dumps(payload), encoding="utf-8")

    sign_request_file(request_path, output_path, SECRET)

    envelope = json.loads(output_path.read_text(encoding="utf-8"))
    assert verify_envelope(envelope, SECRET) == payload
    assert envelope["algorithm"] == "HMAC-SHA256"
    assert envelope["signature"]


def test_sign_request_file_rejects_short_secret(tmp_path):
    request_path = tmp_path / "request.json"
    request_path.write_text(
        json.dumps({
            "job_id": "probe-e2e-002",
            "job_type": "MEDIA_PROBE",
            "created_at": "2026-09-14T02:40:00+07:00",
            "args": {},
        }),
        encoding="utf-8",
    )

    try:
        sign_request_file(request_path, tmp_path / "out.json", b"short")
    except ValueError as exc:
        assert "at least 32" in str(exc)
    else:
        raise AssertionError("short secret must be rejected")
