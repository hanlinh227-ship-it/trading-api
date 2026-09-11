import sqlite3
import sys
from decimal import Decimal

import pytest

from stackhub.adapter_registry import build_adapters
from stackhub.integration import missing_secrets
from stackhub.models import Opportunity, Reward
from stackhub.runtime_status import build_status
from stackhub.solvers.command import CommandSolver, sanitized_solver_env


class Cfg:
    def __init__(self, enabled=True):
        self.enabled = enabled


class Runtime:
    sources = {"taskbounty": Cfg(True), "custom": Cfg(True)}


def test_missing_secrets_does_not_require_paypal_password():
    assert missing_secrets(Runtime(), {}) == ("TASKBOUNTY_API_KEY",)
    assert missing_secrets(
        Runtime(),
        {"TASKBOUNTY_API_KEY": "x"},
    ) == ()


def test_adapter_registry_accepts_plug_in_factories():
    adapters = build_adapters(
        Runtime(),
        {},
        factories={
            "taskbounty": lambda cfg, env: "TB",
            "custom": lambda cfg, env: "CUSTOM",
        },
    )
    assert adapters["custom"] == "CUSTOM"


def test_solver_environment_redacts_marketplace_credentials():
    env = sanitized_solver_env(
        {
            "PATH": "/bin",
            "TASKBOUNTY_API_KEY": "secret",
            "OTHER_TOKEN": "secret2",
            "HOME": "/tmp",
        }
    )
    assert env == {"PATH": "/bin", "HOME": "/tmp"}


@pytest.mark.asyncio
async def test_command_solver_json_bridge():
    code = (
        'import json,sys; json.load(sys.stdin); '
        'print(json.dumps({"artifact_reference":"https://artifact/1",'
        '"evidence":{"ok":True}}))'
    )
    solver = CommandSolver(
        (sys.executable, "-c", code),
        env={"PATH": "/usr/bin:/bin"},
    )
    opportunity = Opportunity(
        id="1",
        source="x",
        url="https://x",
        category="coding",
        reward=Reward(amount=Decimal("1"), asset="USD"),
        competition_model="best",
        agent_allowed=True,
    )

    result = await solver.solve(opportunity, "workspace")

    assert result.artifact.reference == "https://artifact/1"
    assert result.evidence["ok"] is True


class Repo:
    def __init__(self):
        self.conn = sqlite3.connect(":memory:")
        self.conn.row_factory = sqlite3.Row
        self.conn.executescript(
            """
            CREATE TABLE opportunities(id TEXT);
            CREATE TABLE claims(state TEXT);
            CREATE TABLE source_health(
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                source TEXT,
                ok INTEGER,
                status_code INTEGER,
                error_code TEXT,
                observed_at TEXT
            );
            """
        )
        self.conn.execute("INSERT INTO opportunities VALUES('1')")
        self.conn.execute("INSERT INTO claims VALUES('SUBMITTED')")
        self.conn.execute(
            """
            INSERT INTO source_health(source,ok,status_code,error_code,observed_at)
            VALUES('x',1,200,NULL,'2026-09-11T00:00:00+00:00')
            """
        )
        self.conn.commit()


def test_status_is_truthful_and_does_not_invent_revenue():
    status = build_status(Repo())
    assert status.opportunities == 1
    assert status.payout_pending == 1
    assert status.paid_today_usd == 0


def test_failed_retryable_claim_is_not_reported_as_active():
    repo = Repo()
    repo.conn.execute("DELETE FROM claims")
    repo.conn.execute("INSERT INTO claims VALUES('FAILED_RETRYABLE')")
    repo.conn.commit()

    status = build_status(repo)

    assert status.active_claims == 0
    assert status.payout_pending == 0
