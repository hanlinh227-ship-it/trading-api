from __future__ import annotations

from pathlib import Path
import re
import shutil
from typing import Iterable


CHECKPOINT = "v1-5-pruned-emaonly.safetensors"
IPADAPTER_MODEL = "ip-adapter-plus_sd15.safetensors"
CLIP_VISION_MODEL = "CLIP-ViT-H-14-laion2B-s32B-b79K.safetensors"

DEFAULT_NEGATIVE = (
    "low quality, blurry, noisy, malformed, distorted anatomy, duplicate character, "
    "extra limbs, missing limbs, fused limbs, deformed hands, text, logo, watermark, "
    "cropped face, inconsistent costume, identity drift"
)


class WorkflowError(ValueError):
    pass


def _safe_component(value: str) -> str:
    cleaned = re.sub(r"[^A-Za-z0-9._-]+", "_", str(value).strip())
    cleaned = cleaned.strip("._")
    return cleaned or "job"


def stage_references(
    references: Iterable[tuple[str, Path]],
    comfyui_input_dir: Path,
    job_id: str,
) -> dict[str, str]:
    input_root = Path(comfyui_input_dir).expanduser().resolve()
    batch_dir = input_root / "curious_beyond" / _safe_component(job_id)
    batch_dir.mkdir(parents=True, exist_ok=True)
    staged: dict[str, str] = {}

    for reference_id, source_path in references:
        source = Path(source_path).expanduser().resolve()
        if not source.is_file():
            raise WorkflowError(f"reference asset missing: {source}")
        suffix = source.suffix.lower()
        if suffix not in {".png", ".jpg", ".jpeg", ".webp"}:
            raise WorkflowError(f"unsupported reference image type: {source.name}")
        target = batch_dir / f"{_safe_component(reference_id)}{suffix}"
        shutil.copy2(source, target)
        staged[str(reference_id)] = target.relative_to(input_root).as_posix()

    if not staged:
        raise WorkflowError("at least one declared reference is required")
    return staged


def _latent_dimensions(width: int, height: int) -> tuple[int, int]:
    if width <= 768 and height <= 432:
        return width, height
    scale = min(768 / width, 432 / height)
    latent_w = max(64, int(width * scale) // 8 * 8)
    latent_h = max(64, int(height * scale) // 8 * 8)
    return latent_w, latent_h


def build_sd15_reference_workflow(
    *,
    prompt: str,
    reference_input_names: list[str],
    seed: int,
    width: int,
    height: int,
    filename_prefix: str,
    negative_prompt: str = DEFAULT_NEGATIVE,
    checkpoint: str = CHECKPOINT,
    ipadapter_model: str = IPADAPTER_MODEL,
    clip_vision_model: str = CLIP_VISION_MODEL,
) -> dict[str, dict]:
    if not str(prompt).strip():
        raise WorkflowError("prompt is required")
    if not reference_input_names:
        raise WorkflowError("reference-conditioned workflow cannot run without references")
    if width <= 0 or height <= 0 or width % 8 or height % 8:
        raise WorkflowError("width and height must be positive multiples of 8")

    latent_w, latent_h = _latent_dimensions(width, height)
    graph: dict[str, dict] = {
        "1": {
            "class_type": "CheckpointLoaderSimple",
            "inputs": {"ckpt_name": checkpoint},
        },
        "2": {
            "class_type": "CLIPTextEncode",
            "inputs": {"text": str(prompt).strip(), "clip": ["1", 1]},
        },
        "3": {
            "class_type": "CLIPTextEncode",
            "inputs": {"text": negative_prompt, "clip": ["1", 1]},
        },
        "4": {
            "class_type": "EmptyLatentImage",
            "inputs": {"width": latent_w, "height": latent_h, "batch_size": 1},
        },
        "5": {
            "class_type": "IPAdapterModelLoader",
            "inputs": {"ipadapter_file": ipadapter_model},
        },
        "6": {
            "class_type": "CLIPVisionLoader",
            "inputs": {"clip_name": clip_vision_model},
        },
    }

    current_model: list[object] = ["1", 0]
    next_id = 7
    for index, image_name in enumerate(reference_input_names):
        load_id = str(next_id)
        ipa_id = str(next_id + 1)
        graph[load_id] = {
            "class_type": "LoadImage",
            "inputs": {"image": str(image_name)},
        }
        # Multiple unmasked references are chained conservatively to reduce identity blending.
        weight = 0.80 if index == 0 else 0.65
        graph[ipa_id] = {
            "class_type": "IPAdapterAdvanced",
            "inputs": {
                "model": current_model,
                "ipadapter": ["5", 0],
                "image": [load_id, 0],
                "weight": weight,
                "weight_type": "linear",
                "combine_embeds": "concat",
                "start_at": 0.0,
                "end_at": 0.85,
                "embeds_scaling": "V only",
                "clip_vision": ["6", 0],
            },
        }
        current_model = [ipa_id, 0]
        next_id += 2

    sampler_id = str(next_id)
    decode_id = str(next_id + 1)
    graph[sampler_id] = {
        "class_type": "KSampler",
        "inputs": {
            "model": current_model,
            "positive": ["2", 0],
            "negative": ["3", 0],
            "latent_image": ["4", 0],
            "seed": int(seed),
            "steps": 22,
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

    image_output: list[object] = [decode_id, 0]
    next_id += 2
    if (latent_w, latent_h) != (width, height):
        scale_id = str(next_id)
        graph[scale_id] = {
            "class_type": "ImageScale",
            "inputs": {
                "image": image_output,
                "upscale_method": "lanczos",
                "width": width,
                "height": height,
                "crop": "disabled",
            },
        }
        image_output = [scale_id, 0]
        next_id += 1

    save_id = str(next_id)
    graph[save_id] = {
        "class_type": "SaveImage",
        "inputs": {
            "images": image_output,
            "filename_prefix": str(filename_prefix),
        },
    }
    return graph
