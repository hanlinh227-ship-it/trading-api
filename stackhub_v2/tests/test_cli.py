from typer.testing import CliRunner
from stackhub.cli import app


def test_status_command_is_dry_run_and_handles_missing_db(tmp_path):
    runner = CliRunner()
    result = runner.invoke(app, ["status", "--db", str(tmp_path / "missing.db")])
    assert result.exit_code == 0
    assert "DRY-RUN" in result.stdout
    assert "claims/submissions disabled" in result.stdout


def test_mutating_commands_are_not_exposed():
    runner = CliRunner()
    for command in ("claim", "submit", "withdraw", "payout", "spend"):
        result = runner.invoke(app, [command])
        assert result.exit_code != 0, command


def test_live_flag_is_not_exposed():
    runner = CliRunner()
    result = runner.invoke(app, ["status", "--live"])
    assert result.exit_code != 0
