$ErrorActionPreference = 'Stop'
$AppHome = $env:MT5_APP_HOME
if ([string]::IsNullOrWhiteSpace($AppHome)) { $AppHome = 'C:\Trading\MT5Forex' }
$RuntimeFile = Join-Path $AppHome 'runtime.json'
if (-not (Test-Path $RuntimeFile)) { throw 'runtime.json missing; run install-native-mt5.ps1 first' }
$r = Get-Content $RuntimeFile -Raw | ConvertFrom-Json
if (-not (Test-Path $r.terminalPath)) { throw 'terminal64.exe missing' }

# Native Windows MT5 owns broker authentication. We deliberately do not pass
# Login/Password/Server on every launch. MT5 reconnects using the account DB
# created by the normal broker login flow and protected by the same Windows user.
$existing = Get-Process terminal64 -ErrorAction SilentlyContinue
if ($existing) {
  Write-Output 'MT5_WINDOWS_NATIVE_ALREADY_RUNNING=PASS'
  exit 0
}

$args = @("/config:$($r.startConfig)")
Start-Process -FilePath $r.terminalPath -ArgumentList $args -WorkingDirectory $r.terminalDir | Out-Null
$deadline = (Get-Date).AddSeconds(60)
do {
  Start-Sleep -Seconds 2
  $p = Get-Process terminal64 -ErrorAction SilentlyContinue
} while (-not $p -and (Get-Date) -lt $deadline)
if (-not $p) { throw 'Native MT5 terminal did not start' }
Write-Output 'MT5_WINDOWS_NATIVE_PROCESS=PASS'
Write-Output 'MT5_WINDOWS_AUTH_MODE=PERSISTENT_ACCOUNT_DATABASE'
