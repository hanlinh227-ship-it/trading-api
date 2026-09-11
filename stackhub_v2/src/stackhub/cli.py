from __future__ import annotations

import asyncio
import json
import os
from pathlib import Path

import typer

from .adapters.taskbounty import TaskBountyAdapter
from .config import load_runtime_config
from .repository import StackHubRepository
from .scanner import Scanner
from .telemetry import redact

app = typer.Typer(help="STACKHUB V2 read-only bounty scanner")


def _repo(path: Path) -> StackHubRepository:
    repo = StackHubRepository(path)
    repo.initialize()
    return repo


@app.command("status")
def status(db: Path = typer.Option(Path("runtime-data/stackhub-v2.db"), "--db")) -> None:
    repo = _repo(db)
    try:
        health = repo.get_source_health("taskbounty")
        count = len(repo.list_ranked_opportunities(limit=1000))
        typer.echo("STACKHUB V2 — DRY-RUN")
        typer.echo("claims/submissions disabled")
        typer.echo(f"opportunities={count}")
        typer.echo("taskbounty_health=" + json.dumps(redact(health or {"state": "unknown"}), default=str, sort_keys=True))
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
                "source": row["source"], "id": row["id"], "url": row["url"],
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
    source = cfg.sources["taskbounty"]
    repo = _repo(db)

    async def _run() -> None:
        adapter = TaskBountyAdapter(source, api_key=os.getenv("TASKBOUNTY_API_KEY"))
        try:
            result = await Scanner(cfg, repo, {"taskbounty": adapter}).run_once()
            typer.echo(json.dumps(redact(result.__dict__), sort_keys=True))
        finally:
            await adapter.aclose()

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
    source = cfg.sources["taskbounty"]
    repo = _repo(db)

    async def _run() -> None:
        adapter = TaskBountyAdapter(source, api_key=os.getenv("TASKBOUNTY_API_KEY"))
        try:
            await Scanner(cfg, repo, {"taskbounty": adapter}).run_forever()
        finally:
            await adapter.aclose()

    try:
        asyncio.run(_run())
    finally:
        repo.close()


if __name__ == "__main__":
    app()
