from pathlib import Path


def test_windows_setup_uses_powershell5_compatible_rng():
    script = Path("money_ecosystem/worker/setup_windows.ps1").read_text(encoding="utf-8")
    assert "RandomNumberGenerator]::Fill" not in script
    assert "RandomNumberGenerator]::Create()" in script
    assert ".GetBytes($bytes)" in script
    assert ".Dispose()" in script
