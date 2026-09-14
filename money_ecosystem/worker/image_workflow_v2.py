from __future__ import annotations

from typing import Mapping

from money_ecosystem.render_gateway.composition import CompositionBlueprint
from .image_workflow import (
    CHECKPOINT,
    CLIP_VISION_MODEL,
    DEFAULT_NEGATIVE,
    IPADAPTER_MODEL,
)


class LocalCompositionCapabilityMissing(RuntimeError):
    pass


_REQUIRED_NODES = {
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


def build_local_regional_workflow(
    *,
    prompt: str,
    reference_inputs: Mapping[str, str],
    mask_inputs: Mapping[str, str],
    blueprint: CompositionBlueprint,
    seed: int,
    width: int,
    height: int,
    filename_prefix: str,
    available_nodes: set[str],
    checkpoint: str = CHECKPOINT,
    ipadapter_model: str = IPADAPTER_MODEL,
    clip_vision_model: str = CLIP_VISION_MODEL,
    negative_prompt: str = DEFAULT_NEGATIVE,
) -> dict[str, dict]:
    """Build a low-VRAM DRAFT_LOCAL workflow with per-entity attention masks.

    This is intentionally not a FLOW_GRADE implementation. It exists to avoid
    identity blending in local drafts and fails closed when regional-mask
    capability is absent.
    """

    blueprint.validate()
    missing_nodes = sorted(_REQUIRED_NODES - set(available_nodes))
    if missing_nodes:
        raise LocalCompositionCapabilityMissing(
            "LOCAL_COMPOSITION_CAPABILITY_MISSING: " + ", ".join(missing_nodes)
        )
    if not prompt.strip():
        raise ValueError("prompt is required")
    if width <= 0 or height <= 0 or width % 8 or height % 8:
        raise ValueError("width and height must be positive multiples of 8")

    entities = tuple(region.entity_id for region in blueprint.regions)
    if set(reference_inputs) != set(entities):
        raise ValueError("reference_inputs must exactly match blueprint entities")
    if set(mask_inputs) != set(entities):
        raise ValueError("mask_inputs must exactly match blueprint entities")

    graph: dict[str, dict] = {
        "1": {"class_type": "CheckpointLoaderSimple", "inputs": {"ckpt_name": checkpoint}},
        "2": {"class_type": "CLIPTextEncode", "inputs": {"text": prompt.strip(), "clip": ["1", 1]}},
        "3": {"class_type": "CLIPTextEncode", "inputs": {"text": negative_prompt, "clip": ["1", 1]}},
        "4": {"class_type": "EmptyLatentImage", "inputs": {"width": width, "height": height, "batch_size": 1}},
        "5": {"class_type": "IPAdapterModelLoader", "inputs": {"ipadapter_file": ipadapter_model}},
        "6": {"class_type": "CLIPVisionLoader", "inputs": {"clip_name": clip_vision_model}},
    }

    current_model: list[object] = ["1", 0]
    next_id = 7
    for entity_id in entities:
        image_id = str(next_id)
        mask_id = str(next_id + 1)
        ipa_id = str(next_id + 2)
        graph[image_id] = {
            "class_type": "LoadImage",
            "inputs": {"image": reference_inputs[entity_id]},
            "_meta": {"entity_id": entity_id, "role": "reference"},
        }
        graph[mask_id] = {
            "class_type": "LoadImageMask",
            "inputs": {"image": mask_inputs[entity_id], "channel": "red"},
            "_meta": {"entity_id": entity_id, "role": "attention_mask"},
        }
        graph[ipa_id] = {
            "class_type": "IPAdapterAdvanced",
            "inputs": {
                "model": current_model,
                "ipadapter": ["5", 0],
                "image": [image_id, 0],
                "weight": 0.85,
                "weight_type": "linear",
                "combine_embeds": "concat",
                "start_at": 0.0,
                "end_at": 0.9,
                "embeds_scaling": "V only",
                "clip_vision": ["6", 0],
                "attn_mask": [mask_id, 0],
            },
            "_meta": {"entity_id": entity_id, "conditioning": "regional_masked"},
        }
        current_model = [ipa_id, 0]
        next_id += 3

    sampler_id = str(next_id)
    decode_id = str(next_id + 1)
    save_id = str(next_id + 2)
    graph[sampler_id] = {
        "class_type": "KSampler",
        "inputs": {
            "model": current_model,
            "positive": ["2", 0],
            "negative": ["3", 0],
            "latent_image": ["4", 0],
            "seed": int(seed),
            "steps": 28,
            "cfg": 6.0,
            "sampler_name": "dpmpp_2m",
            "scheduler": "karras",
            "denoise": 1.0,
        },
    }
    graph[decode_id] = {
        "class_type": "VAEDecode",
        "inputs": {"samples": [sampler_id, 0], "vae": ["1", 2]},
    }
    graph[save_id] = {
        "class_type": "SaveImage",
        "inputs": {"images": [decode_id, 0], "filename_prefix": filename_prefix},
    }
    return graph
