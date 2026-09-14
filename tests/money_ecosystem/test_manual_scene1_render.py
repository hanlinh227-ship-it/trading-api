from pathlib import Path

from money_ecosystem.worker.manual_scene1_render import build_scene1_job


def test_build_scene1_job_uses_local_refs_and_production_profile(tmp_path):
    job = build_scene1_job(tmp_path)
    assert job["job_type"] == "IMAGE_RENDER"
    args = job["args"]
    assert args["width"] == 1024
    assert args["height"] == 576
    assert args["workflow_profile"] == "sd15_reference_lowvram"
    assert args["max_attempts"] == 2
    assert [r["path"] for r in args["references"]] == [
        "assets/max-bus/max.png",
        "assets/max-bus/dad_max.png",
    ]
    assert args["scenes"][0]["reference_ids"] == ["max", "dad_max"]
