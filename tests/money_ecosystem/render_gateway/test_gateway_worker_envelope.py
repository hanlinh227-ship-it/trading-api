import pytest

from money_ecosystem.worker.protocol import sign_payload, verify_envelope


def _envelope_payload():
    return {
        "job_id": "gateway-job-1",
        "job_type": "RENDER_GATEWAY",
        "created_at": "2026-09-14T20:00:00+07:00",
        "args": {
            "render_job": {
                "job_id": "job-1",
                "attempt_id": "a1",
                "project_id": "max-bus",
                "job_type": "IMAGE_RENDER",
                "quality_tier": "FLOW_GRADE",
            }
        },
    }


def test_gateway_job_can_be_signed_and_verified():
    secret = b"secret"
    envelope = sign_payload(_envelope_payload(), secret)
    verified = verify_envelope(envelope, secret)
    assert verified["job_type"] == "RENDER_GATEWAY"
    assert verified["args"]["render_job"]["attempt_id"] == "a1"


def test_gateway_job_still_rejects_nested_shell_fields():
    payload = _envelope_payload()
    payload["args"]["render_job"]["metadata"] = {"powershell": "whoami"}
    with pytest.raises(ValueError, match="Arbitrary shell"):
        sign_payload(payload, b"secret")
