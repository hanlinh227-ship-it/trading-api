from __future__ import annotations

import asyncio
import json
import os
import shlex
from pathlib import Path

import typer

from .adapter_registry import build_adapters
from .config import load_runtime_config
from .integration import missing_secrets
from .opportunity_pool import RepositoryOpportunityPool
from .orchestrator import RevenueOrchestrator
from .repository import StackHubRepository
from .runtime_status import build_status, status_dict
from .scout import Scout
from .solvers.command import CommandSolver
from .telemetry import redact

app = typer.Typer(help="STACKHUB V2 continuous multi-source revenue runtime")


def _repo(path: Path) -> StackHubRepository:
    repo = StackHubRepository(path)
    repo.initialize()
    return repo


def _allowed_claim_diagnostics(repo: StackHubRepository) -> tuple[dict[str, int], list[dict[str, object]]]:
    count_rows = repo.conn.execute(
        """SELECT c.state, COUNT(*) AS n
        FROM claims c
        JOIN opportunities o ON o.source=c.source AND o.id=c.opportunity_id
        WHERE o.policy_allowed=1
        GROUP BY c.state
        ORDER BY c.state"""
    ).fetchall()
    counts = {str(row["state"]): int(row["n"]) for row in count_rows}
    blocked_rows = repo.conn.execute(
        """SELECT c.source, c.opportunity_id, c.state, c.last_error_code
        FROM claims c
        JOIN opportunities o ON o.source=c.source AND o.id=c.opportunity_id
        WHERE o.policy_allowed=1
          AND c.state IN ('FAILED_PERMANENT','REJECTED','SUBMITTED','PAID')
        ORDER BY c.id DESC
        LIMIT 20"""
    ).fetchall()
    blocked = [dict(row) for row in blocked_rows]
    return counts, blocked


async def _close_adapters(adapters: dict[str, object]) -> None:
    for adapter in adapters.values():
        closer = getattr(adapter, "aclose", None)
        if closer is not None:
            await closer()


async def _scan_cycle(cfg, repo, adapters) -> list[dict[str, object]]:
    pool = RepositoryOpportunityPool(cfg, repo)
    scouts = [Scout(adapter, pool) for adapter in adapters.values()]
    if not scouts:
        return []
    results = await asyncio.gather(*(scout.run_once() for scout in scouts))
    return [result.__dict__ for result in results]


def _solver_map_from_env() -> dict[str, object]:
    raw = os.getenv("STACKHUB_SOLVER_COMMAND", "").strip()
    if not raw:
        return {}
    command = shlex.split(raw)
    solver = CommandSolver(command)
    return {
        "coding": solver,
        "research": solver,
        "data": solver,
        "service": solver,
        "content": solver,
    }


@app.command("doctor")
def doctor(
    config: Path = typer.Option(Path("config/sources.yaml"), "--config"),
) -> None:
    cfg = load_runtime_config(config)
    adapters = build_adapters(cfg, os.environ)
    enabled = sorted(name for name, item in cfg.sources.items() if item.enabled)
    loaded = sorted(adapters)
    report = {
        "config_ok": True,
        "dry_run": cfg.dry_run,
        "worker_enabled": cfg.worker_enabled,
        "zero_external_spend": str(cfg.external_spend_limit_usd) == "0",
        "enabled_sources": enabled,
        "loaded_adapters": loaded,
        "unloaded_sources": sorted(set(enabled) - set(loaded)),
        "missing_secrets": list(missing_secrets(cfg, os.environ)),
        "solver_bridge_configured": bool(os.getenv("STACKHUB_SOLVER_COMMAND", "").strip()),
    }
    typer.echo(json.dumps(redact(report), sort_keys=True, default=str))


@app.command("status")
def status(
    db: Path = typer.Option(Path("runtime-data/stackhub-v2.db"), "--db"),
    config: Path = typer.Option(Path("config/sources.yaml"), "--config"),
) -> None:
    cfg = load_runtime_config(config)
    repo = _repo(db)
    try:
        dry_run = cfg.dry_run or not cfg.worker_enabled
        mode = "DRY-RUN" if dry_run else "LIVE-CANDIDATE"
        mutation_status = "claims/submissions disabled" if dry_run else "capability-gated"
        allowed_claim_state_counts, blocked_allowed_claims = _allowed_claim_diagnostics(repo)
        report = {
            "mode": mode,
            "mutation_status": mutation_status,
            "allowed_claim_state_counts": allowed_claim_state_counts,
            "blocked_allowed_claims": blocked_allowed_claims,
            **status_dict(build_status(repo)),
        }
        typer.echo(json.dumps(redact(report), sort_keys=True, default=str))
    finally:
        repo.close()


@app.command("opportunities")
def opportunities(
    db: Path = typer.Option(Path("runtime-data/stackhub-v2.db"), "--db"),
    limit: int = typer.Option(20, "--limit", min=1, max=100),
) -> None:
    repo = _repo(db)
    try:
        for row in repo.list_ranked_opportunities(limit=limit):
            safe = {
                "source": row["source"],
                "id": row["id"],
                "url": row["url"],
                "reward": f"{row['reward_amount']} {row['reward_asset']}",
                "policy_allowed": bool(row["policy_allowed"]),
                "score_usd_per_minute": row["score_usd_per_minute"],
            }
            typer.echo(json.dumps(redact(safe), sort_keys=True))
    finally:
        repo.close()


@app.command("scan-once")
def scan_once(
    config: Path = typer.Option(Path("config/sources.yaml"), "--config"),
    db: Path = typer.Option(Path("runtime-data/stackhub-v2.db"), "--db"),
) -> None:
    cfg = load_runtime_config(config)
    repo = _repo(db)
    adapters = build_adapters(cfg, os.environ)

    async def _run() -> None:
        try:
            result = await _scan_cycle(cfg, repo, adapters)
            typer.echo(json.dumps(redact(result), sort_keys=True, default=str))
        finally:
            await _close_adapters(adapters)

    try:
        asyncio.run(_run())
    finally:
        repo.close()


@app.command("orchestrate-once")
def orchestrate_once(
    config: Path = typer.Option(Path("config/sources.live.example.yaml"), "--config"),
    db: Path = typer.Option(Path("runtime-data/stackhub-v2.db"), "--db"),
) -> None:
    cfg = load_runtime_config(config)
    if not cfg.worker_enabled or cfg.dry_run:
        raise typer.BadParameter("orchestrate-once requires worker_enabled=true and dry_run=false")
    solvers = _solver_map_from_env()
    if not solvers:
        raise typer.BadParameter("STACKHUB_SOLVER_COMMAND is required for automatic solving")
    repo = _repo(db)
    adapters = build_adapters(cfg, os.environ)

    async def _run() -> None:
        try:
            await _scan_cycle(cfg, repo, adapters)
            result = await RevenueOrchestrator(
                repo,
                adapters,
                solvers,
                max_active_claims=cfg.max_active_claims,
            ).run_batch()
            typer.echo(json.dumps(redact(result), sort_keys=True, default=str))
        finally:
            await _close_adapters(adapters)

    try:
        asyncio.run(_run())
    finally:
        repo.close()


@app.command("run")
def run(
    config: Path = typer.Option(Path("config/sources.yaml"), "--config"),
    db: Path = typer.Option(Path("runtime-data/stackhub-v2.db"), "--db"),
) -> None:
    cfg = load_runtime_config(config)
    repo = _repo(db)
    adapters = build_adapters(cfg, os.environ)
    solvers = _solver_map_from_env()

    async def _run() -> None:
        try:
            while True:
                await _scan_cycle(cfg, repo, adapters)
                if cfg.worker_enabled:
                    if not solvers:
                        raise RuntimeError("STACKHUB_SOLVER_COMMAND is required when worker_enabled=true")
                    await RevenueOrchestrator(
                        repo,
                        adapters,
                        solvers,
                        max_active_claims=cfg.max_active_claims,
                    ).run_batch()
                await asyncio.sleep(cfg.scan_interval_seconds)
        finally:
            await _close_adapters(adapters)

    try:
        asyncio.run(_run())
    finally:
        repo.close()


if __name__ == "__main__":
    app()
