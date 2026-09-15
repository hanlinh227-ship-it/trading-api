from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import yaml
from jsonschema import Draft202012Validator


_PERMISSION_RANK = {"read_only": 0, "bounded_write": 1, "sandbox_execute": 2}
_RISK_RANK = {"A": 0, "B": 1, "C": 2, "D": 3}
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
