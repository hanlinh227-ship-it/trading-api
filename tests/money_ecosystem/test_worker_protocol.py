from pathlib import Path
import json
import tempfile

import pytest

from money_ecosystem.worker.protocol import JobEnvelope, sign_payload, verify_envelope
from money_ecosystem.worker.allowlist import ensure_safe_path, validate_job_request
from money_ecosystem.worker.client import WorkerQueue
from money_ecosystem.worker.runtime import execute_job
from money_ecosystem.worker.runner import run_once

SECRET = b"test-secret-32-bytes-minimum-value!!"


def test_signed_allowed_job_verifies():
    payload = {
        "job_id": "job-001",
        "job_type": "MEDIA_PROBE",
        "created_at": "2026-09-14T02:00:00+07:00",
        "args": {"targets": ["python", "ffmpeg"]},
    }
    envelope = sign_payload(payload, SECRET)
    assert verify_envelope(envelope, SECRET) == payload


def test_unsigned_job_is_rejected():
    envelope = JobEnvelope(
        payload={
            "job_id": "job-002",
            "job_type": "MEDIA_PROBE",
            "created_at": "2026-09-14T02:00:00+07:00",
            "args": {},
        },
        signature="",
    )
    with pytest.raises(ValueError, match="signature"):
        verify_envelope(envelope, SECRET)


def test_unknown_job_type_is_rejected():
    with pytest.raises(ValueError, match="Unsupported job type"):
        validate_job_request(
            {
                "job_id": "job-003",
                "job_type": "SHELL",
                "created_at": "2026-09-14T02:00:00+07:00",
                "args": {},
            }
        )


def test_arbitrary_shell_command_is_rejected():
    with pytest.raises(ValueError, match="shell"):
        validate_job_request(
            {
                "job_id": "job-004",
                "job_type": "MEDIA_PROBE",
                "created_at": "2026-09-14T02:00:00+07:00",
                "args": {"command": "rm -rf /"},
            }
        )


def test_path_traversal_is_rejected():
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        with pytest.raises(ValueError, match="outside worker root"):
            ensure_safe_path(root, root / ".." / "evil.txt")


def test_allowed_path_is_accepted():
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        inside = root / "outputs" / "clip.mp4"
        assert ensure_safe_path(root, inside) == inside.resolve()


def test_queue_reads_verified_current_job_and_deduplicates(tmp_path):
    queue = WorkerQueue(tmp_path, SECRET)
    payload = {
        "job_id": "job-100",
        "job_type": "MEDIA_PROBE",
        "created_at": "2026-09-14T02:00:00+07:00",
        "args": {"targets": ["python"]},
    }
    signed_path = tmp_path / "worker_jobs" / "signed" / "current.json"
    signed_path.parent.mkdir(parents=True)
    signed_path.write_text(
        json.dumps(sign_payload(payload, SECRET).to_dict()),
        encoding="utf-8",
    )
    assert queue.next_job()["job_id"] == "job-100"
    queue.mark_seen("job-100")
    assert queue.next_job() is None


def test_queue_writes_result_only_under_results(tmp_path):
    queue = WorkerQueue(tmp_path, SECRET)
    path = queue.write_result("job-200", "SUCCESS", {"files": []}, "ok")
    assert path == (
        tmp_path / "worker_jobs" / "results" / "job-200.json"
    ).resolve()
    data = json.loads(path.read_text(encoding="utf-8"))
    assert data["job_id"] == "job-200"
    assert data["status"] == "SUCCESS"


def test_media_probe_returns_capabilities_without_shell_input(tmp_path):
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


def test_unimplemented_render_job_fails_closed(tmp_path):
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
    assert "not enabled" in result["message"].lower()


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


def test_runner_processes_one_job_and_marks_seen(tmp_path):
    queue = _FakeQueue(
        {
            "job_id": "job-400",
            "job_type": "MEDIA_PROBE",
            "created_at": "2026-09-14T02:00:00+07:00",
            "args": {"targets": ["python"]},
        }
    )
    processed = run_once(queue, tmp_path)
    assert processed is True
    assert queue.seen == ["job-400"]
    assert queue.results[0][0] == "job-400"


def test_runner_returns_false_when_queue_empty(tmp_path):
    queue = _FakeQueue(None)
    assert run_once(queue, tmp_path) is False
