from __future__ import annotations

from dataclasses import dataclass
from typing import Mapping


@dataclass(frozen=True)
class SecretRequirement:
    source: str
    env_name: str
    required_for: str


_DEFAULT_REQUIREMENTS = {
    "taskbounty": (
        SecretRequirement(
            "taskbounty",
            "TASKBOUNTY_API_KEY",
            "authenticated API access",
        ),
    ),
}


def secret_requirements(config) -> tuple[SecretRequirement, ...]:
    out: list[SecretRequirement] = []
    for source_name, source_cfg in config.sources.items():
        if getattr(source_cfg, "enabled", False):
            out.extend(_DEFAULT_REQUIREMENTS.get(source_name, ()))
    return tuple(out)


def missing_secrets(
    config,
    env: Mapping[str, str],
) -> tuple[str, ...]:
    return tuple(
        requirement.env_name
        for requirement in secret_requirements(config)
        if not str(env.get(requirement.env_name, "")).strip()
    )
