from __future__ import annotations

from decimal import Decimal
from pathlib import Path
from urllib.parse import urlparse

import yaml
from pydantic import BaseModel, Field


class SourceConfig(BaseModel):
    enabled: bool
    base_url: str
    agent_native: bool
    read_only: bool
    request_timeout_seconds: int = Field(gt=0, le=120)
    min_poll_interval_seconds: int = Field(ge=60)


class RuntimeConfig(BaseModel):
    dry_run: bool = True
    external_spend_limit_usd: Decimal = Decimal("0")
    scan_interval_seconds: int = Field(ge=60)
    max_concurrent_tasks: int = Field(ge=1, le=8)
    sources: dict[str, SourceConfig]


def load_runtime_config(path: Path) -> RuntimeConfig:
    raw = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    runtime_raw = dict(raw.get("runtime") or {})
    runtime_raw["sources"] = raw.get("sources") or {}
    cfg = RuntimeConfig.model_validate(runtime_raw)

    if not cfg.dry_run:
        raise ValueError("STACKHUB V2 Plan 1 requires dry_run=true")
    if cfg.external_spend_limit_usd != Decimal("0"):
        raise ValueError("STACKHUB V2 Plan 1 requires external spend limit 0")

    taskbounty = cfg.sources.get("taskbounty")
    if taskbounty:
        if not taskbounty.read_only:
            raise ValueError("TaskBounty must remain read-only in Plan 1")
        parsed = urlparse(taskbounty.base_url)
        if parsed.scheme != "https" or parsed.hostname != "www.task-bounty.com":
            raise ValueError("TaskBounty base URL must use https://www.task-bounty.com")
    return cfg
