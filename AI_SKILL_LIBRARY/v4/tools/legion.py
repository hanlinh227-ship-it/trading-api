from __future__ import annotations

import copy
import json
from pathlib import Path
from typing import Any

import yaml
from jsonschema import Draft202012Validator


_PERMISSION_RANK = {"read_only": 0, "bounded_write": 1, "sandbox_execute": 2}
_RISK_RANK = {"A": 0, "B": 1, "C": 2, "D": 3}
_PROFILE_PARALLEL = {"FAST": 0, "STANDARD": 2, "DEEP": 4}
_FORBIDDEN_TOOLS = {"financial_execution", "credential_mutation", "permission_widening", "destructive_production"}


def _schema(root: Path, name: str) -> dict[str, Any]:
    return json.loads((root / "AI_SKILL_LIBRARY/v4/schemas" / name).read_text(encoding="utf-8"))


def load_agent_registry(root: Path) -> dict[str, dict]:
    payload = yaml.safe_load((root / "AI_SKILL_LIBRARY/v4/legion/agents.yaml").read_text(encoding="utf-8"))
    agents = payload.get("agents", {}) if isinstance(payload, dict) else {}
    if not isinstance(agents, dict):
        raise ValueError("legion agents registry must be a mapping")
    return {str(agent_id): dict(agent) for agent_id, agent in agents.items()}


def validate_agent_contract(agent: dict) -> list[str]:
    root = Path(__file__).resolve().parents[3]
    validator = Draft202012Validator(_schema(root, "legion_agent.schema.json"))
    errors = [f"{'.'.join(str(p) for p in err.path) or '<root>'}: {err.message}" for err in validator.iter_errors(agent)]
    if agent.get("routing_authority") is not False:
        errors.append("routing_authority must be false")
    if agent.get("reasoning_authority") is not False:
        errors.append("reasoning_authority must be false")
    if set(agent.get("tools", [])) & _FORBIDDEN_TOOLS:
        errors.append("forbidden high-risk tool declared")
    if agent.get("agent_id") == "quant_researcher":
        if agent.get("research_only") is not True:
            errors.append("quant_researcher must be research_only")
        if agent.get("live_financial_execution") is not False:
            errors.append("quant_researcher live_financial_execution must be false")
    return sorted(set(errors))


def _can_cover_ceiling(agent_value: str, required_value: str, ranks: dict[str, int]) -> bool:
    return agent_value in ranks and required_value in ranks and ranks[agent_value] >= ranks[required_value]


def eligible_agents(task: dict, agents: dict[str, dict]) -> list[dict]:
    required_tools = set(task.get("required_tools", []))
    if required_tools & _FORBIDDEN_TOOLS:
        return []

    domain = task.get("domain")
    mode = task.get("mode")
    required_caps = set(task.get("required_model_capabilities", []))
    permission = task.get("permission_ceiling", "read_only")
    risk = task.get("risk_ceiling", "A")
    data_class = task.get("data_class", "PUBLIC")

    selected: list[dict] = []
    for agent_id in sorted(agents):
        agent = agents[agent_id]
        if validate_agent_contract(agent):
            continue
        if domain not in agent.get("domains", []):
            continue
        modes = agent.get("modes", [])
        if mode and mode not in modes:
            continue
        if not _can_cover_ceiling(agent.get("permission_ceiling", ""), permission, _PERMISSION_RANK):
            continue
        if not _can_cover_ceiling(agent.get("risk_ceiling", ""), risk, _RISK_RANK):
            continue
        if not required_tools.issubset(set(agent.get("tools", []))):
            continue
        if not required_caps.issubset(set(agent.get("model_capabilities", []))):
            continue
        if data_class not in agent.get("privacy_classes", []):
            continue
        selected.append(dict(agent))
    return selected


def _validate_task_node(node: dict) -> list[str]:
    root = Path(__file__).resolve().parents[3]
    validator = Draft202012Validator(_schema(root, "legion_task.schema.json"))
    return [f"{'.'.join(str(p) for p in err.path) or '<root>'}: {err.message}" for err in validator.iter_errors(node)]


def build_task_graph(request: dict, *, profile: str) -> dict:
    profile = profile.upper()
    if profile not in _PROFILE_PARALLEL:
        raise ValueError(f"unknown profile: {profile}")
    if profile == "FAST":
        return {
            "request_id": request.get("request_id"),
            "profile": profile,
            "max_parallel": 0,
            "routing_authority": False,
            "nodes": [],
        }

    domain = request.get("domain", "core")
    raw_nodes = request.get("subtasks")
    if raw_nodes is None:
        raw_nodes = [{
            "task_id": f"{request.get('request_id', 'request')}-primary",
            "role": "specialist",
            "depends_on": [],
            "read_set": [],
            "write_set": [],
            "permission_ceiling": "read_only",
            "risk_class": "A",
            "required_capabilities": ["text_reasoning"],
            "verification": "checker",
        }]

    nodes: list[dict] = []
    ids: set[str] = set()
    for raw in raw_nodes:
        node = copy.deepcopy(raw)
        node.setdefault("domain", domain)
        errors = _validate_task_node(node)
        if errors:
            raise ValueError("invalid task node: " + "; ".join(errors))
        task_id = node["task_id"]
        if task_id in ids:
            raise ValueError(f"duplicate task_id: {task_id}")
        ids.add(task_id)
        nodes.append(node)

    for node in nodes:
        missing = set(node["depends_on"]) - ids
        if missing:
            raise ValueError(f"unknown dependencies for {node['task_id']}: {sorted(missing)}")
        if node["task_id"] in node["depends_on"]:
            raise ValueError(f"self dependency forbidden: {node['task_id']}")

    return {
        "request_id": request.get("request_id"),
        "profile": profile,
        "max_parallel": _PROFILE_PARALLEL[profile],
        "routing_authority": False,
        "reasoning_authority": False,
        "nodes": nodes,
    }


def ready_nodes(graph: dict, completed: set[str]) -> list[dict]:
    ready: list[dict] = []
    for node in graph.get("nodes", []):
        if node.get("task_id") in completed:
            continue
        if set(node.get("depends_on", [])).issubset(completed):
            ready.append(copy.deepcopy(node))
    return ready[: int(graph.get("max_parallel", 0))]


def assign_agents(graph: dict, agents: list[dict], *, profile: str) -> dict:
    profile = profile.upper()
    max_parallel = _PROFILE_PARALLEL.get(profile)
    if max_parallel is None:
        raise ValueError(f"unknown profile: {profile}")
    result = copy.deepcopy(graph)
    result["max_parallel"] = min(int(result.get("max_parallel", max_parallel)), max_parallel)
    result["routing_authority"] = False
    result["reasoning_authority"] = False
    safe_agents = [
        a for a in agents
        if a.get("routing_authority") is False and a.get("reasoning_authority") is False
    ]
    if result["nodes"] and not safe_agents:
        raise ValueError("no non-authoritative agents available")

    for index, node in enumerate(result.get("nodes", [])):
        domain = node.get("domain", "core")
        candidates = [a for a in safe_agents if domain in a.get("domains", [])]
        if not candidates:
            raise ValueError(f"no eligible agent for domain {domain}")
        node["assigned_agent"] = candidates[index % len(candidates)]["agent_id"]
    return result


def validate_artifact_ownership(graph: dict) -> list[str]:
    owners: dict[str, list[dict]] = {}
    for node in graph.get("nodes", []):
        for artifact in node.get("write_set", []):
            owners.setdefault(artifact, []).append(node)

    errors: list[str] = []
    for artifact, writers in sorted(owners.items()):
        if len(writers) <= 1:
            continue
        integrators = [writer for writer in writers if writer.get("role") == "integrator"]
        non_integrators = [writer for writer in writers if writer.get("role") != "integrator"]
        allowed = False
        if len(integrators) == 1:
            deps = set(integrators[0].get("depends_on", []))
            allowed = all(writer.get("task_id") in deps for writer in non_integrators)
        if not allowed:
            ids = [writer.get("task_id") for writer in writers]
            errors.append(f"artifact {artifact} has conflicting writers: {ids}")
    return errors
