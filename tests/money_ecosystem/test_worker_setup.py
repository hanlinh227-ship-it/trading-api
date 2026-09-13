from pathlib import Path


def test_windows_setup_uses_powershell5_compatible_rng():
    script = Path("money_ecosystem/worker/setup_windows.ps1").read_text(encoding="utf-8")
    assert "RandomNumberGenerator]::Fill" not in script
    assert "RandomNumberGenerator]::Create()" in script
    assert ".GetBytes($bytes)" in script
    assert ".Dispose()" in script


def test_windows_start_script_has_watchdog_restart_loop():
    script = Path("money_ecosystem/worker/setup_windows.ps1").read_text(encoding="utf-8")
    assert "while (`$true)" in script
    assert "Worker exited unexpectedly" in script
    assert "Start-Sleep -Seconds 3" in script
    assert "-1073741510" in script
