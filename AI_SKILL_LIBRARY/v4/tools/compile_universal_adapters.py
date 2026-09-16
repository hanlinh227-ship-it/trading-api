from __future__ import annotations

import argparse
import json
import re
from pathlib import Path

import yaml

SHA_RE = re.compile(r"^[0-9a-f]{40}$")
PRINCIPAL_TYPES = {"user", "internal"}


def _load_registry(root: Path) -> dict:
    path = root / "AI_SKILL_LIBRARY/v4/adapters/registry.yaml"
    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError("adapter_registry_must_be_mapping")
    return data


def compile_registry(root: Path, source_sha: str) -> dict:
    root = root.resolve()
    source_sha = str(source_sha or "").strip().lower()
    if not SHA_RE.fullmatch(source_sha):
        raise ValueError("source_sha_must_be_40_hex")
    data = _load_registry(root)
    rows = data.get("adapters")
    if not isinstance(rows, list) or not rows:
        raise ValueError("adapter_registry_requires_rows")

    seen_ids: set[str] = set()
    seen_bindings: set[str] = set()
    adapters: list[dict] = []
    for raw in rows:
        if not isinstance(raw, dict):
            raise ValueError("adapter_row_must_be_mapping")
        adapter_id = str(raw.get("id") or "").strip().lower()
        principal_type = str(raw.get("principal_type") or "user").strip().lower()
        binding = str(raw.get("token_binding") or "").strip()
        scopes_raw = raw.get("scopes")
        if not adapter_id or adapter_id in seen_ids:
            raise ValueError(f"invalid_or_duplicate_adapter_id:{adapter_id}")
        if principal_type not in PRINCIPAL_TYPES:
            raise ValueError(f"invalid_principal_type:{adapter_id}:{principal_type}")
        if not binding or binding in seen_bindings:
            raise ValueError(f"invalid_or_duplicate_token_binding:{binding}")
        if not isinstance(scopes_raw, list) or not scopes_raw:
            raise ValueError(f"adapter_scopes_required:{adapter_id}")
        scopes = sorted({str(scope).strip() for scope in scopes_raw if str(scope).strip()})
        if principal_type == "user" and "brain.route" not in scopes:
            raise ValueError(f"brain_route_scope_required:{adapter_id}")
        if principal_type == "internal" and "brain.route" in scopes:
            raise ValueError(f"internal_route_scope_forbidden:{adapter_id}")
        if raw.get("routing_authority") is not False or raw.get("reasoning_authority") is not False:
            raise ValueError(f"adapter_authority_forbidden:{adapter_id}")
        seen_ids.add(adapter_id)
        seen_bindings.add(binding)
        adapters.append(
            {
                "id": adapter_id,
                "principal_type": principal_type,
                "token_binding": binding,
                "scopes": scopes,
                "routing_authority": False,
                "reasoning_authority": False,
            }
        )

    adapters.sort(key=lambda row: row["id"])
    return {
        "schema_version": 1,
        "source_sha": source_sha,
        "authority": False,
        "adapters": adapters,
    }


def write_payload(payload: dict, output: Path) -> None:
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(payload, sort_keys=True, separators=(",", ":")) + "\n", encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", default=".")
    parser.add_argument("--source-sha", required=True)
    parser.add_argument("--output", default="AI_SKILL_LIBRARY/v4/runtime/generated/universal-adapters.json")
    args = parser.parse_args()
    root = Path(args.root).resolve()
    try:
        payload = compile_registry(root, args.source_sha)
        output = (root / args.output).resolve()
        output.relative_to(root)
        write_payload(payload, output)
    except (OSError, ValueError, yaml.YAMLError) as exc:
        print(f"[ERROR] {exc}")
        return 1
    print(f"UNIVERSAL_ADAPTERS_COMPILE=PASS source_sha={payload['source_sha']} adapters={len(payload['adapters'])}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
