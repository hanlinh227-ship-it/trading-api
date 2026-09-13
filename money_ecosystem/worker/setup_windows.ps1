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
        git pull --ff-only origin $Branch
        if ($LASTEXITCODE -ne 0) { throw "git pull failed" }
    } finally {
        Pop-Location
    }
}

if (-not (Test-Path $SecretFile)) {
    $bytes = New-Object byte[] 48
    [System.Security.Cryptography.RandomNumberGenerator]::Fill($bytes)
    $secret = [Convert]::ToBase64String($bytes)
    [System.IO.File]::WriteAllText($SecretFile, $secret, [System.Text.Encoding]::UTF8)
    Write-Host "Created local pairing secret." -ForegroundColor Green
} else {
    Write-Host "Existing local pairing secret kept unchanged." -ForegroundColor Green
}

$startContent = @"
`$ErrorActionPreference = "Stop"
Set-Location "$RepoRoot"
& "$PythonExe" -m money_ecosystem.worker.runner --repo-root "$RepoRoot" --secret-file "$SecretFile" --branch "$Branch" --poll-seconds 15
"@
[System.IO.File]::WriteAllText($StartScript, $startContent, [System.Text.Encoding]::UTF8)

Write-Host ""
Write-Host "Setup complete." -ForegroundColor Green
Write-Host "Local secret file: $SecretFile"
Write-Host "Start command: powershell -ExecutionPolicy Bypass -File `"$StartScript`""
Write-Host ""
Write-Host "NEXT: add the exact contents of worker_secret.txt to the GitHub Actions repository secret CURIOUS_WORKER_HMAC_KEY." -ForegroundColor Yellow
Write-Host "Do not paste the secret into ChatGPT and do not commit it to GitHub." -ForegroundColor Yellow
