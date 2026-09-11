from __future__ import annotations

from decimal import Decimal
from pathlib import Path
from urllib.parse import urlparse

import yaml
from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from .source_capabilities import SourceCapabilities


class SourceConfig(BaseModel):
    model_config = ConfigDict(frozen=True)

    enabled: bool
    base_url: str
    agent_native: bool
    read_only: bool
    request_timeout_seconds: int = Field(gt=0)
    min_poll_interval_seconds: int = Field(ge=60)
    capabilities: SourceCapabilities = Field(default_factory=SourceCapabilities)

    @field_validator("base_url")
    @classmethod
    def validate_base_url(cls, value: str) -> str:
        parsed = urlparse(value)
        if parsed.scheme != "https" or not parsed.hostname:
            raise ValueError("base_url must use https and include a hostname")
        return value.rstrip("/")


class WorkerPoolConfig(BaseModel):
    model_config = ConfigDict(frozen=True)

    scouts: int = Field(default=3, ge=1, le=3)
    code_fix: int = Field(default=2, ge=1, le=2)
    research_data: int = Field(default=2, ge=0, le=2)
    service: int = Field(default=2, ge=0, le=2)
    verification: int = Field(default=2, ge=1, le=2)
    submission: int = Field(default=1, ge=1, le=1)


class RuntimeConfig(BaseModel):
    model_config = ConfigDict(frozen=True)

    dry_run: bool = True
    worker_enabled: bool = False
    external_spend_limit_usd: Decimal = Decimal("0")
    scan_interval_seconds: int = Field(ge=60)
    max_concurrent_tasks: int = Field(ge=1)
    max_active_claims: int = Field(default=1, ge=1, le=4)
    opportunity_allowlist: tuple[str, ...] = ()
    worker_pools: WorkerPoolConfig = Field(default_factory=WorkerPoolConfig)
    sources: dict[str, SourceConfig]

    @field_validator("opportunity_allowlist")
    @classmethod
    def normalize_opportunity_allowlist(cls, value: tuple[str, ...]) -> tuple[str, ...]:
        return tuple(dict.fromkeys(item.strip() for item in value if item.strip()))

    @model_validator(mode="after")
    def enforce_guardrails(self) -> "RuntimeConfig":
        if self.external_spend_limit_usd != Decimal("0"):
            raise ValueError("STACKHUB V2 requires zero external spend")

        taskbounty = self.sources.get("taskbounty")
        if taskbounty is not None:
            parsed = urlparse(taskbounty.base_url)
            if parsed.hostname != "www.task-bounty.com":
                raise ValueError("TaskBounty hostname must be exactly www.task-bounty.com")

        if self.worker_enabled:
            if self.dry_run:
                raise ValueError("worker_enabled=true requires dry_run=false")
            mutable_sources = [
                source
                for source in self.sources.values()
                if source.enabled and not source.read_only
            ]
            if not mutable_sources:
                raise ValueError("worker_enabled=true requires at least one enabled mutable source")
        else:
            if self.dry_run is not True:
                raise ValueError("dry_run=false requires worker_enabled=true")
            if any(source.enabled and not source.read_only for source in self.sources.values()):
                raise ValueError("all enabled sources must remain read-only when worker is disabled")

        return self


def load_runtime_config(path: Path) -> RuntimeConfig:
    data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    runtime_data = dict(data.get("runtime") or {})
    runtime_data["sources"] = data.get("sources") or {}
    return RuntimeConfig.model_validate(runtime_data)
