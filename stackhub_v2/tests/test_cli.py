from typer.testing import CliRunner
from stackhub.cli import app


def test_status_command_is_dry_run_and_handles_missing_db(tmp_path):
    runner = CliRunner()
    result = runner.invoke(app, ["status", "--db", str(tmp_path / "missing.db")])
    assert result.exit_code == 0
    assert "DRY-RUN" in result.stdout
    assert "claims/submissions disabled" in result.stdout
