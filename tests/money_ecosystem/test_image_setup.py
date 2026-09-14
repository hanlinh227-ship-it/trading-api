from pathlib import Path

from money_ecosystem.worker import image_setup


def test_find_comfyui_root_prefers_candidate_with_models_and_custom_nodes(tmp_path):
    bad = tmp_path / "bad"
    good = tmp_path / "good"
    (bad / "models").mkdir(parents=True)
    (good / "models").mkdir(parents=True)
    (good / "custom_nodes").mkdir()

    found = image_setup.find_comfyui_root([bad, good])
    assert found == good.resolve()


def test_discover_comfyui_root_finds_nested_desktop_data_directory(tmp_path):
    root = tmp_path / "AppData" / "Roaming" / "ComfyUI" / "app" / "ComfyUI"
    (root / "models").mkdir(parents=True)
    (root / "custom_nodes").mkdir()

    found = image_setup.discover_comfyui_root([tmp_path], max_depth=6)
    assert found == root.resolve()


def test_discover_comfyui_root_respects_depth_bound(tmp_path):
    root = tmp_path / "a" / "b" / "c" / "d" / "e" / "ComfyUI"
    (root / "models").mkdir(parents=True)
    (root / "custom_nodes").mkdir()

    assert image_setup.discover_comfyui_root([tmp_path], max_depth=2) is None


def test_bootstrap_plan_is_fixed_zero_cost_and_hash_pinned(tmp_path):
    root = tmp_path / "ComfyUI"
    (root / "models").mkdir(parents=True)
    (root / "custom_nodes").mkdir()

    plan = image_setup.build_bootstrap_plan(root)
    assert plan["zero_paid_services"] is True
    assert plan["cloud_fallback"] is False
    assert plan["node_repo"]["url"] == "https://github.com/cubiq/ComfyUI_IPAdapter_plus.git"
    assert len(plan["node_repo"]["commit"]) == 40
    names = {item["name"] for item in plan["files"]}
    assert names == {
        "v1-5-pruned-emaonly.safetensors",
        "ip-adapter-plus_sd15.safetensors",
        "CLIP-ViT-H-14-laion2B-s32B-b79K.safetensors",
    }
    assert all(len(item["sha256"]) == 64 for item in plan["files"])


def test_runtime_accepts_only_fixed_image_setup_action(monkeypatch, tmp_path):
    from money_ecosystem.worker import runtime

    monkeypatch.setattr(
        runtime,
        "bootstrap_reference_stack",
        lambda: {"status": "INSTALLED", "restart_required": True, "zero_paid_services": True},
    )
    ok = runtime.execute_job(
        {
            "job_id": "setup-1",
            "job_type": "IMAGE_SETUP",
            "created_at": "2026-09-14T07:10:00+07:00",
            "args": {"action": "bootstrap_reference_stack"},
        },
        tmp_path,
    )
    assert ok["status"] == "SUCCESS"
    assert ok["artifact_manifest"]["restart_required"] is True

    bad = runtime.execute_job(
        {
            "job_id": "setup-2",
            "job_type": "IMAGE_SETUP",
            "created_at": "2026-09-14T07:10:00+07:00",
            "args": {"action": "download_any_url"},
        },
        tmp_path,
    )
    assert bad["status"] == "BLOCKED"
