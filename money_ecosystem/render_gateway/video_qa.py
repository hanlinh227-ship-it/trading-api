from __future__ import annotations

from pathlib import Path
import subprocess
import tempfile
from typing import Any, Callable, Iterable


def sample_video_frames(path: Path | str, interval_seconds: float) -> list[Path]:
    video = Path(path)
    if not video.is_file():
        raise FileNotFoundError(video)
    if interval_seconds <= 0:
        raise ValueError("interval_seconds must be > 0")
    output_dir = Path(tempfile.mkdtemp(prefix="curious_video_qa_"))
    pattern = output_dir / "frame_%06d.png"
    fps_expr = f"fps=1/{interval_seconds:g}"
    result = subprocess.run(
        [
            "ffmpeg", "-hide_banner", "-loglevel", "error", "-y",
            "-i", str(video), "-vf", fps_expr, str(pattern),
        ],
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        check=False,
    )
    if result.returncode != 0:
        raise RuntimeError(f"ffmpeg frame sampling failed: {result.stdout.strip()}")
    return sorted(output_dir.glob("frame_*.png"))


def evaluate_video_continuity(
    frames: Iterable[Path | str],
    *,
    semantic_verifier: Callable[[list[Path]], dict[str, Any]] | None,
) -> dict[str, Any]:
    frame_paths = [Path(frame) for frame in frames]
    missing = [str(path) for path in frame_paths if not path.is_file() or path.stat().st_size == 0]
    if missing:
        return {
            "terminal_status": "REJECTED",
            "semantic_verified": False,
            "reason": "missing/empty sampled frames: " + ", ".join(missing),
        }
    if not frame_paths:
        return {
            "terminal_status": "REJECTED",
            "semantic_verified": False,
            "reason": "no sampled frames",
        }
    if semantic_verifier is None:
        return {
            "terminal_status": "HUMAN_REVIEW",
            "semantic_verified": False,
            "reason": "no semantic continuity verifier connected",
            "frame_count": len(frame_paths),
        }
    evidence = semantic_verifier(frame_paths) or {}
    passed = evidence.get("pass") is True
    return {
        "terminal_status": "VERIFIED" if passed else "REJECTED",
        "semantic_verified": passed,
        "reason": str(evidence.get("reason") or ("semantic continuity verified" if passed else "semantic continuity failed")),
        "frame_count": len(frame_paths),
        "evidence": evidence,
    }
