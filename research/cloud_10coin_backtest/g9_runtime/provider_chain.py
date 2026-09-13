from __future__ import annotations

from copy import deepcopy
from datetime import datetime
from typing import Any, Iterable, Protocol


class MinuteStateProvider(Protocol):
    def fetch_minute_state(self, now: datetime) -> dict[str, Any]: ...


class FailoverMinuteProvider:
    """Ordered read-only provider chain. Never merges unlike market semantics."""

    def __init__(self, providers: Iterable[tuple[str, MinuteStateProvider]]):
        normalized = [(str(name), provider) for name, provider in providers if str(name)]
        if not normalized:
            raise ValueError("at least one minute provider is required")
        names = [name for name, _ in normalized]
        if len(set(names)) != len(names):
            raise ValueError("minute provider names must be unique")
        self.providers = tuple(normalized)

    def fetch_minute_state(self, now: datetime) -> dict[str, Any]:
        failures: list[dict[str, str]] = []
        for name, provider in self.providers:
            try:
                payload = provider.fetch_minute_state(now)
            except Exception as exc:
                failures.append({"provider": name, "error": f"{type(exc).__name__}:{exc}"})
                continue

            if not isinstance(payload, dict):
                failures.append({"provider": name, "error": "ValueError:provider payload must be object"})
                continue
            if payload.get("production_execution_authority") is not False:
                failures.append({"provider": name, "error": "ValueError:execution authority escalation forbidden"})
                continue
            if payload.get("research_only") is not True:
                failures.append({"provider": name, "error": "ValueError:research-only provider required"})
                continue

            selected = deepcopy(payload)
            selected["provider"] = str(selected.get("provider") or name)
            selected["provider_status"] = "PRIMARY" if not failures else "DEGRADED_FAILOVER"
            selected["provider_failures"] = list(failures)
            selected["research_only"] = True
            selected["production_execution_authority"] = False
            return selected

        detail = "; ".join(f"{row['provider']}={row['error']}" for row in failures)
        raise RuntimeError(f"all minute providers failed: {detail}")
