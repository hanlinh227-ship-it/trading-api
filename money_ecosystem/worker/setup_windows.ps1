param(
    [string]$Root = "C:\AI\CuriousBeyond",
    [string]$Branch = "ai-money-ecosystem-autopilot-v1"
)

$ErrorActionPreference = "Stop"
$RepoUrl = "https://github.com/hanlinh227-ship-it/trading-api.git"
$RepoRoot = Join-Path $Root "repo"
$SecretFile = Join-Path $Root "worker_secret.txt"
$PythonExe = Join-Path $Root "venv\Scripts\python.exe"
$StartScript = Join-Path $Root "start_worker.ps1"
$Utf8NoBom = New-Object System.Text.UTF8Encoding($false)

Write-Host "=== Curious Beyond Worker Setup ===" -ForegroundColor Cyan

if (-not (Test-Path $Root)) {
    New-Item -ItemType Directory -Force -Path $Root | Out-Null
}

if (-not (Test-Path $PythonExe)) {
    throw "Python venv not found at $PythonExe. Create the Python 3.11 venv first."
}

if (-not (Get-Command git -ErrorAction SilentlyContinue)) {
    throw "Git is not available in PATH."
}

if (-not (Test-Path (Join-Path $RepoRoot ".git"))) {
    Write-Host "Cloning project branch..." -ForegroundColor Yellow
    git clone --branch $Branch --single-branch $RepoUrl $RepoRoot
    if ($LASTEXITCODE -ne 0) { throw "git clone failed" }
} else {
    Write-Host "Updating existing project checkout..." -ForegroundColor Yellow
    Push-Location $RepoRoot
    try {
        git fetch origin $Branch
        if ($LASTEXITCODE -ne 0) { throw "git fetch failed" }
        git checkout $Branch
        if ($LASTEXITCODE -ne 0) { throw "git checkout failed" }
        git pull --rebase origin $Branch
        if ($LASTEXITCODE -ne 0) { throw "git pull --rebase failed" }
    } finally {
        Pop-Location
    }
}

Push-Location $RepoRoot
try {
    git config user.name "Curious Beyond Worker"
    if ($LASTEXITCODE -ne 0) { throw "git config user.name failed" }
    git config user.email "curious-beyond-worker@users.noreply.github.com"
    if ($LASTEXITCODE -ne 0) { throw "git config user.email failed" }
} finally {
    Pop-Location
}

$DriveRequirements = Join-Path $RepoRoot "money_ecosystem\render_gateway\requirements-drive.txt"
if (Test-Path $DriveRequirements) {
    Write-Host "Installing/updating free Render Gateway Drive dependencies..." -ForegroundColor Yellow
    & $PythonExe -m pip install --disable-pip-version-check -r $DriveRequirements
    if ($LASTEXITCODE -ne 0) { throw "Render Gateway Drive dependency install failed" }
}

if (-not (Test-Path $SecretFile)) {
    $bytes = New-Object byte[] 48
    $rng = [System.Security.Cryptography.RandomNumberGenerator]::Create()
    try {
        $rng.GetBytes($bytes)
    } finally {
        $rng.Dispose()
    }
    $secret = [Convert]::ToBase64String($bytes)
    [System.IO.File]::WriteAllText($SecretFile, $secret, $Utf8NoBom)
    Write-Host "Created local pairing secret." -ForegroundColor Green
} else {
    Write-Host "Existing local pairing secret kept unchanged." -ForegroundColor Green
}

$startContent = @"
`$ErrorActionPreference = "Continue"
Set-Location "$RepoRoot"
while (`$true) {
    & "$PythonExe" -m money_ecosystem.worker.runner_v2 --repo-root "$RepoRoot" --secret-file "$SecretFile" --branch "$Branch" --poll-seconds 15
    `$exitCode = `$LASTEXITCODE
    if (`$exitCode -eq -1073741510 -or `$exitCode -eq 130) {
        Write-Host "Worker stopped by user." -ForegroundColor Yellow
        break
    }
    Write-Host "Worker exited unexpectedly with code `$exitCode; restarting in 3 seconds..." -ForegroundColor Red
    Start-Sleep -Seconds 3
}
"@
[System.IO.File]::WriteAllText($StartScript, $startContent, $Utf8NoBom)

Write-Host ""
Write-Host "Setup complete." -ForegroundColor Green
Write-Host "Runtime: Render Gateway V2"
Write-Host "Local secret file: $SecretFile"
Write-Host "Start command: powershell -ExecutionPolicy Bypass -File `"$StartScript`""
Write-Host ""
Write-Host "Existing pairing secret is preserved. Do not paste it into ChatGPT or commit it to GitHub." -ForegroundColor Yellow
Write-Host "FLOW_GRADE remains fail-closed until an authenticated quality-provider connector is bound." -ForegroundColor Yellow