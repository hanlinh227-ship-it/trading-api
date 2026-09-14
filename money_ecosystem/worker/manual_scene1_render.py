from __future__ import annotations

from datetime import datetime, timezone
import json
from pathlib import Path

from .runtime import execute_job


SCENE1_PROMPT = (
    "3D preschool animation, soft rounded shapes, bright pastel colors, clean child-friendly lighting. "
    "BG1 pastel neighborhood street at a bus stop. Medium-wide low three-quarter front view. "
    "Max, exactly matching the declared Max reference, stands on the sidewalk happily waving toward the approaching fixed yellow bus. "
    "Dad Max, exactly matching the declared Dad Max reference, is visible exactly once in the driver seat, wearing a navy suit, white shirt and black tie. "
    "Exactly two characters visible: Max and Dad Max. Yellow bus body, light-blue lower body, cream roof, large rounded windows. "
    "Natural anatomy, correct hands and limbs, stable faces and outfits, no duplicated people, no extra characters, no text, no logo, no watermark."
)


def build_scene1_job(repo_root: Path | str) -> dict:
    _ = Path(repo_root).resolve()
    return {
        "job_id": "image-render-scene01-manual-smoke",
        "job_type": "IMAGE_RENDER",
        "created_at": datetime.now(timezone.utc).isoformat(),
        "args": {
            "project_id": "max-bus",
            "width": 1024,
            "height": 576,
            "max_attempts": 2,
            "workflow_profile": "sd15_reference_lowvram",
            "references": [
                {"id": "max", "path": "assets/max-bus/max.png", "character": "Max"},
                {"id": "dad_max", "path": "assets/max-bus/dad_max.png", "character": "Dad Max"},
            ],
            "scenes": [
                {"id": 1, "prompt": SCENE1_PROMPT, "reference_ids": ["max", "dad_max"]}
            ],
        },
    }


def main() -> int:
    repo_root = Path(__file__).resolve().parents[2]
    job = build_scene1_job(repo_root)
    result = execute_job(job, repo_root)
    print(json.dumps(result, indent=2, ensure_ascii=False))
    return 0 if result.get("status") == "SUCCESS" else 2


if __name__ == "__main__":
    raise SystemExit(main())
