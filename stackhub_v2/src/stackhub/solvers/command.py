from __future__ import annotations

import asyncio
import json
import os
from collections.abc import Mapping, Sequence

from ..models import Opportunity
from .base import Artifact, SolverResult

_BLOCKED_ENV_PARTS = (
    "API_KEY",
    "TOKEN",
    "SECRET",
    "PASSWORD",
    "PRIVATE_KEY",
    "SEED",
    "MNEMONIC",
)


def sanitized_solver_env(
    source: Mapping[str, str] | None = None,
) -> dict[str, str]:
    source = dict(source or os.environ)
    output: dict[str, str] = {}
    for key, value in source.items():
        upper = key.upper()
        if any(part in upper for part in _BLOCKED_ENV_PARTS):
            continue
        output[key] = value
    return output


class CommandSolver:
    """JSON bridge for an authorized local/CLI AI solver; no shell and no secrets."""

    def __init__(
        self,
        command: Sequence[str],
        *,
        timeout_seconds: int = 900,
        env: Mapping[str, str] | None = None,
    ):
        if not command:
            raise ValueError("solver command is required")
        self.command = tuple(command)
        self.timeout_seconds = max(1, int(timeout_seconds))
        self.env = sanitized_solver_env(env)

    async def solve(
        self,
        opportunity: Opportunity,
        workspace_reference: str,
    ) -> SolverResult:
        payload = {
            "opportunity": opportunity.model_dump(mode="json"),
            "workspace_reference": workspace_reference,
        }
        process = await asyncio.create_subprocess_exec(
            *self.command,
            stdin=asyncio.subprocess.PIPE,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            env=self.env,
        )
        try:
            stdout, stderr = await asyncio.wait_for(
                process.communicate(json.dumps(payload).encode()),
                timeout=self.timeout_seconds,
            )
        except asyncio.TimeoutError:
            process.kill()
            await process.wait()
            raise RuntimeError("solver_timeout")

        if process.returncode != 0:
            stderr_tail = stderr.decode(errors="replace")[-1000:]
            raise RuntimeError(
                f"solver_exit_{process.returncode}:{stderr_tail}"
            )
        try:
            data = json.loads(stdout.decode())
        except Exception as exc:
            raise RuntimeError("solver_invalid_json") from exc

        reference = str(data.get("artifact_reference") or "").strip()
        evidence = data.get("evidence") or {}
        if not isinstance(evidence, dict):
            raise RuntimeError("solver_invalid_evidence")
        return SolverResult(
            Artifact(
                reference,
                kind=str(data.get("artifact_kind") or "generic"),
                metadata=dict(data.get("metadata") or {}),
            ),
            evidence,
        )
