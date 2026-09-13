from pathlib import Path

import pytest

from money_ecosystem.worker.allowlist import ensure_safe_path, validate_job_request
from money_ecosystem.worker.client import WorkerQueue
from money_ecosystem.worker.protocol import sign_payload, verify_envelope
from money_ecosystem.worker.runner import run_once
from money_ecosystem.worker.runtime import execute_job


def test_sign_and_verify_roundtrip():
    secret = b"a" * 32
    payload = {
        "job_id": "job-001",
        "job_type": "MEDIA_PROBE",
        "created_at": "2026-09-14T00:00:00+07:00",
        "args": {"targets": ["python"]},
    }
    envelope = sign_payload(payload, secret)
    assert verify_envelope(envelope, secret) == payload


def test_tampered_payload_is_rejected():
    secret = b"a" * 32
    envelope = sign_payload(
        {
            "job_id": "job-001",
            "job_type": "MEDIA_PROBE",
            "created_at": "2026-09-14T00:00:00+07:00",
            "args": {},
        },
        secret,
    )
    envelope["payload"]["job_id"] = "tampered"
    with pytest.raises(ValueError):
        verify_envelope(envelope, secret)


def test_shell_fields_are_rejected():
    with pytest.raises(ValueError):
        validate_job_request(
            {
                "job_id": "job-002",
                "job_type": "IMAGE_RENDER",
                "created_at": "2026-09-14T00:00:00+07:00",
                "args": {"command": "whoami"},
            }
        )


def test_unknown_job_type_is_rejected():
    with pytest.raises(ValueError):
        validate_job_request(
            {
                "job_id": "job-003",
                "job_type": "SHELL",
                "created_at": "2026-09-14T00:00:00+07:00",
                "args": {},
            }
        )


def test_safe_path_blocks_escape(tmp_path):
    with pytest.raises(ValueError):
        ensure_safe_path(tmp_path, tmp_path.parent / "escape.txt")


def test_queue_skips_seen_job(tmp_path):
    secret = b"b" * 32
    signed_dir = tmp_path / "worker_jobs" / "signed"
    signed_dir.mkdir(parents=True)
    payload = {
        "job_id": "job-004",
        "job_type": "MEDIA_PROBE",
        "created_at": "2026-09-14T00:00:00+07:00",
        "args": {"targets": ["python"]},
    }
    import json

    (signed_dir / "current.json").write_text(
        json.dumps(sign_payload(payload, secret)), encoding="utf-8"
    )
    queue = WorkerQueue(tmp_path, secret)
    assert queue.next_job()["job_id"] == "job-004"
    queue.mark_seen("job-004")
    assert queue.next_job() is None


def test_media_probe_executes(tmp_path):
    result = execute_job(
        {
            "job_id": "job-300",
            "job_type": "MEDIA_PROBE",
            "created_at": "2026-09-14T02:00:00+07:00",
            "args": {
                "targets": ["python", "ffmpeg", "whisper", "kokoro", "comfyui"]
            },
        },
        tmp_path,
    )
    assert result["status"] in {"SUCCESS", "DEGRADED"}
    assert "python" in result["artifact_manifest"]["capabilities"]


def test_invalid_image_render_contract_fails_closed(tmp_path):
    result = execute_job(
        {
            "job_id": "job-301",
            "job_type": "IMAGE_RENDER",
            "created_at": "2026-09-14T02:00:00+07:00",
            "args": {},
        },
        tmp_path,
    )
    assert result["status"] == "BLOCKED"
    assert "contract rejected" in result["message"].lower()


class _FakeQueue:
    def __init__(self, job):
        self.job = job
        self.results = []
        self.seen = []

    def next_job(self):
        return self.job

    def write_result(self, job_id, status, artifact_manifest, message):
        self.results.append((job_id, status, artifact_manifest, message))
        return Path("result.json")

    def mark_seen(self, job_id):
        self.seen.append(job_id)


def test_run_once_writes_result_and_marks_seen(tmp_path):
    queue = _FakeQueue(
        {
            "job_id": "job-302",
            "job_type": "MEDIA_PROBE",
            "created_at": "2026-09-14T02:00:00+07:00",
            "args": {"targets": ["python"]},
        }
    )
    assert run_once(queue, tmp_path) is True
    assert queue.results[0][0] == "job-302"
    assert queue.seen == ["job-302"]
