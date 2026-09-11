from __future__ import annotations

from typing import Callable, Mapping

AdapterFactory = Callable[[object, Mapping[str, str]], object]


def _taskbounty_factory(source_cfg, env):
    from .adapters.taskbounty import TaskBountyAdapter

    return TaskBountyAdapter(
        source_cfg,
        api_key=env.get("TASKBOUNTY_API_KEY"),
    )


def build_adapters(
    config,
    env: Mapping[str, str],
    factories: Mapping[str, AdapterFactory] | None = None,
) -> dict[str, object]:
    registry: dict[str, AdapterFactory] = {
        "taskbounty": _taskbounty_factory,
    }
    if factories:
        registry.update(factories)

    adapters: dict[str, object] = {}
    for name, source_cfg in config.sources.items():
        if not source_cfg.enabled:
            continue
        factory = registry.get(name)
        if factory is None:
            continue
        adapters[name] = factory(source_cfg, env)
    return adapters
