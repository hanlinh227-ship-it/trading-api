from pathlib import Path
import pytest

from money_ecosystem.worker.image_workflow import (
    WorkflowError,
    build_sd15_reference_workflow,
    stage_references,
)


def test_builds_two_reference_ipadapter_chain_and_final_1024x576():
    graph = build_sd15_reference_workflow(
        prompt="Max waves beside a yellow bus while Dad Max drives",
        reference_input_names=["job/max.png", "job/dad.png"],
        seed=101000,
        width=1024,
        height=576,
        filename_prefix="curious_beyond/scene_01",
    )
    classes = [node["class_type"] for node in graph.values()]
    assert classes.count("LoadImage") == 2
    assert classes.count("IPAdapterAdvanced") == 2
    assert classes.count("KSampler") == 1
    assert classes.count("ImageScale") == 1
    scale = next(node for node in graph.values() if node["class_type"] == "ImageScale")
    assert scale["inputs"]["width"] == 1024
    assert scale["inputs"]["height"] == 576
    sampler = next(node for node in graph.values() if node["class_type"] == "KSampler")
    assert sampler["inputs"]["seed"] == 101000
    assert sampler["inputs"]["model"][0] != "1"  # reference conditioning is actually in the model path


def test_workflow_never_falls_back_without_reference():
    with pytest.raises(WorkflowError):
        build_sd15_reference_workflow(
            prompt="scene",
            reference_input_names=[],
            seed=1,
            width=1024,
            height=576,
            filename_prefix="scene",
        )


def test_stage_references_copies_declared_assets_into_dedicated_input_subdir(tmp_path):
    workspace = tmp_path / "repo"
    source = workspace / "assets" / "max.png"
    source.parent.mkdir(parents=True)
    source.write_bytes(b"png-bytes")
    input_dir = tmp_path / "comfy-input"

    staged = stage_references(
        references=[("max", source)],
        comfyui_input_dir=input_dir,
        job_id="scene-1/test",
    )

    assert staged == {"max": "curious_beyond/scene-1_test/max.png"}
    assert (input_dir / staged["max"]).read_bytes() == b"png-bytes"
