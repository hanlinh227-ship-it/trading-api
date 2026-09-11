import json

from typer.testing import CliRunner

from stackhub.cli import app
from stackhub.repository import StackHubRepository


def test_status_command_is_dry_run_and_handles_missing_db(tmp_path):
    runner = CliRunner()
    result = runner.invoke(app, ["status", "--db", str(tmp_path / "missing.db")])
    assert result.exit_code == 0
    assert "DRY-RUN" in result.stdout
    assert "claims/submissions disabled" in result.stdout


def test_status_exposes_safe_allowed_claim_blockers(tmp_path):
    db_path = tmp_path / "claims.db"
    repo = StackHubRepository(db_path)
    repo.initialize()
    repo.conn.execute(
        """
        INSERT INTO opportunities(
            source,id,url,category,reward_amount,reward_asset,
            requirements_json,acceptance_criteria_json,competition_model,
            policy_allowed,policy_reasons_json,score_usd_per_minute
        ) VALUES(?,?,?,?,?,?,?,?,?,?,?,?)
        """,
        (
            "taskforce",
            "tf-blocked",
            "https://example.invalid/task",
            "development",
            "1",
            "USDC",
            "[]",
            "[]",
            "application",
            1,
            "[]",
            "0.25",
        ),
    )
    repo.conn.execute(
        "INSERT INTO claims(source,opportunity_id,state,updated_at,last_error_code) VALUES(?,?,?,?,?)",
        (
            "taskforce",
            "tf-blocked",
            "FAILED_PERMANENT",
            "2026-09-11T20:00:00+00:00",
            "http_400",
        ),
    )
    repo.conn.commit()
    repo.close()

    runner = CliRunner()
    result = runner.invoke(app, ["status", "--db", str(db_path)])

    assert result.exit_code == 0
    report = json.loads(result.stdout)
    assert report["allowed_claim_state_counts"] == {"FAILED_PERMANENT": 1}
    assert report["blocked_allowed_claims"] == [
        {
            "source": "taskforce",
            "opportunity_id": "tf-blocked",
            "state": "FAILED_PERMANENT",
            "last_error_code": "http_400",
        }
    ]


def test_mutating_commands_are_not_exposed():
    runner = CliRunner()
    for command in ("claim", "submit", "withdraw", "payout", "spend"):
        result = runner.invoke(app, [command])
        assert result.exit_code != 0, command


def test_live_flag_is_not_exposed():
    runner = CliRunner()
    result = runner.invoke(app, ["status", "--live"])
    assert result.exit_code != 0
