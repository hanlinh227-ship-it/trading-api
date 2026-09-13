from money_ecosystem.worker import runtime


def _job(tmp_path):
    ref = tmp_path / "assets" / "max.png"
    ref.parent.mkdir(parents=True, exist_ok=True)
    return {
        "job_id": "image-test",
        "job_type": "IMAGE_RENDER",
        "created_at": "2026-09-14T06:50:00+07:00",
        "args": {
            "project_id": "max-bus",
            "width": 1024,
            "height": 576,
            "max_attempts": 1,
            "workflow_profile": "sd15_reference_lowvram",
            "references": [{"id": "max", "path": "assets/max.png", "character": "Max"}],
            "scenes": [{"id": 1, "prompt": "Max waves", "reference_ids": ["max"]}],
        },
    }


def test_image_render_blocks_with_exact_missing_reference(tmp_path):
    result = runtime.execute_job(_job(tmp_path), tmp_path)
    assert result["status"] == "BLOCKED"
    assert "assets/max.png" in result["message"].replace("\\", "/")


def test_image_render_runs_comfyui_preflight_after_refs_exist(monkeypatch, tmp_path):
    job = _job(tmp_path)
    (tmp_path / "assets" / "max.png").write_bytes(b"x")

    class FakeAdapter:
        def preflight(self):
            raise runtime.DependencyMissing("IPAdapter reference-conditioning nodes")

    monkeypatch.setattr(runtime, "ComfyUIAdapter", lambda: FakeAdapter())
    result = runtime.execute_job(job, tmp_path)
    assert result["status"] == "BLOCKED"
    assert "IPAdapter" in result["message"]
