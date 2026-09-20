#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import re
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[3]

LOCAL_PROVIDER_IDS = {
    "ephemeral-local-0",
    "github_actions_ubuntu_latest",
}


def _yaml(path: Path) -> dict:
    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    return data if isinstance(data, dict) else {}


def _json(path: Path) -> dict:
    data = json.loads(path.read_text(encoding="utf-8"))
    return data if isinstance(data, dict) else {}


def validate(root: Path = ROOT) -> list[str]:
    root = Path(root)
    errors: list[str] = []

    policy = _yaml(root / "AI_SKILL_LIBRARY/v4/model_mesh/policy.yaml")
    active = _json(root / "AI_SKILL_LIBRARY/v4/model_mesh/active.json")
    bindings = _json(root / "AI_SKILL_LIBRARY/v4/model_mesh/runtime_bindings.json")
    cloud = policy.get("cloud_24x7") or {}

    expected_false = {
        "personal_pc_required",
        "local_runtime_required",
        "local_fallback_allowed",
        "paid_fallback_allowed",
        "all_models_must_be_hot",
    }
    if cloud.get("enabled") is not True:
        errors.append("cloud_24x7.enabled must be true")
    if cloud.get("semantics") != "service_continuity_not_all_models_hot":
        errors.append("cloud_24x7 semantics must distinguish service continuity from all-model residency")
    for key in expected_false:
        if cloud.get(key) is not False:
            errors.append(f"cloud_24x7.{key} must be false")
    if cloud.get("provider_managed_residency") is not True:
        errors.append("cloud_24x7.provider_managed_residency must be true")

    refresh = cloud.get("health_refresh") or {}
    cadence = int(refresh.get("cadence_minutes") or 0)
    ttl = int(refresh.get("live_evidence_ttl_minutes") or 0)
    if refresh.get("authority") != "cloudflare_worker_cron":
        errors.append("cloud health refresh authority must be Cloudflare Worker cron")
    if cadence <= 0 or ttl <= 0 or cadence >= ttl:
        errors.append("cloud health refresh cadence must stay strictly inside live evidence TTL")
    if refresh.get("opportunistic_self_heal") is not True:
        errors.append("cloud 24x7 must keep opportunistic self-heal enabled")
    if refresh.get("request_path_probe_blocking") is not False:
        errors.append("health probes must not block the request path")

    failover = cloud.get("failover") or {}
    for key in (
        "quota_aware",
        "health_aware",
        "model_family_diversity",
        "rotate_on_429",
        "rotate_on_5xx",
        "rotate_before_free_quota_exhaustion",
        "respect_provider_reset",
        "never_open_second_account_to_bypass_quota",
    ):
        if failover.get(key) is not True:
            errors.append(f"cloud_24x7.failover.{key} must be true")

    if policy.get("mode") != "FREE_ONLY":
        errors.append("Model Mesh must remain FREE_ONLY")
    if policy.get("paid_fallback") != "disabled" or policy.get("auto_purchase") is not False:
        errors.append("paid fallback and auto purchase must remain disabled")
    fallback = policy.get("fallback") or {}
    if fallback.get("stable_survives_mesh_failure") is not True:
        errors.append("Stable runtime must survive mesh failure")
    if fallback.get("rotate_to_next_verified_zero_cost_candidate") is not True:
        errors.append("mesh must rotate to the next verified zero-cost candidate")

    models = active.get("models") or []
    eligible = [
        m for m in models
        if isinstance(m, dict) and m.get("registry_state") != "NOT_ELIGIBLE"
    ]
    min_models = int(cloud.get("minimum_active_eligible_models") or 0)
    min_providers = int(cloud.get("minimum_independent_provider_paths") or 0)
    providers = {str(m.get("provider_id") or "") for m in eligible if m.get("provider_id")}
    if len(eligible) < min_models:
        errors.append(f"eligible active models {len(eligible)} < required {min_models}")
    if len(providers) < min_providers:
        errors.append(f"independent cloud providers {len(providers)} < required {min_providers}")

    runtime_bindings = bindings.get("bindings") or {}
    for provider in sorted(providers):
        if provider in LOCAL_PROVIDER_IDS:
            errors.append(f"active cloud pool must not depend on local execution provider {provider}")
            continue
        row = runtime_bindings.get(provider)
        if not isinstance(row, dict) or row.get("enabled") is not True:
            errors.append(f"eligible provider {provider} lacks an enabled runtime binding")

    scheduler = (root / "cloudflare-worker/model-mesh/scheduled-health.js").read_text(encoding="utf-8")
    expected_cron = f"*/{cadence} * * * *"
    if f"HEALTH_REFRESH_CRON = '{expected_cron}'" not in scheduler:
        errors.append(f"Cloudflare health cron must match policy cadence: {expected_cron}")
    if "claimSelfHeal" not in scheduler or "probeProviders" not in scheduler:
        errors.append("Cloudflare health cron must use bounded self-heal and canonical provider probing")

    wrangler = (root / "cloudflare-worker/prepare-wrangler.mjs").read_text(encoding="utf-8")
    if "triggers:{crons:[HEALTH_REFRESH_CRON]}" not in wrangler.replace(" ", ""):
        errors.append("wrangler generation must carry the canonical health cron")
    if "MODEL_MESH_EXECUTION_ENABLED:'1'" not in wrangler:
        errors.append("Cloudflare deployment must enable Model Mesh execution")

    checkpoint = (root / "AI_SKILL_LIBRARY/AI_GLOBAL_CHECKPOINT.md").read_text(encoding="utf-8")
    if "PERSONAL_PC_REQUIRED = false" not in checkpoint:
        errors.append("global checkpoint must keep PERSONAL_PC_REQUIRED=false")

    return errors


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path, default=ROOT)
    args = parser.parse_args()
    errors = validate(args.root)
    for error in errors:
        print(f"[ERROR] {error}")
    print(f"CLOUD_24X7_VALIDATE={'PASS' if not errors else 'FAIL'} errors={len(errors)}")
    return 1 if errors else 0


if __name__ == "__main__":
    raise SystemExit(main())
