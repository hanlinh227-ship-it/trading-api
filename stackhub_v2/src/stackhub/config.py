from __future__ import annotations

from decimal import Decimal
from pathlib import Path
from urllib.parse import urlparse

import yaml
from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


class SourceConfig(BaseModel):
    model_config = ConfigDict(frozen=True)

    enabled: bool
    base_url: str
    agent_native: bool
    read_only: bool
    request_timeout_seconds: int = Field(gt=0)
    min_poll_interval_seconds: int = Field(ge=60)

    @field_validator("base_url")
    @classmethod
    def validate_base_url(cls, value: str) -> str:
        parsed = urlparse(value)
        if parsed.scheme != "https" or not parsed.hostname:
            raise ValueError("base_url must use https and include a hostname")
        return value.rstrip("/")


class RuntimeConfig(BaseModel):
    model_config = ConfigDict(frozen=True)

    dry_run: bool = True
    external_spend_limit_usd: Decimal = Decimal("0")
    scan_interval_seconds: int = Field(ge=60)
    max_concurrent_tasks: int = Field(ge=1)
    sources: dict[str, SourceConfig]

    @model_validator(mode="after")
    def enforce_read_only_guardrails(self) -> "RuntimeConfig":
        if self.dry_run is not True:
            raise ValueError("STACKHUB V2 Plan 1 requires dry_run=true")
        if self.external_spend_limit_usd != Decimal("0"):
            raise ValueError("STACKHUB V2 Plan 1 requires zero external spend")

        taskbounty = self.sources.get("taskbounty")
        if taskbounty is not None:
            parsed = urlparse(taskbounty.base_url)
            if parsed.hostname != "www.task-bounty.com":
                raise ValueError("TaskBounty hostname must be exactly www.task-bounty.com")
            if taskbounty.read_only is not True:
                raise ValueError("TaskBounty must remain read-only in Plan 1")
        return self


def load_runtime_config(path: Path) -> RuntimeConfig:
    data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    runtime_data = dict(data.get("runtime") or {})
    runtime_data["sources"] = data.get("sources") or {}
    return RuntimeConfig.model_validate(runtime_data)
