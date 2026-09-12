from __future__ import annotations

from pathlib import Path

import yaml


def _load(path: Path) -> dict:
    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError(f"invalid yaml mapping: {path}")
    return data


def resolve_context_nodes(
    v4_root: Path,
    primary: str,
    requested_bridges: list[str],
    *,
    profile: str,
    authority_loaded: bool = False,
) -> list[str]:
    """Resolve the bounded list of knowledge-mesh domains for a routed request.

    Bridges declared ``authority_required: true`` (every bridge touching ``trading``)
    may only be traversed after the caller has loaded the current project authority.
    """
    graph = _load(v4_root / "mesh/graph.yaml")
    bridges = _load(v4_root / "mesh/bridges.yaml")
    domains = {row["id"] for row in graph.get("domains", []) if isinstance(row, dict) and isinstance(row.get("id"), str)}
    if primary not in domains:
        raise ValueError(f"unknown primary domain: {primary}")
    if profile == "FAST":
        if requested_bridges:
            raise ValueError("FAST profile does not allow cross-domain bridge loading")
        return [primary]
    max_nodes = {"STANDARD": 2, "DEEP": 3}.get(profile)
    if max_nodes is None:
        raise ValueError(f"unknown profile: {profile}")
    legal = {
        (row.get("from"), row.get("to")): bool(row.get("authority_required", True))
        for row in bridges.get("bridges", [])
        if isinstance(row, dict)
    }
    result = [primary]
    for target in requested_bridges:
        if target in result:
            continue
        if (primary, target) not in legal:
            raise ValueError(f"illegal knowledge bridge: {primary}->{target}")
        if legal[(primary, target)] and not authority_loaded:
            raise PermissionError(f"bridge {primary}->{target} requires current project authority to be loaded first")
        result.append(target)
        if len(result) > max_nodes:
            raise ValueError(f"profile {profile} bridge-node budget exceeded")
    return result
