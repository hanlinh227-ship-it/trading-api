import pytest

from money_ecosystem.render_gateway.control_plane import (
    ControlPlaneError,
    assert_same_attempt,
    attempt_path,
    result_path,
)


def _job(prompt="original"):
    return {
        "job_id": "job-1",
        "attempt_id": "a1",
        "project_id": "max-bus",
        "prompt": prompt,
    }


def test_revision_requires_new_attempt_id():
    with pytest.raises(ControlPlaneError, match="immutable"):
        assert_same_attempt(_job(), _job(prompt="changed"))


def test_identical_attempt_is_allowed():
    assert_same_attempt(_job(), dict(_job()))


def test_control_paths_are_compact_and_attempt_scoped():
    assert attempt_path("max-bus", "job-1", "a1") == (
        "render_gateway/jobs/max-bus/job-1/a1/request.json"
    )
    assert result_path("max-bus", "job-1", "a1") == (
        "render_gateway/jobs/max-bus/job-1/a1/result.json"
    )
