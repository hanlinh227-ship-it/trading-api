from pathlib import Path

from money_ecosystem.render_gateway.video_qa import evaluate_video_continuity, sample_video_frames


def test_video_without_semantic_verifier_requires_human_review(tmp_path: Path):
    frame = tmp_path / "frame.png"
    frame.write_bytes(b"frame")
    report = evaluate_video_continuity([frame], semantic_verifier=None)
    assert report["terminal_status"] == "HUMAN_REVIEW"
    assert report["semantic_verified"] is False


def test_semantic_failure_is_rejected(tmp_path: Path):
    frame = tmp_path / "frame.png"
    frame.write_bytes(b"frame")
    report = evaluate_video_continuity([frame], semantic_verifier=lambda _: {"pass": False, "reason": "identity drift"})
    assert report["terminal_status"] == "REJECTED"
    assert "identity drift" in report["reason"]


def test_sample_video_frames_builds_deterministic_ffmpeg_command(tmp_path: Path, monkeypatch):
    video = tmp_path / "clip.mp4"
    video.write_bytes(b"fake-video")
    calls = []

    class Result:
        returncode = 0
        stdout = ""

    def fake_run(cmd, **kwargs):
        calls.append(cmd)
        out_pattern = Path(cmd[-1])
        out_pattern.parent.mkdir(parents=True, exist_ok=True)
        (out_pattern.parent / "frame_000001.png").write_bytes(b"frame")
        return Result()

    monkeypatch.setattr("money_ecosystem.render_gateway.video_qa.subprocess.run", fake_run)
    frames = sample_video_frames(video, 2.0)
    assert frames and frames[0].name == "frame_000001.png"
    assert "fps=1/2" in calls[0]
