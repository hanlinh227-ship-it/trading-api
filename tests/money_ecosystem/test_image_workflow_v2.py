import pytest

from money_ecosystem.render_gateway.composition import CompositionBlueprint, Region
from money_ecosystem.worker.image_workflow_v2 import (
    LocalCompositionCapabilityMissing,
    build_local_regional_workflow,
)


REQUIRED_NODES = {
    "CheckpointLoaderSimple",
    "CLIPTextEncode",
    "EmptyLatentImage",
    "IPAdapterModelLoader",
    "CLIPVisionLoader",
    "LoadImage",
    "LoadImageMask",
    "IPAdapterAdvanced",
    "KSampler",
    "VAEDecode",
    "SaveImage",
}


def _blueprint():
    return CompositionBlueprint(
        anchor_id="layout-1",
        anchor_kind="layout_sketch",
        regions=(
            Region("character.max", 0.0, 0.2, 0.38, 1.0),
            Region("character.dad_max", 0.58, 0.1, 1.0, 0.8),
        ),
    )


def test_two_characters_receive_separate_attention_masks():
    graph = build_local_regional_workflow(
        prompt="Max waves while Dad Max drives",
        reference_inputs={"character.max": "max.png", "character.dad_max": "dad.png"},
        mask_inputs={"character.max": "max_mask.png", "character.dad_max": "dad_mask.png"},
        blueprint=_blueprint(),
        seed=123,
        width=768,
        height=432,
        filename_prefix="scene_01",
        available_nodes=REQUIRED_NODES,
    )
    ipa_nodes = [node for node in graph.values() if node["class_type"] == "IPAdapterAdvanced"]
    assert len(ipa_nodes) == 2
    assert all("attn_mask" in node["inputs"] for node in ipa_nodes)
    assert ipa_nodes[0]["inputs"]["image"] != ipa_nodes[1]["inputs"]["image"]
    assert ipa_nodes[0]["inputs"]["attn_mask"] != ipa_nodes[1]["inputs"]["attn_mask"]


def test_missing_mask_capability_fails_closed():
    nodes = set(REQUIRED_NODES)
    nodes.remove("LoadImageMask")
    with pytest.raises(LocalCompositionCapabilityMissing, match="LoadImageMask"):
        build_local_regional_workflow(
            prompt="scene",
            reference_inputs={"character.max": "max.png"},
            mask_inputs={"character.max": "max_mask.png"},
            blueprint=CompositionBlueprint("layout", "layout_sketch", (Region("character.max", 0, 0, 1, 1),)),
            seed=1,
            width=768,
            height=432,
            filename_prefix="scene",
            available_nodes=nodes,
        )
