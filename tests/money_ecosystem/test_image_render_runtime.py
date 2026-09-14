from pathlib import Path

from PIL import Image

from money_ecosystem.worker import runtime
from money_ecosystem.worker.comfyui_adapter import RenderArtifact


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


def test_image_render_executes_one_scene_and_packages_zip(monkeypatch, tmp_path):
    job = _job(tmp_path)
    ref_path = tmp_path / "assets" / "max.png"
    Image.new("RGB", (256, 256), "white").save(ref_path)
    comfy_input = tmp_path / "comfy-input"
    submitted = []

    class FakeAdapter:
        def preflight(self):
            return {"reference_nodes": ["IPAdapterAdvanced"], "checkpoints": ["v1-5-pruned-emaonly.safetensors"]}

        def input_directory(self):
            comfy_input.mkdir(parents=True, exist_ok=True)
            return comfy_input

        def submit(self, workflow):
            submitted.append(workflow)
            return "prompt-1"

        def wait(self, prompt_id):
            assert prompt_id == "prompt-1"
            return RenderArtifact("fake.png")

        def fetch_artifact(self, artifact, target):
            Image.new("RGB", (1024, 576), "white").save(target)
            return Path(target)

    monkeypatch.setattr(runtime, "ComfyUIAdapter", lambda: FakeAdapter())
    result = runtime.execute_job(job, tmp_path)

    assert result["status"] == "SUCCESS"
    manifest = result["artifact_manifest"]
    assert manifest["accepted"] == 1
    assert manifest["failed"] == 0
    assert Path(manifest["zip_path"]).is_file()
    assert Path(manifest["manifest_path"]).is_file()
    assert submitted and any(node["class_type"] == "IPAdapterAdvanced" for node in submitted[0].values())
