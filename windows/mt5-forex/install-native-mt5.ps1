$ErrorActionPreference = 'Stop'

$AppHome = $env:MT5_APP_HOME
if ([string]::IsNullOrWhiteSpace($AppHome)) { $AppHome = 'C:\Trading\MT5Forex' }
$Repo = $env:FOREX_RESEARCH_REPO
if ([string]::IsNullOrWhiteSpace($Repo)) { $Repo = 'C:\Trading\trading-api-main' }
$Terminal = $env:MT5_TERMINAL_PATH
if ([string]::IsNullOrWhiteSpace($Terminal)) {
  $candidates = @(
    'C:\Program Files\MetaTrader 5\terminal64.exe',
    'C:\Program Files\The5ers MetaTrader 5\terminal64.exe',
    'C:\Program Files\Five Percent Online MT5\terminal64.exe'
  )
  $Terminal = $candidates | Where-Object { Test-Path $_ } | Select-Object -First 1
}
if (-not $Terminal -or -not (Test-Path $Terminal)) {
  throw 'Native Windows MT5 terminal not found. Install the The5ers/MetaTrader 5 Windows terminal first.'
}

$TerminalDir = Split-Path -Parent $Terminal
$originNeedle = [IO.Path]::GetFullPath($TerminalDir).TrimEnd('\').ToLowerInvariant()
$dataRoot = Join-Path $env:APPDATA 'MetaQuotes\Terminal'
$DataDir = $null
if (Test-Path $dataRoot) {
  Get-ChildItem $dataRoot -Directory -ErrorAction SilentlyContinue | ForEach-Object {
    $origin = Join-Path $_.FullName 'origin.txt'
    if (Test-Path $origin) {
      $text = (Get-Content $origin -Raw -ErrorAction SilentlyContinue).Trim().TrimEnd('\').ToLowerInvariant()
      if ($text -eq $originNeedle) { $script:DataDir = $_.FullName }
    }
  }
}
if (-not $DataDir) {
  throw "Could not resolve MT5 data directory for $TerminalDir. Start MT5 once under this Windows user, then rerun."
}

$EaSrc = Join-Path $Repo 'mt5\ForexAutoThe5ers.mq5'
if (-not (Test-Path $EaSrc)) { throw "EA source missing: $EaSrc" }
$Experts = Join-Path $DataDir 'MQL5\Experts'
$Presets = Join-Path $DataDir 'MQL5\Presets'
$Bridge = Join-Path $DataDir 'MQL5\Files\FOREX_BRIDGE'
$Config = Join-Path $DataDir 'Config'
New-Item -ItemType Directory -Force -Path $AppHome,$Experts,$Presets,$Bridge,$Config | Out-Null
Copy-Item $EaSrc (Join-Path $Experts 'ForexAutoThe5ers.mq5') -Force

$MetaEditor = Join-Path $TerminalDir 'metaeditor64.exe'
if (-not (Test-Path $MetaEditor)) { throw 'MetaEditor64.exe not found beside terminal64.exe' }
$CompileLog = Join-Path $AppHome 'metaeditor-compile.log'
$p = Start-Process -FilePath $MetaEditor -ArgumentList @("/compile:$($Experts)\ForexAutoThe5ers.mq5", "/log:$CompileLog") -PassThru -Wait
$Ex5 = Join-Path $Experts 'ForexAutoThe5ers.ex5'
if (-not (Test-Path $Ex5)) { throw 'EA compile did not produce ForexAutoThe5ers.ex5' }

$Preset = Join-Path $Presets 'ForexAutoThe5ers.set'
@"
InpHubUrl=$($env:MT5_HUB_URL)
InpBridgeToken=$($env:MT5_BRIDGE_TOKEN)
InpAllowLiveTrading=$($env:MT5_ALLOW_LIVE)
InpPulseSeconds=60
InpMaxRiskPct=1.00
InpMinFreeMarginPct=35.0
InpMinMarginLevelPct=300.0
InpMagic=560501
InpSymbols=EURUSD,GBPUSD,USDJPY,USDCHF,AUDUSD,NZDUSD,USDCAD,EURJPY,GBPJPY,EURGBP,XAUUSD
InpBreakEvenR=1.00
InpProfitLockR=1.35
InpTrailR=1.60
"@ | Set-Content -Path $Preset -Encoding ASCII

$StartConfig = Join-Path $AppHome 'mt5-startup.ini'
@"
[Experts]
Enabled=1
AllowLiveTrading=1
AllowDllImport=0

[StartUp]
Expert=ForexAutoThe5ers
ExpertParameters=ForexAutoThe5ers.set
Symbol=EURUSD
Period=M5
ShutdownTerminal=0
"@ | Set-Content -Path $StartConfig -Encoding ASCII

$runtime = @{
  terminalPath = $Terminal
  terminalDir = $TerminalDir
  dataDir = $DataDir
  bridgeDir = $Bridge
  startConfig = $StartConfig
  architecture = 'WINDOWS_NATIVE_MT5_EXECUTION'
}
$runtime | ConvertTo-Json | Set-Content (Join-Path $AppHome 'runtime.json') -Encoding UTF8
Write-Output 'MT5_WINDOWS_NATIVE_INSTALL=PASS'
Write-Output "MT5_WINDOWS_TERMINAL=$Terminal"
Write-Output "MT5_WINDOWS_DATA_DIR=$DataDir"
Write-Output 'MT5_WINDOWS_BROKER_SESSION=PRESERVE_EXISTING_ACCOUNT_DB'
