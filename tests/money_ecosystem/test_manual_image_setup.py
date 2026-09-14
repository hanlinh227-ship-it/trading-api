from pathlib import Path

from money_ecosystem.worker import manual_image_setup


def test_root_from_system_stats_argv_base_directory(tmp_path):
    root = tmp_path / "ComfyData"
    (root / "models").mkdir(parents=True)
    stats = {"system": {"argv": ["main.py", "--base-directory", str(root), "--port", "8188"]}}
    assert manual_image_setup.root_from_system_stats(stats) == root.resolve()


def test_root_from_system_stats_extra_models_config(tmp_path):
    root = tmp_path / "ComfyData"
    (root / "models").mkdir(parents=True)
    cfg = tmp_path / "extra_model_paths.yaml"
    cfg.write_text(f"desktop:\n  base_path: '{root}'\n", encoding="utf-8")
    stats = {"system": {"argv": ["main.py", "--extra-model-paths-config", str(cfg)]}}
    assert manual_image_setup.root_from_system_stats(stats) == root.resolve()


def test_install_rejects_non_comfy_root(tmp_path):
    try:
        manual_image_setup.install_to_root(tmp_path)
    except manual_image_setup.ManualSetupError as exc:
        assert "models" in str(exc).lower()
    else:
        raise AssertionError("expected ManualSetupError")
