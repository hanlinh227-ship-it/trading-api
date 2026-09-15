from __future__ import annotations

import argparse
import json
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import yaml

try:
    from .model_mesh import normalize_candidate
except ImportError:
    from model_mesh import normalize_candidate


V4_ROOT = Path(__file__).resolve().parents[1]
DISCOVERY_CONFIG = V4_ROOT / "model_mesh/discovery.yaml"

MODELS_DEV_URL = "https://models.dev/api.json"
OPENCODE_ZEN_URL = "https://opencode.ai/zen/v1/models"
PORTKEY_MODELS_EVIDENCE = "https://github.com/Portkey-AI/models"


def _capability(name: str, supported: object, *, source: str, observed_at: str) -> tuple[str, dict] | None:
    if supported not in {True, False}:
        return None
    return name, {
        "supported": supported,
        "score": 0.0,
        "evidence": [source],
        "verified_at": observed_at,
    }


def _catalog_candidate(
    *,
    provider_id: str,
    model_id: str,
    model_family: str,
    observed_at: str,
    source: str,
    endpoint_family: str = "other",
    context_window: int | None = None,
    capabilities: dict[str, dict] | None = None,
) -> dict:
    raw = {
        "provider_class": "Q",
        "model_id": model_id,
        "model_family": model_family,
        "model_variant": "catalog_discovered",
        "endpoint_family": endpoint_family,
        "free_status": "unknown",
        "free_verified_at": None,
        "quota_scope": "unknown",
        "quota_dimensions": [],
        "reset_semantics": "unknown",
        "capabilities": capabilities or {},
        "context_window": context_window,
        "privacy_class": "unknown",
        "data_training_allowed_by_provider": None,
        "retention_policy": "",
        "usage_terms": "unknown",
        "health": "unavailable",
        "latency_ema_ms": None,
        "success_rate_ema": None,
        "quality_scores": {},
        "last_benchmark_at": None,
        "source_evidence": [source],
    }
    return normalize_candidate(provider_id, raw, observed_at=observed_at)


def _models_dev_capabilities(model: dict, *, observed_at: str) -> dict[str, dict]:
    source = MODELS_DEV_URL
    result: dict[str, dict] = {}
    nested = model.get("capabilities") if isinstance(model.get("capabilities"), dict) else {}
    pairs = [
        ("text_reasoning", model.get("reasoning", nested.get("reasoning"))),
        ("tool_calling", model.get("tool_call", nested.get("tool_calling"))),
        ("structured_output", model.get("structured_output", nested.get("structured_output"))),
    ]
    modalities = model.get("modalities") if isinstance(model.get("modalities"), dict) else {}
    inputs = modalities.get("input") if isinstance(modalities.get("input"), list) else []
    if inputs:
        pairs.append(("vision", "image" in inputs))
    for name, supported in pairs:
        row = _capability(name, supported, source=source, observed_at=observed_at)
        if row:
            result[row[0]] = row[1]
    return result


def parse_models_dev(payload: object, observed_at: str) -> list[dict]:
    if not isinstance(payload, dict):
        return []
    rows: list[dict] = []
    for provider_key, provider_raw in payload.items():
        if not isinstance(provider_raw, dict):
            continue
        provider_id = str(provider_raw.get("id") or provider_key).strip()
        if not provider_id:
            continue
        npm = str(provider_raw.get("npm") or "").lower()
        endpoint_family = "openai_compatible" if "openai-compatible" in npm else "other"
        models = provider_raw.get("models")
        if not isinstance(models, dict):
            continue
        for model_key, model_raw in models.items():
            if not isinstance(model_raw, dict):
                continue
            model_id = str(model_raw.get("id") or model_key).strip()
            if not model_id:
                continue
            family = str(model_raw.get("family") or model_raw.get("base_model") or model_id).strip()
            limit = model_raw.get("limit") if isinstance(model_raw.get("limit"), dict) else {}
            context_raw = limit.get("context")
            context = context_raw if isinstance(context_raw, int) and not isinstance(context_raw, bool) and context_raw > 0 else None
            rows.append(
                _catalog_candidate(
                    provider_id=provider_id,
                    model_id=model_id,
                    model_family=family,
                    observed_at=observed_at,
                    source=MODELS_DEV_URL,
                    endpoint_family=endpoint_family,
                    context_window=context,
                    capabilities=_models_dev_capabilities(model_raw, observed_at=observed_at),
                )
            )
    return rows


def parse_opencode_zen(payload: object, observed_at: str) -> list[dict]:
    if not isinstance(payload, dict):
        return []
    data = payload.get("data")
    if not isinstance(data, list):
        return []
    rows: list[dict] = []
    for item in data:
        if not isinstance(item, dict):
            continue
        model_id = str(item.get("id") or "").strip()
        if not model_id:
            continue
        # Even an explicit '-free' model id is not account-entitlement proof.
        family = str(item.get("model_family") or model_id).strip()
        rows.append(
            _catalog_candidate(
                provider_id="opencode_zen",
                model_id=model_id,
                model_family=family,
                observed_at=observed_at,
                source=OPENCODE_ZEN_URL,
            )
        )
    return rows


def parse_portkey_models(payload: object, observed_at: str) -> list[dict]:
    if not isinstance(payload, dict):
        return []
    provider_id = str(payload.get("provider") or "portkey_catalog").strip()
    models = payload.get("models")
    if not isinstance(models, dict):
        # Raw Portkey provider pricing files are keyed directly by model id.
        models = {key: value for key, value in payload.items() if key not in {"provider", "default"} and isinstance(value, dict)}
    rows: list[dict] = []
    for model_id, model_raw in models.items():
        if not isinstance(model_raw, dict):
            continue
        model_name = str(model_id).strip()
        if not model_name:
            continue
        family = str(model_raw.get("model_family") or model_raw.get("family") or model_name).strip()
        # Pricing metadata, including zero prices, remains evidence only.
        rows.append(
            _catalog_candidate(
                provider_id=provider_id,
                model_id=model_name,
                model_family=family,
                observed_at=observed_at,
                source=PORTKEY_MODELS_EVIDENCE,
            )
        )
    return rows


def merge_candidates(*groups: list[dict]) -> list[dict]:
    merged: dict[tuple[str, str], dict] = {}
    order: list[tuple[str, str]] = []
    for group in groups:
        for candidate in group:
            if not isinstance(candidate, dict):
                continue
            key = (str(candidate.get("provider_id") or ""), str(candidate.get("model_id") or ""))
            if not all(key):
                continue
            if key not in merged:
                merged[key] = dict(candidate)
                order.append(key)
                continue
            current = merged[key]
            evidence = list(current.get("source_evidence", []))
            for source in candidate.get("source_evidence", []):
                if source not in evidence:
                    evidence.append(source)
            current["source_evidence"] = evidence
            if current.get("context_window") is None and candidate.get("context_window") is not None:
                current["context_window"] = candidate["context_window"]
            if current.get("endpoint_family") == "other" and candidate.get("endpoint_family") != "other":
                current["endpoint_family"] = candidate["endpoint_family"]
            capabilities = dict(current.get("capabilities", {}))
            for name, value in candidate.get("capabilities", {}).items():
                capabilities.setdefault(name, value)
            current["capabilities"] = capabilities
            # Conflicting or catalog-only economics never auto-promote to free.
            if current.get("free_status") != candidate.get("free_status"):
                current["free_status"] = "unknown"
                current["free_verified_at"] = None
    return [merged[key] for key in order]


def _load_config() -> dict:
    data = yaml.safe_load(DISCOVERY_CONFIG.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError("model mesh discovery config must be a mapping")
    return data


def _fetch_json(url: str, *, timeout: int, user_agent: str) -> object:
    request = urllib.request.Request(url, headers={"Accept": "application/json", "User-Agent": user_agent})
    with urllib.request.urlopen(request, timeout=timeout) as response:
        return json.loads(response.read().decode("utf-8"))


def _fixture_payload(fixture_dir: Path, name: str) -> object:
    return json.loads((fixture_dir / name).read_text(encoding="utf-8"))


def discover(output: Path, fixture_dir: Path | None = None) -> dict:
    config = _load_config()
    network = config.get("network", {})
    timeout = int(network.get("timeout_seconds", 20))
    user_agent = str(network.get("user_agent") or "github-brain-v4-model-mesh-discovery")
    observed_at = datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")
    groups: list[list[dict]] = []
    errors: list[dict] = []

    sources = config.get("catalog_sources", {})
    parsers = {
        "models_dev": parse_models_dev,
        "opencode_zen": parse_opencode_zen,
        "portkey_models": parse_portkey_models,
    }
    fixture_names = {
        "models_dev": "models_dev.json",
        "opencode_zen": "opencode_zen.json",
        "portkey_models": "portkey_models.json",
    }

    for source_id, parser in parsers.items():
        source = sources.get(source_id, {}) if isinstance(sources, dict) else {}
        try:
            if fixture_dir is not None:
                payload = _fixture_payload(Path(fixture_dir), fixture_names[source_id])
            else:
                payload = _fetch_json(str(source["url"]), timeout=timeout, user_agent=user_agent)
                provider_hint = source.get("provider_hint")
                if source_id == "portkey_models" and provider_hint and isinstance(payload, dict) and "provider" not in payload:
                    payload = {"provider": provider_hint, "models": payload}
            groups.append(parser(payload, observed_at))
        except Exception as exc:
            errors.append({"source": source_id, "error": type(exc).__name__})

    report = {
        "generated_at": observed_at,
        "state": "quarantine",
        "routing_authority": False,
        "stable_mutation": False,
        "candidates": merge_candidates(*groups),
        "errors": errors,
    }
    output = Path(output)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return report


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Discover free-model candidates into Evergreen quarantine")
    parser.add_argument("--root", default=".")
    parser.add_argument("--output", required=True)
    parser.add_argument("--fixture-dir", default=None)
    args = parser.parse_args(argv)
    root = Path(args.root).resolve()
    output = Path(args.output)
    if not output.is_absolute():
        output = root / output
    fixture_dir = Path(args.fixture_dir) if args.fixture_dir else None
    report = discover(output=output, fixture_dir=fixture_dir)
    print(
        "MODEL_MESH_DISCOVERY=PASS "
        f"candidates={len(report['candidates'])} errors={len(report['errors'])} state={report['state']}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
