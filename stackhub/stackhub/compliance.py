from __future__ import annotations

from .models import AutomationClass, SourcePolicy


_VALID_ENVIRONMENTS = {"vps", "residential", "desktop"}


def can_auto_run(source: SourcePolicy, environment: str) -> tuple[bool, str]:
    env = environment.strip().lower()
    if env not in _VALID_ENVIRONMENTS:
        return False, f"Unknown environment: {environment}"

    if source.automation_class is AutomationClass.HUMAN_REQUIRED:
        return False, "Human-required work must never be auto-executed."

    if source.automation_class is AutomationClass.DISCOVERY_ONLY:
        return False, "Discovery-only source: STACKHUB may rank work but a human must execute it."

    if source.residential_only and env == "vps":
        return False, "This source requires a residential environment and is blocked on VPS/server infrastructure."

    if source.automation_class is AutomationClass.PASSIVE_ALLOWED:
        return True, "Passive background operation is permitted by STACKHUB policy for this environment."

    return False, "Automation class is not recognized."
