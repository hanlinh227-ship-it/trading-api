<#
.SYNOPSIS
    Bounded multi-AI engineering loop controller (AI_LOOP_V1).

.DESCRIPTION
    Connects CLAUDE CODE LOCAL + DEEPSEEK API + OPENAI CODEX GITHUB REVIEW + GITHUB +
    CLOUDFLARE VALIDATION into one bounded loop.

    The controller owns every git write operation (branch, commit, push, PR). Claude only
    edits files and runs tests, under a narrow --allowedTools list. The loop NEVER merges,
    NEVER deploys, and NEVER runs unbounded.

    Contract: docs/ai-coengineer/AI_LOOP_CONTRACT.md
    State schema: docs/ai-coengineer/AI_LOOP_STATE.schema.json

.EXAMPLE
    powershell -ExecutionPolicy Bypass -File .\scripts\ai\ai-loop.ps1 `
      -Task "Improve Forex/XAU/Index entry intelligence until acceptance tests and both independent reviews pass" `
      -MaxRounds 5

.NOTES
    Windows PowerShell 5.1 compatible. Terminal states: READY_TO_MERGE, BLOCKED,
    MAX_ROUNDS_REACHED.
#>

[CmdletBinding()]
param(
    # AllowEmptyString so an empty objective reaches our own validator and produces a clean
    # BLOCKED summary, rather than a raw PowerShell parameter-binder error.
    [Parameter(Mandatory = $false)]
    [AllowEmptyString()]
    [string]$Task,

    [Parameter(Mandatory = $false)]
    [int]$PrNumber = 0,

    [Parameter(Mandatory = $false)]
    [int]$MaxRounds = 5,

    [Parameter(Mandatory = $false)]
    [string]$Branch = "",

    [Parameter(Mandatory = $false)]
    [string]$BaseBranch = "main",

    [Parameter(Mandatory = $false)]
    [string]$Repo = "hanlinh227-ship-it/trading-api",

    # Validate the whole path end to end without calling external reviewers or pushing.
    [Parameter(Mandatory = $false)]
    [switch]$DryRun,

    # Skip a specific reviewer (used by the dry run to avoid burning quota).
    [Parameter(Mandatory = $false)]
    [switch]$SkipDeepSeek,

    [Parameter(Mandatory = $false)]
    [switch]$SkipCodex,

    # Bounded wait for reviewers/checks, in seconds.
    [Parameter(Mandatory = $false)]
    [int]$ReviewTimeoutSec = 900,

    [Parameter(Mandatory = $false)]
    [int]$PollIntervalSec = 20
)

$ErrorActionPreference = "Stop"
Set-StrictMode -Version 2.0

# ======================================================================================
# Hard bounds. These are ceilings, not defaults, and cannot be raised from the CLI.
# ======================================================================================
$script:HARD_MAX_ROUNDS      = 5
$script:HARD_MAX_POLLS       = 120
$script:PROTECTED_BRANCHES   = @("main", "master", "refs/heads/main", "origin/main")
$script:REPO_ROOT            = (Resolve-Path (Join-Path $PSScriptRoot "..\..")).Path
$script:PROMPT_TEMPLATE      = Join-Path $script:REPO_ROOT "scripts\ai\claude_loop_prompt.md"
$script:LOCK_FILE            = Join-Path $script:REPO_ROOT "docs\ai-coengineer\WRITE_LOCK.md"
$script:RUN_DIR              = Join-Path $env:TEMP "ai-loop"

# Loop state, mirroring AI_LOOP_STATE.schema.json.
$script:State = [ordered]@{
    task_id             = ""
    objective           = ""
    created_at          = (Get-Date).ToUniversalTime().ToString("yyyy-MM-ddTHH:mm:ssZ")
    round               = 0
    max_rounds          = 0
    branch              = ""
    pr_number           = $null
    head_sha            = $null
    status              = "IDLE"
    tests               = "NOT_RUN"
    deepseek_verdict    = $null
    deepseek_review_sha = $null
    codex_verdict       = $null
    codex_review_sha    = $null
    blocking_findings   = @()
    checks              = "UNKNOWN"
    last_actor          = "CONTROLLER"
    next_actor          = "CONTROLLER"
    next_action         = ""
}

# ======================================================================================
# Output helpers
# ======================================================================================
function Write-Step  { param([string]$m) Write-Host "==> $m" -ForegroundColor Cyan }
function Write-Info  { param([string]$m) Write-Host "    $m" -ForegroundColor Gray }
function Write-Good  { param([string]$m) Write-Host "  + $m" -ForegroundColor Green }
function Write-Warn2 { param([string]$m) Write-Host "  ! $m" -ForegroundColor Yellow }
function Write-Bad   { param([string]$m) Write-Host "  x $m" -ForegroundColor Red }

# Belt and braces: never let a credential-shaped string reach the console.
function Protect-Secret {
    param([string]$Text)
    if ([string]::IsNullOrEmpty($Text)) { return $Text }
    $out = $Text
    $out = [regex]::Replace($out, 'sk-[A-Za-z0-9_\-]{16,}', '[REDACTED]')
    $out = [regex]::Replace($out, 'gh[pousr]_[A-Za-z0-9]{20,}', '[REDACTED]')
    $out = [regex]::Replace($out, '(?i)(DEEPSEEK_API_KEY|ANTHROPIC_API_KEY|CLOUDFLARE_API_TOKEN|TWELVEDATA_API_KEY|GITHUB_TOKEN)\s*[:=]\s*\S+', '$1=[REDACTED]')
    return $out
}

function Stop-Loop {
    param(
        [Parameter(Mandatory = $true)][ValidateSet("BLOCKED", "MAX_ROUNDS_REACHED", "READY_TO_MERGE")][string]$Status,
        [Parameter(Mandatory = $true)][string]$Reason
    )
    $script:State.status      = $Status
    $script:State.next_actor  = "HUMAN"
    $script:State.next_action = $Reason
    if ($Status -ne "READY_TO_MERGE") {
        if ($script:State.blocking_findings -notcontains $Reason) {
            $script:State.blocking_findings = @($script:State.blocking_findings) + $Reason
        }
    }
    Write-Summary
    if ($Status -eq "READY_TO_MERGE") { exit 0 }
    exit 1
}

# ======================================================================================
# Native command execution
#
# Windows PowerShell 5.1 runs on .NET Framework, where ProcessStartInfo.ArgumentList does
# not exist (it arrived in .NET Core 2.1). We therefore build a single command-line string
# using the exact quoting rules CommandLineToArgvW applies, so arguments containing spaces
# or quotes survive intact. On PowerShell 7+ the structured ArgumentList is used instead.
# ======================================================================================
function ConvertTo-NativeArgument {
    param([Parameter(Mandatory = $true)][AllowEmptyString()][string]$Value)

    if ($Value.Length -gt 0 -and $Value -notmatch '[ \t\n\v"]') { return $Value }

    $sb = New-Object System.Text.StringBuilder
    [void]$sb.Append('"')
    for ($i = 0; $i -lt $Value.Length; $i++) {
        $backslashes = 0
        while ($i -lt $Value.Length -and $Value[$i] -eq '\') { $backslashes++; $i++ }
        if ($i -eq $Value.Length) {
            # Trailing backslashes must be doubled so they do not escape the closing quote.
            [void]$sb.Append('\' * ($backslashes * 2))
            break
        }
        if ($Value[$i] -eq '"') {
            [void]$sb.Append('\' * ($backslashes * 2 + 1))
            [void]$sb.Append('"')
        } else {
            [void]$sb.Append('\' * $backslashes)
            [void]$sb.Append($Value[$i])
        }
    }
    [void]$sb.Append('"')
    return $sb.ToString()
}

function ConvertTo-NativeArgumentString {
    param([Parameter(Mandatory = $true)][AllowEmptyCollection()][string[]]$Arguments)
    $quoted = @()
    foreach ($a in $Arguments) { $quoted += (ConvertTo-NativeArgument -Value $a) }
    return ($quoted -join ' ')
}

function Invoke-Native {
    param(
        [Parameter(Mandatory = $true)][string]$File,
        [Parameter(Mandatory = $true)][string[]]$Arguments,
        [string]$WorkingDirectory = $script:REPO_ROOT,
        [int]$TimeoutSec = 300,
        [string]$StdInFile = ""
    )
    if (-not (Test-Path $script:RUN_DIR)) { New-Item -ItemType Directory -Force -Path $script:RUN_DIR | Out-Null }
    $stamp   = [guid]::NewGuid().ToString("N").Substring(0, 8)
    $outFile = Join-Path $script:RUN_DIR "out_$stamp.txt"
    $errFile = Join-Path $script:RUN_DIR "err_$stamp.txt"

    $psi = New-Object System.Diagnostics.ProcessStartInfo
    $psi.FileName = $File
    $psi.WorkingDirectory = $WorkingDirectory
    $psi.UseShellExecute = $false
    $psi.RedirectStandardOutput = $true
    $psi.RedirectStandardError = $true
    $psi.RedirectStandardInput = $true
    $psi.CreateNoWindow = $true
    $psi.StandardOutputEncoding = [System.Text.Encoding]::UTF8
    $psi.StandardErrorEncoding = [System.Text.Encoding]::UTF8

    # PowerShell 7+ exposes ArgumentList; 5.1 (.NET Framework) does not.
    $hasArgumentList = $null -ne ($psi | Get-Member -Name 'ArgumentList' -ErrorAction SilentlyContinue)
    if ($hasArgumentList) {
        foreach ($a in $Arguments) { $psi.ArgumentList.Add($a) | Out-Null }
    } else {
        $psi.Arguments = ConvertTo-NativeArgumentString -Arguments $Arguments
    }

    $proc = New-Object System.Diagnostics.Process
    $proc.StartInfo = $psi
    $sbOut = New-Object System.Text.StringBuilder
    $sbErr = New-Object System.Text.StringBuilder
    $onOut = Register-ObjectEvent -InputObject $proc -EventName OutputDataReceived -Action {
        if ($null -ne $EventArgs.Data) { [void]$Event.MessageData.AppendLine($EventArgs.Data) }
    } -MessageData $sbOut
    $onErr = Register-ObjectEvent -InputObject $proc -EventName ErrorDataReceived -Action {
        if ($null -ne $EventArgs.Data) { [void]$Event.MessageData.AppendLine($EventArgs.Data) }
    } -MessageData $sbErr

    [void]$proc.Start()
    $proc.BeginOutputReadLine()
    $proc.BeginErrorReadLine()

    if ($StdInFile -and (Test-Path $StdInFile)) {
        $content = Get-Content -Path $StdInFile -Raw -Encoding UTF8
        $proc.StandardInput.Write($content)
    }
    $proc.StandardInput.Close()

    $exited = $proc.WaitForExit($TimeoutSec * 1000)
    if (-not $exited) {
        try { $proc.Kill() } catch { }
        Unregister-Event -SourceIdentifier $onOut.Name -ErrorAction SilentlyContinue
        Unregister-Event -SourceIdentifier $onErr.Name -ErrorAction SilentlyContinue
        return [pscustomobject]@{ ExitCode = 124; StdOut = $sbOut.ToString(); StdErr = "TIMEOUT after ${TimeoutSec}s"; TimedOut = $true }
    }
    Start-Sleep -Milliseconds 120
    Unregister-Event -SourceIdentifier $onOut.Name -ErrorAction SilentlyContinue
    Unregister-Event -SourceIdentifier $onErr.Name -ErrorAction SilentlyContinue
    Remove-Item $outFile, $errFile -ErrorAction SilentlyContinue

    return [pscustomobject]@{
        ExitCode = $proc.ExitCode
        StdOut   = $sbOut.ToString()
        StdErr   = $sbErr.ToString()
        TimedOut = $false
    }
}

function Invoke-Git {
    param([Parameter(Mandatory = $true)][string[]]$Arguments, [int]$TimeoutSec = 180)
    return Invoke-Native -File "git" -Arguments $Arguments -TimeoutSec $TimeoutSec
}

function Invoke-Gh {
    param([Parameter(Mandatory = $true)][string[]]$Arguments, [int]$TimeoutSec = 120)
    return Invoke-Native -File "gh" -Arguments $Arguments -TimeoutSec $TimeoutSec
}

# ======================================================================================
# STEP 1 - Preflight: required tooling
# ======================================================================================
function Resolve-Tool {
    param([string]$Name)
    $cmd = Get-Command $Name -ErrorAction SilentlyContinue
    if ($null -eq $cmd) { return $null }
    return $cmd.Source
}

function Resolve-Python {
    # The Windows Store stub 'python' resolves but fails to execute; prefer the launcher.
    foreach ($candidate in @("py", "python3", "python")) {
        $path = Resolve-Tool $candidate
        if ($null -ne $path) {
            $probe = Invoke-Native -File $candidate -Arguments @("-c", "import sys;print(sys.version_info[0])") -TimeoutSec 30
            if ($probe.ExitCode -eq 0 -and $probe.StdOut.Trim() -eq "3") { return $candidate }
        }
    }
    return $null
}

function Test-Preflight {
    Write-Step "STEP 1/12  Verifying required tooling"
    $required = @("git", "gh", "claude", "node")
    $missing = @()
    foreach ($t in $required) {
        $p = Resolve-Tool $t
        if ($null -eq $p) { $missing += $t; Write-Bad "$t NOT FOUND" }
        else { Write-Good "$t -> $p" }
    }
    $script:PythonCmd = Resolve-Python
    if ($null -eq $script:PythonCmd) { Write-Warn2 "python NOT FOUND (DeepSeek reviewer runs in CI, so this is non-fatal locally)" }
    else { Write-Good "python -> $script:PythonCmd" }

    if ($missing.Count -gt 0) {
        Stop-Loop -Status "BLOCKED" -Reason ("Required tool(s) missing: " + ($missing -join ", "))
    }
}

# ======================================================================================
# STEP 2 - GitHub auth
# ======================================================================================
function Test-GitHubAuth {
    Write-Step "STEP 2/12  Verifying GitHub authentication"
    $r = Invoke-Gh -Arguments @("auth", "status") -TimeoutSec 60
    if ($r.ExitCode -ne 0) {
        Stop-Loop -Status "BLOCKED" -Reason "GitHub CLI is not authenticated. Run: gh auth login"
    }
    $combined = "$($r.StdOut)$($r.StdErr)"
    if ($combined -notmatch "Logged in to") {
        Stop-Loop -Status "BLOCKED" -Reason "GitHub CLI reported no active login."
    }
    Write-Good "gh authenticated"

    # Existence-only secret check. Values are never read or printed.
    $s = Invoke-Gh -Arguments @("secret", "list", "--repo", $Repo) -TimeoutSec 60
    if ($s.ExitCode -eq 0) {
        if ($s.StdOut -match "DEEPSEEK_API_KEY") { Write-Good "DEEPSEEK_API_KEY present in repo secrets (value not read)" }
        else {
            Write-Warn2 "DEEPSEEK_API_KEY not found in repo secrets"
            $script:DeepSeekSecretMissing = $true
        }
    } else {
        Write-Warn2 "Could not list secret names (insufficient scope). DeepSeek availability unknown."
    }
}

# ======================================================================================
# STEP 3 - Refresh base
# ======================================================================================
function Update-Base {
    Write-Step "STEP 3/12  Refreshing origin/$BaseBranch"
    $r = Invoke-Git -Arguments @("fetch", "origin", "--prune")
    if ($r.ExitCode -ne 0) { Stop-Loop -Status "BLOCKED" -Reason "git fetch failed: $(Protect-Secret $r.StdErr)" }
    $sha = (Invoke-Git -Arguments @("rev-parse", "origin/$BaseBranch")).StdOut.Trim()
    Write-Good "origin/$BaseBranch = $sha"
}

# ======================================================================================
# STEP 4 - WRITE_LOCK
# ======================================================================================
function Test-WriteLock {
    Write-Step "STEP 4/12  Verifying WRITE_LOCK"
    if (-not (Test-Path $script:LOCK_FILE)) {
        Write-Warn2 "WRITE_LOCK.md not found; continuing without a lock assertion"
        return
    }
    $lock = Get-Content -Path $script:LOCK_FILE -Raw -Encoding UTF8
    $locked = ($lock -match "(?m)^LOCKED:\s*true")
    $owner = ""
    if ($lock -match "(?m)^OWNER:\s*(.+)$") { $owner = $Matches[1].Trim() }
    $scope = ""
    if ($lock -match "(?m)^SCOPE:\s*(.+)$") { $scope = $Matches[1].Trim() }

    if ($locked) {
        Write-Info "LOCKED: true / OWNER: $owner"
        Write-Info "SCOPE : $scope"
        if ($owner -ne "CLAUDE_LOCAL") {
            Stop-Loop -Status "BLOCKED" -Reason "WRITE_LOCK is held by '$owner', not CLAUDE_LOCAL. Refusing to write."
        }
        Write-Good "Lock held by CLAUDE_LOCAL"
    } else {
        Write-Good "WRITE_LOCK is free"
    }
}

# ======================================================================================
# STEP 5 - Branch resolution. NEVER main.
# ======================================================================================
function Test-BranchSafe {
    param([string]$Name)
    if ([string]::IsNullOrWhiteSpace($Name)) { return $false }
    $normalized = $Name.Trim().ToLowerInvariant() -replace '^refs/heads/', ''
    foreach ($p in $script:PROTECTED_BRANCHES) {
        if ($normalized -eq ($p.ToLowerInvariant() -replace '^refs/heads/', '')) { return $false }
    }
    return $true
}

function New-TaskId {
    param([string]$Objective)
    $slug = ($Objective.ToLowerInvariant() -replace '[^a-z0-9]+', '-').Trim('-')
    if ($slug.Length -gt 28) { $slug = $slug.Substring(0, 28).Trim('-') }
    if ([string]::IsNullOrWhiteSpace($slug)) { $slug = "loop-task" }
    $stamp = (Get-Date).ToUniversalTime().ToString("yyyyMMdd-HHmmss")
    return "$slug-$stamp"
}

function Initialize-Branch {
    Write-Step "STEP 5/12  Resolving implementation branch"

    if ($PrNumber -gt 0) {
        $r = Invoke-Gh -Arguments @("pr", "view", "$PrNumber", "--repo", $Repo, "--json", "headRefName,headRefOid,state")
        if ($r.ExitCode -ne 0) { Stop-Loop -Status "BLOCKED" -Reason "PR #$PrNumber could not be read." }
        $pr = $r.StdOut | ConvertFrom-Json
        if ($pr.state -ne "OPEN") { Stop-Loop -Status "BLOCKED" -Reason "PR #$PrNumber is $($pr.state), not OPEN." }
        $script:State.branch = $pr.headRefName
        $script:State.pr_number = $PrNumber
        Write-Good "Reusing PR #$PrNumber on branch $($pr.headRefName)"
    }
    elseif ($Branch) {
        $script:State.branch = $Branch
    }
    else {
        $script:State.branch = "ai-loop/" + $script:State.task_id
    }

    if (-not (Test-BranchSafe $script:State.branch)) {
        Stop-Loop -Status "BLOCKED" -Reason "Refusing to run implementation on protected branch '$($script:State.branch)'. The controller never pushes to main."
    }
    Write-Good "Implementation branch: $($script:State.branch)"

    # Check out or create the branch locally.
    $exists = Invoke-Git -Arguments @("rev-parse", "--verify", "--quiet", "refs/heads/$($script:State.branch)")
    if ($exists.ExitCode -eq 0) {
        $co = Invoke-Git -Arguments @("checkout", $script:State.branch)
        if ($co.ExitCode -ne 0) { Stop-Loop -Status "BLOCKED" -Reason "Could not check out $($script:State.branch)." }
    } else {
        $remote = Invoke-Git -Arguments @("rev-parse", "--verify", "--quiet", "refs/remotes/origin/$($script:State.branch)")
        if ($remote.ExitCode -eq 0) {
            $co = Invoke-Git -Arguments @("checkout", "-B", $script:State.branch, "origin/$($script:State.branch)")
        } else {
            $co = Invoke-Git -Arguments @("checkout", "-B", $script:State.branch, "origin/$BaseBranch")
        }
        if ($co.ExitCode -ne 0) { Stop-Loop -Status "BLOCKED" -Reason "Could not create branch $($script:State.branch)." }
    }

    # Final paranoia check: whatever we ended up on must not be a protected branch.
    $current = (Invoke-Git -Arguments @("rev-parse", "--abbrev-ref", "HEAD")).StdOut.Trim()
    if (-not (Test-BranchSafe $current)) {
        Stop-Loop -Status "BLOCKED" -Reason "Working tree is on protected branch '$current'. Aborting before any write."
    }
    Write-Good "Checked out $current"
}

# ======================================================================================
# STEP 6 - Claude implementation round (narrow allowedTools, never skip-permissions)
# ======================================================================================
function Get-ClaudeAllowedTools {
    # Deliberately narrow. Claude may read/edit and run read-only git plus the test
    # commands. It gets no push, no commit, no merge, no deploy, no secret access.
    return @(
        "Read", "Edit", "Write", "Glob", "Grep",
        "Bash(git status:*)",
        "Bash(git log:*)",
        "Bash(git diff:*)",
        "Bash(git show:*)",
        "Bash(git rev-parse:*)",
        "Bash(node --check:*)",
        "Bash(node scripts/ai/:*)",
        "Bash(node cloudflare-worker/validate-worker.mjs)",
        "Bash(npm test:*)"
    ) -join ","
}

function Build-RoundPrompt {
    param([string]$BlockingFindings)

    if (-not (Test-Path $script:PROMPT_TEMPLATE)) {
        Stop-Loop -Status "BLOCKED" -Reason "Prompt template missing: $script:PROMPT_TEMPLATE"
    }
    $tpl = Get-Content -Path $script:PROMPT_TEMPLATE -Raw -Encoding UTF8

    $prRef = "(not created yet)"
    if ($null -ne $script:State.pr_number) { $prRef = "#$($script:State.pr_number)" }
    $headSha = "(uncommitted working tree)"
    if ($script:State.head_sha) { $headSha = $script:State.head_sha }

    $tpl = $tpl.Replace("{{ROUND}}",             [string]$script:State.round)
    $tpl = $tpl.Replace("{{MAX_ROUNDS}}",        [string]$script:State.max_rounds)
    $tpl = $tpl.Replace("{{TASK_ID}}",           $script:State.task_id)
    $tpl = $tpl.Replace("{{BRANCH}}",            $script:State.branch)
    $tpl = $tpl.Replace("{{BASE_BRANCH}}",       $BaseBranch)
    $tpl = $tpl.Replace("{{PR_REF}}",            $prRef)
    $tpl = $tpl.Replace("{{HEAD_SHA}}",          $headSha)
    $tpl = $tpl.Replace("{{OBJECTIVE}}",         $script:State.objective)
    $tpl = $tpl.Replace("{{BLOCKING_FINDINGS}}", $BlockingFindings)
    $tpl = $tpl.Replace("{{TEST_COMMANDS}}",     (Get-TestCommandList) -join "`n")
    return $tpl
}

function Invoke-ClaudeRound {
    param([string]$BlockingFindings)

    Write-Step "STEP 6/12  CLAUDE_LOCAL implementation round $($script:State.round)/$($script:State.max_rounds)"
    $script:State.status = "IMPLEMENTING"
    $script:State.last_actor = "CLAUDE_LOCAL"

    $prompt = Build-RoundPrompt -BlockingFindings $BlockingFindings
    if (-not (Test-Path $script:RUN_DIR)) { New-Item -ItemType Directory -Force -Path $script:RUN_DIR | Out-Null }
    $promptFile = Join-Path $script:RUN_DIR "prompt_r$($script:State.round).md"
    Set-Content -Path $promptFile -Value $prompt -Encoding UTF8

    $allowed = Get-ClaudeAllowedTools
    Write-Info "allowedTools: $allowed"
    Write-Info "prompt: $promptFile ($($prompt.Length) chars)"

    if ($DryRun) {
        Write-Warn2 "DRY RUN - not invoking claude -p. Prompt rendered and validated only."
        foreach ($ph in @("{{ROUND}}", "{{OBJECTIVE}}", "{{TASK_ID}}", "{{BRANCH}}", "{{TEST_COMMANDS}}", "{{BLOCKING_FINDINGS}}")) {
            if ($prompt.Contains($ph)) { Stop-Loop -Status "BLOCKED" -Reason "Prompt placeholder $ph was not substituted." }
        }
        Write-Good "Prompt fully substituted (no placeholders remain)"
        return [pscustomobject]@{ Status = "DRY_RUN"; Blockers = @(); Summary = "dry run"; SafetyInvariants = "PASS"; Raw = "" }
    }

    # NOTE: --dangerously-skip-permissions is deliberately NEVER used.
    $args = @("-p", "--allowedTools", $allowed)
    $r = Invoke-Native -File "claude" -Arguments $args -TimeoutSec 1800 -StdInFile $promptFile

    $raw = "$($r.StdOut)"
    $transcript = Join-Path $script:RUN_DIR "claude_r$($script:State.round).txt"
    Set-Content -Path $transcript -Value (Protect-Secret $raw) -Encoding UTF8
    Write-Info "transcript: $transcript"

    if ($r.TimedOut) { Stop-Loop -Status "BLOCKED" -Reason "Claude round timed out after 1800s." }
    if ($r.ExitCode -ne 0 -and [string]::IsNullOrWhiteSpace($raw)) {
        Stop-Loop -Status "BLOCKED" -Reason "claude -p failed (exit $($r.ExitCode)): $(Protect-Secret $r.StdErr)"
    }

    return Read-ClaudeBlock -Text $raw
}

function Read-ClaudeBlock {
    param([string]$Text)
    $result = [pscustomobject]@{
        Status           = "UNKNOWN"
        FilesChanged     = @()
        TestsResult      = "NOT_RUN"
        Summary          = ""
        Blockers         = @()
        SafetyInvariants = "UNKNOWN"
        Raw              = $Text
    }
    if ($Text -notmatch "CLAUDE_ROUND_BEGIN") {
        Write-Warn2 "Claude did not emit a CLAUDE_ROUND block; treating the round as unverified."
        return $result
    }
    $body = ($Text -split "CLAUDE_ROUND_BEGIN", 2)[1]
    $body = ($body -split "CLAUDE_ROUND_END", 2)[0]

    $current = ""
    $collect = @{ "BLOCKERS" = @(); "TESTS_RUN" = @() }
    foreach ($line in ($body -split "`r?`n")) {
        $t = $line.Trim()
        if ([string]::IsNullOrWhiteSpace($t)) { continue }
        if ($t -match '^(TASK_ID|ROUND|STATUS|FILES_CHANGED|TESTS_RUN|TESTS_RESULT|SUMMARY|BLOCKERS|SAFETY_INVARIANTS)\s*=\s*(.*)$') {
            $current = $Matches[1]
            $val = $Matches[2].Trim()
            switch ($current) {
                "STATUS"            { $result.Status = $val.ToUpperInvariant() }
                "TESTS_RESULT"      { $result.TestsResult = $val.ToUpperInvariant() }
                "SUMMARY"           { $result.Summary = $val }
                "SAFETY_INVARIANTS" { $result.SafetyInvariants = $val.ToUpperInvariant() }
                "FILES_CHANGED"     { if ($val -and $val.ToUpperInvariant() -ne "NONE") { $result.FilesChanged = ($val -split ',') | ForEach-Object { $_.Trim() } } }
                "BLOCKERS"          { if ($val -and $val.ToUpperInvariant() -ne "NONE") { $collect["BLOCKERS"] += $val } }
                "TESTS_RUN"         { if ($val -and $val.ToUpperInvariant() -ne "NONE") { $collect["TESTS_RUN"] += $val } }
            }
        }
        elseif ($current -eq "BLOCKERS") { $collect["BLOCKERS"] += $t }
        elseif ($current -eq "TESTS_RUN") { $collect["TESTS_RUN"] += $t }
    }
    $result.Blockers = @($collect["BLOCKERS"] | Where-Object { $_ -and $_.ToUpperInvariant() -ne "NONE" })
    return $result
}

# ======================================================================================
# STEP 7 - Deterministic tests (controller-run, independent of Claude's claims)
# ======================================================================================
function Get-ChangedFiles {
    $r = Invoke-Git -Arguments @("diff", "--name-only", "HEAD")
    $tracked = @()
    if ($r.ExitCode -eq 0) { $tracked = @($r.StdOut -split "`r?`n" | Where-Object { $_ }) }
    $u = Invoke-Git -Arguments @("ls-files", "--others", "--exclude-standard")
    if ($u.ExitCode -eq 0) { $tracked += @($u.StdOut -split "`r?`n" | Where-Object { $_ }) }
    return @($tracked | Select-Object -Unique)
}

function Get-TestCommandList {
    return @(
        "node cloudflare-worker/validate-worker.mjs",
        "node scripts/ai/forex-metal-index-validation.mjs",
        "node scripts/ai/ai-loop-selftest.mjs",
        "node --check <each changed cloudflare-worker/**/*.js>",
        "git diff --check"
    )
}

function Invoke-DeterministicTests {
    Write-Step "STEP 7/12  Running deterministic tests"
    $script:State.status = "TESTING"
    $results = @()
    $allPass = $true

    $changed = Get-ChangedFiles
    if ($changed.Count -gt 0) { Write-Info "changed files: $($changed -join ', ')" }

    # 1. Syntax-check every changed JS/MJS file.
    foreach ($f in $changed) {
        if ($f -match '\.(js|mjs)$' -and (Test-Path (Join-Path $script:REPO_ROOT $f))) {
            $r = Invoke-Native -File "node" -Arguments @("--check", $f) -TimeoutSec 60
            $ok = ($r.ExitCode -eq 0)
            if (-not $ok) { $allPass = $false }
            $results += [pscustomobject]@{ Command = "node --check $f"; Pass = $ok; Output = (Protect-Secret $r.StdErr) }
            if ($ok) { Write-Good "node --check $f" } else { Write-Bad "node --check $f`n$(Protect-Secret $r.StdErr)" }
        }
        if ($f -match '\.py$' -and $null -ne $script:PythonCmd -and (Test-Path (Join-Path $script:REPO_ROOT $f))) {
            $r = Invoke-Native -File $script:PythonCmd -Arguments @("-m", "py_compile", $f) -TimeoutSec 60
            $ok = ($r.ExitCode -eq 0)
            if (-not $ok) { $allPass = $false }
            $results += [pscustomobject]@{ Command = "py_compile $f"; Pass = $ok; Output = (Protect-Secret $r.StdErr) }
            if ($ok) { Write-Good "py_compile $f" } else { Write-Bad "py_compile $f`n$(Protect-Secret $r.StdErr)" }
        }
    }

    # 2. Always-run repository validators (only if present).
    $always = @(
        @{ Name = "worker preflight";       File = "node"; Args = @("validate-worker.mjs"); Cwd = (Join-Path $script:REPO_ROOT "cloudflare-worker"); Probe = (Join-Path $script:REPO_ROOT "cloudflare-worker\validate-worker.mjs") },
        @{ Name = "V78-032 invariants";     File = "node"; Args = @("scripts/ai/forex-metal-index-validation.mjs"); Cwd = $script:REPO_ROOT; Probe = (Join-Path $script:REPO_ROOT "scripts\ai\forex-metal-index-validation.mjs") },
        @{ Name = "ai-loop selftest";       File = "node"; Args = @("scripts/ai/ai-loop-selftest.mjs"); Cwd = $script:REPO_ROOT; Probe = (Join-Path $script:REPO_ROOT "scripts\ai\ai-loop-selftest.mjs") }
    )
    foreach ($t in $always) {
        if (-not (Test-Path $t.Probe)) { Write-Info "skip $($t.Name) (not present)"; continue }
        $r = Invoke-Native -File $t.File -Arguments $t.Args -WorkingDirectory $t.Cwd -TimeoutSec 300
        $ok = ($r.ExitCode -eq 0)
        if (-not $ok) { $allPass = $false }
        $results += [pscustomobject]@{ Command = $t.Name; Pass = $ok; Output = (Protect-Secret ($r.StdOut + $r.StdErr)) }
        if ($ok) { Write-Good "$($t.Name)" } else { Write-Bad "$($t.Name)`n$(Protect-Secret ($r.StdOut + $r.StdErr))" }
    }

    # 3. Whitespace / conflict-marker hygiene.
    $r = Invoke-Git -Arguments @("diff", "--check")
    $ok = ($r.ExitCode -eq 0)
    if (-not $ok) { $allPass = $false }
    $results += [pscustomobject]@{ Command = "git diff --check"; Pass = $ok; Output = (Protect-Secret $r.StdOut) }
    if ($ok) { Write-Good "git diff --check" } else { Write-Bad "git diff --check" }

    $script:State.tests = if ($allPass) { "PASS" } else { "FAIL" }
    $script:TestEvidence = $results
    return $allPass
}

function Write-EvidenceFile {
    $path = Join-Path $script:RUN_DIR "evidence_r$($script:State.round).txt"
    $lines = @("AI_LOOP deterministic test evidence", "task_id=$($script:State.task_id)", "round=$($script:State.round)", "")
    foreach ($t in $script:TestEvidence) {
        $verdict = if ($t.Pass) { "PASS" } else { "FAIL" }
        $lines += "[$verdict] $($t.Command)"
        if (-not $t.Pass -and $t.Output) { $lines += ("        " + (($t.Output -split "`r?`n") -join "`n        ")) }
    }
    Set-Content -Path $path -Value ($lines -join "`n") -Encoding UTF8
    return $path
}

# ======================================================================================
# STEP 8/9 - Commit, push, PR (controller-owned git writes only)
# ======================================================================================
function Publish-Round {
    Write-Step "STEP 8/12  Committing and pushing (controller-owned)"

    $current = (Invoke-Git -Arguments @("rev-parse", "--abbrev-ref", "HEAD")).StdOut.Trim()
    if (-not (Test-BranchSafe $current)) {
        Stop-Loop -Status "BLOCKED" -Reason "Refusing to push: HEAD is on protected branch '$current'."
    }

    $status = (Invoke-Git -Arguments @("status", "--porcelain")).StdOut
    if ([string]::IsNullOrWhiteSpace($status)) {
        Write-Warn2 "No changes to commit this round."
        $script:State.head_sha = (Invoke-Git -Arguments @("rev-parse", "HEAD")).StdOut.Trim()
        return $false
    }

    if ($DryRun) {
        Write-Warn2 "DRY RUN - skipping commit and push. Pending changes left in the working tree."
        return $false
    }

    [void](Invoke-Git -Arguments @("add", "-A"))
    $msgFile = Join-Path $script:RUN_DIR "commitmsg_r$($script:State.round).txt"
    $msg = @(
        "$($script:State.task_id): AI loop round $($script:State.round)",
        "",
        $script:State.objective,
        "",
        "Round $($script:State.round)/$($script:State.max_rounds). Deterministic tests: $($script:State.tests).",
        "Produced by the bounded AI engineering loop (AI_LOOP_V1). Not merged, not deployed.",
        "",
        "Co-Authored-By: Claude Opus 5 (1M context) <noreply@anthropic.com>"
    ) -join "`n"
    Set-Content -Path $msgFile -Value $msg -Encoding UTF8

    $c = Invoke-Git -Arguments @("commit", "-F", $msgFile)
    if ($c.ExitCode -ne 0) { Stop-Loop -Status "BLOCKED" -Reason "git commit failed: $(Protect-Secret $c.StdErr)" }

    # Explicit refspec, never a force push.
    $p = Invoke-Git -Arguments @("push", "origin", "$($script:State.branch):$($script:State.branch)") -TimeoutSec 300
    if ($p.ExitCode -ne 0) { Stop-Loop -Status "BLOCKED" -Reason "git push failed: $(Protect-Secret $p.StdErr)" }

    $script:State.head_sha = (Invoke-Git -Arguments @("rev-parse", "HEAD")).StdOut.Trim()
    Write-Good "pushed $($script:State.branch) -> $($script:State.head_sha)"
    return $true
}

function Sync-PullRequest {
    Write-Step "STEP 9/12  Creating or updating the pull request"
    if ($DryRun) { Write-Warn2 "DRY RUN - skipping PR create/update."; return }

    if ($null -ne $script:State.pr_number) {
        Write-Good "Using existing PR #$($script:State.pr_number)"
        return
    }
    $find = Invoke-Gh -Arguments @("pr", "list", "--repo", $Repo, "--head", $script:State.branch, "--state", "open", "--json", "number", "--jq", ".[0].number")
    $existing = $find.StdOut.Trim()
    if ($existing -match '^\d+$') {
        $script:State.pr_number = [int]$existing
        Write-Good "Found existing PR #$existing"
        return
    }

    $bodyFile = Join-Path $script:RUN_DIR "prbody_$($script:State.task_id).md"
    $body = @(
        "## AI loop objective",
        "",
        $script:State.objective,
        "",
        "## Loop metadata",
        "",
        "- task_id: ``$($script:State.task_id)``",
        "- round: $($script:State.round)/$($script:State.max_rounds)",
        "- deterministic tests: **$($script:State.tests)**",
        "",
        "## Review protocol",
        "",
        "This PR is reviewed by two independent reviewers before it can reach ``READY_TO_MERGE``:",
        "",
        "- **DeepSeek** (adversarial reviewer) via ``AI Loop DeepSeek Review``",
        "- **Codex** (independent reviewer) via ``@codex review``",
        "",
        "Both must accept the **same** head SHA, and required checks must pass.",
        "",
        "The loop never merges and never deploys. Merging is a human action.",
        "",
        "See ``docs/ai-coengineer/AI_LOOP_CONTRACT.md``."
    ) -join "`n"
    Set-Content -Path $bodyFile -Value $body -Encoding UTF8

    $title = "$($script:State.task_id): $($script:State.objective)"
    if ($title.Length -gt 100) { $title = $title.Substring(0, 97) + "..." }

    $r = Invoke-Gh -Arguments @("pr", "create", "--repo", $Repo, "--base", $BaseBranch, "--head", $script:State.branch, "--title", $title, "--body-file", $bodyFile)
    if ($r.ExitCode -ne 0) { Stop-Loop -Status "BLOCKED" -Reason "gh pr create failed: $(Protect-Secret $r.StdErr)" }

    $num = Invoke-Gh -Arguments @("pr", "list", "--repo", $Repo, "--head", $script:State.branch, "--state", "open", "--json", "number", "--jq", ".[0].number")
    if ($num.StdOut.Trim() -match '^\d+$') { $script:State.pr_number = [int]$num.StdOut.Trim() }
    Write-Good "Created PR #$($script:State.pr_number)"
}

# ======================================================================================
# STEP 10 - Trigger reviewers
# ======================================================================================
function Request-DeepSeekReview {
    Write-Step "STEP 10/12  Requesting DeepSeek adversarial review"
    if ($SkipDeepSeek -or $DryRun) {
        Write-Warn2 "DeepSeek request skipped (dry run or -SkipDeepSeek). No API quota consumed."
        $script:State.deepseek_verdict = "PENDING"
        return
    }
    if ($script:DeepSeekSecretMissing) {
        Write-Bad "DEEPSEEK_API_KEY missing. Classification: MISSING_SECRET"
        $script:State.deepseek_verdict = "BLOCKED"
        return
    }
    # The workflow also fires automatically on pull_request synchronize; this dispatch is
    # a belt-and-braces trigger for the exact head.
    $r = Invoke-Gh -Arguments @("workflow", "run", "ai-loop-deepseek-review.yml", "--repo", $Repo, "-f", "pr_number=$($script:State.pr_number)")
    if ($r.ExitCode -ne 0) { Write-Warn2 "workflow dispatch failed; relying on the pull_request trigger instead." }
    else { Write-Good "DeepSeek review workflow dispatched" }
    $script:State.deepseek_verdict = "PENDING"
}

function Request-CodexReview {
    Write-Step "STEP 11/12  Requesting Codex independent review"
    if ($SkipCodex -or $DryRun) {
        Write-Warn2 "Codex request skipped (dry run or -SkipCodex)."
        $script:State.codex_verdict = "PENDING"
        return
    }
    $body = @(
        "@codex review",
        "",
        "Review the exact current HEAD ``$($script:State.head_sha)`` as an independent reviewer.",
        "Focus on correctness, regression risk, test evidence, safety invariants and task acceptance criteria.",
        "",
        "Objective under test:",
        "",
        "> $($script:State.objective)",
        "",
        "Safety invariants that must not be weakened: SIGNAL-ONLY architecture, quote freshness,",
        "structural SL, RR gates, anti-chase, hard-news safeguards, exact market identity,",
        "TRADING_STATE, v775:books, and the V73 frozen prior."
    ) -join "`n"
    $bodyFile = Join-Path $script:RUN_DIR "codexreq_r$($script:State.round).md"
    Set-Content -Path $bodyFile -Value $body -Encoding UTF8

    $r = Invoke-Gh -Arguments @("pr", "comment", "$($script:State.pr_number)", "--repo", $Repo, "--body-file", $bodyFile)
    if ($r.ExitCode -ne 0) { Write-Warn2 "Could not post the Codex review request: $(Protect-Secret $r.StdErr)" }
    else { Write-Good "Requested Codex review for $($script:State.head_sha)" }
    $script:State.codex_verdict = "PENDING"
}

# ======================================================================================
# STEP 12 - Poll GitHub for checks and both reviewer verdicts
# ======================================================================================
function Get-CheckRollup {
    $r = Invoke-Gh -Arguments @("api", "repos/$Repo/commits/$($script:State.head_sha)/check-runs", "--jq", "[.check_runs[] | {name, status, conclusion}]")
    if ($r.ExitCode -ne 0) { return [pscustomobject]@{ Status = "UNKNOWN"; Failing = @() } }
    $runs = @()
    try { $runs = @($r.StdOut | ConvertFrom-Json) } catch { return [pscustomobject]@{ Status = "UNKNOWN"; Failing = @() } }
    if ($runs.Count -eq 0) { return [pscustomobject]@{ Status = "UNKNOWN"; Failing = @() } }
    $failing = @(); $pending = 0
    foreach ($run in $runs) {
        if ($run.status -ne "completed") { $pending++ }
        elseif (@("failure", "timed_out", "cancelled", "action_required") -contains $run.conclusion) { $failing += $run.name }
    }
    if ($failing.Count -gt 0) { return [pscustomobject]@{ Status = "FAIL"; Failing = $failing } }
    if ($pending -gt 0) { return [pscustomobject]@{ Status = "PENDING"; Failing = @() } }
    return [pscustomobject]@{ Status = "PASS"; Failing = @() }
}

function Get-DeepSeekVerdict {
    $r = Invoke-Gh -Arguments @("api", "repos/$Repo/issues/$($script:State.pr_number)/comments", "--paginate", "--jq", "[.[] | {body}]")
    if ($r.ExitCode -ne 0) { return [pscustomobject]@{ Verdict = "PENDING"; Sha = $null; Blockers = @() } }
    $comments = @()
    try { $comments = @($r.StdOut | ConvertFrom-Json) } catch { return [pscustomobject]@{ Verdict = "PENDING"; Sha = $null; Blockers = @() } }

    $best = [pscustomobject]@{ Verdict = "PENDING"; Sha = $null; Blockers = @() }
    foreach ($c in $comments) {
        $b = $c.body
        if ($null -eq $b -or $b -notmatch "DEEPSEEK_REVIEW_BEGIN") { continue }
        $block = ($b -split "DEEPSEEK_REVIEW_BEGIN", 2)[1]
        $block = ($block -split "DEEPSEEK_REVIEW_END", 2)[0]
        $sha = $null; $verdict = "PENDING"; $blockers = @(); $cur = ""
        foreach ($line in ($block -split "`r?`n")) {
            $t = $line.Trim()
            if ([string]::IsNullOrWhiteSpace($t)) { continue }
            if ($t -match '^(HEAD_SHA|VERDICT|BLOCKERS|NON_BLOCKING)\s*=\s*(.*)$') {
                $cur = $Matches[1]; $val = $Matches[2].Trim()
                if ($cur -eq "HEAD_SHA") { $sha = $val.ToLowerInvariant() }
                elseif ($cur -eq "VERDICT") { $verdict = $val.ToUpperInvariant() }
                elseif ($cur -eq "BLOCKERS" -and $val -and $val.ToUpperInvariant() -ne "NONE") { $blockers += $val }
            }
            elseif ($cur -eq "BLOCKERS" -and $t.ToUpperInvariant() -ne "NONE") { $blockers += $t }
        }
        # Contract rule: ACCEPT with blockers is a contradiction; downgrade to REJECT.
        if ($verdict -eq "ACCEPT" -and $blockers.Count -gt 0) { $verdict = "REJECT" }
        if ($sha -eq $script:State.head_sha.ToLowerInvariant()) {
            $best = [pscustomobject]@{ Verdict = $verdict; Sha = $sha; Blockers = $blockers }
        }
    }
    return $best
}

function Get-CodexVerdict {
    $blockers = @()
    $r = Invoke-Gh -Arguments @("api", "repos/$Repo/pulls/$($script:State.pr_number)/reviews", "--paginate", "--jq", "[.[] | {login: .user.login, state, commit_id, body}]")
    if ($r.ExitCode -eq 0) {
        $reviews = @()
        try { $reviews = @($r.StdOut | ConvertFrom-Json) } catch { $reviews = @() }
        foreach ($rev in $reviews) {
            if ($null -eq $rev.login -or $rev.login -notmatch '(?i)codex') { continue }
            if ($null -eq $rev.commit_id) { continue }
            if ($rev.commit_id.ToLowerInvariant() -ne $script:State.head_sha.ToLowerInvariant()) { continue }
            if ($rev.state -eq "APPROVED") { return [pscustomobject]@{ Verdict = "ACCEPT"; Sha = $rev.commit_id; Blockers = @() } }
            if ($rev.state -eq "CHANGES_REQUESTED") {
                $summary = "Codex requested changes"
                if ($rev.body) { $summary = ($rev.body -split "`r?`n" | Where-Object { $_.Trim() } | Select-Object -First 6) -join " " }
                return [pscustomobject]@{ Verdict = "REJECT"; Sha = $rev.commit_id; Blockers = @($summary) }
            }
            if ($rev.state -eq "COMMENTED" -and $rev.body) {
                if ($rev.body -match '(?i)\b(P1|blocking|must fix|critical|bug:)\b') {
                    $summary = ($rev.body -split "`r?`n" | Where-Object { $_.Trim() } | Select-Object -First 6) -join " "
                    return [pscustomobject]@{ Verdict = "REJECT"; Sha = $rev.commit_id; Blockers = @($summary) }
                }
                return [pscustomobject]@{ Verdict = "ACCEPT"; Sha = $rev.commit_id; Blockers = @() }
            }
        }
    }
    return [pscustomobject]@{ Verdict = "PENDING"; Sha = $null; Blockers = $blockers }
}

function Wait-ForReviews {
    Write-Step "STEP 12/12  Polling GitHub for checks and reviewer verdicts"
    $script:State.status = "AWAITING_REVIEWS"

    if ($DryRun) {
        Write-Warn2 "DRY RUN - not polling live reviewers."
        return $false
    }

    $deadline = (Get-Date).AddSeconds($ReviewTimeoutSec)
    $polls = 0
    while ((Get-Date) -lt $deadline -and $polls -lt $script:HARD_MAX_POLLS) {
        $polls++
        $checks = Get-CheckRollup
        $script:State.checks = $checks.Status

        $ds = Get-DeepSeekVerdict
        if ($SkipDeepSeek) { $ds = [pscustomobject]@{ Verdict = "ACCEPT"; Sha = $script:State.head_sha; Blockers = @() } }
        $script:State.deepseek_verdict = $ds.Verdict
        $script:State.deepseek_review_sha = $ds.Sha

        $cx = Get-CodexVerdict
        if ($SkipCodex) { $cx = [pscustomobject]@{ Verdict = "ACCEPT"; Sha = $script:State.head_sha; Blockers = @() } }
        $script:State.codex_verdict = $cx.Verdict
        $script:State.codex_review_sha = $cx.Sha

        Write-Info "poll $polls/$script:HARD_MAX_POLLS  checks=$($checks.Status)  deepseek=$($ds.Verdict)  codex=$($cx.Verdict)"

        # Fail fast on a definite rejection - do not wait out the timeout.
        if ($ds.Verdict -eq "REJECT" -or $cx.Verdict -eq "REJECT" -or $ds.Verdict -eq "BLOCKED") {
            $script:State.blocking_findings = @($ds.Blockers) + @($cx.Blockers) | Where-Object { $_ }
            if ($checks.Status -eq "FAIL") {
                $script:State.blocking_findings += "Failing GitHub checks: " + ($checks.Failing -join ", ")
            }
            return $false
        }

        $bothAccepted = ($ds.Verdict -eq "ACCEPT" -and $cx.Verdict -eq "ACCEPT")
        $shaFresh = $true
        if (-not $SkipDeepSeek) { if ($ds.Sha -ne $script:State.head_sha.ToLowerInvariant()) { $shaFresh = $false } }
        if (-not $SkipCodex)    { if ($null -eq $cx.Sha -or $cx.Sha.ToLowerInvariant() -ne $script:State.head_sha.ToLowerInvariant()) { $shaFresh = $false } }

        if ($bothAccepted -and $shaFresh -and $checks.Status -eq "PASS" -and $script:State.tests -eq "PASS") {
            return $true
        }
        if ($checks.Status -eq "FAIL") {
            $script:State.blocking_findings = @("Failing GitHub checks: " + ($checks.Failing -join ", "))
            return $false
        }
        Start-Sleep -Seconds $PollIntervalSec
    }

    Write-Warn2 "Review window elapsed without a complete verdict set."
    $script:State.blocking_findings = @("Reviews did not complete within ${ReviewTimeoutSec}s (deepseek=$($script:State.deepseek_verdict), codex=$($script:State.codex_verdict), checks=$($script:State.checks))")
    return $false
}

# ======================================================================================
# Final summary
# ======================================================================================
function Write-Summary {
    $pr = "none"
    if ($null -ne $script:State.pr_number) { $pr = "#$($script:State.pr_number)" }
    $head = "none"
    if ($script:State.head_sha) { $head = $script:State.head_sha }
    $nextAction = $script:State.next_action
    if ([string]::IsNullOrWhiteSpace($nextAction)) {
        switch ($script:State.status) {
            "READY_TO_MERGE"     { $nextAction = "Human review and manual merge. The loop never merges." }
            "MAX_ROUNDS_REACHED" { $nextAction = "Inspect the remaining blocking findings and decide manually." }
            "BLOCKED"            { $nextAction = "Resolve the hard blocker listed above, then re-run." }
            default              { $nextAction = "Re-run the loop." }
        }
    }

    Write-Host ""
    Write-Host "==================== AI_LOOP_RESULT ====================" -ForegroundColor Cyan
    Write-Host "TASK=$($script:State.objective)"
    Write-Host "TASK_ID=$($script:State.task_id)"
    Write-Host "PR=$pr"
    Write-Host "HEAD=$head"
    Write-Host "ROUNDS=$($script:State.round)/$($script:State.max_rounds)"
    Write-Host "TESTS=$($script:State.tests)"
    Write-Host "CHECKS=$($script:State.checks)"
    $dsv = $script:State.deepseek_verdict; if ($null -eq $dsv) { $dsv = "NOT_RUN" }
    $cxv = $script:State.codex_verdict;    if ($null -eq $cxv) { $cxv = "NOT_RUN" }
    Write-Host "DEEPSEEK=$dsv (sha=$($script:State.deepseek_review_sha))"
    Write-Host "CODEX=$cxv (sha=$($script:State.codex_review_sha))"
    Write-Host "STATUS=$($script:State.status)"
    Write-Host "NEXT_ACTION=$nextAction"
    if (@($script:State.blocking_findings).Count -gt 0) {
        Write-Host "BLOCKING_FINDINGS:"
        foreach ($b in $script:State.blocking_findings) { Write-Host "  - $(Protect-Secret $b)" }
    }
    Write-Host "MERGE_PERFORMED=NO"
    Write-Host "DEPLOY_PERFORMED=NO"
    Write-Host "========================================================" -ForegroundColor Cyan

    # Persist run state locally. Deliberately NOT committed to main (see contract sec. 7).
    try {
        if (-not (Test-Path $script:RUN_DIR)) { New-Item -ItemType Directory -Force -Path $script:RUN_DIR | Out-Null }
        $statePath = Join-Path $script:RUN_DIR "state_$($script:State.task_id).json"
        ($script:State | ConvertTo-Json -Depth 6) | Set-Content -Path $statePath -Encoding UTF8
        Write-Info "run state: $statePath"
    } catch { }
}

# ======================================================================================
# MAIN
# ======================================================================================
function Main {
    Write-Host ""
    Write-Host "AI LOOP V1 - bounded multi-AI engineering loop" -ForegroundColor Cyan
    Write-Host "repo: $Repo   base: $BaseBranch   dry-run: $($DryRun.IsPresent)" -ForegroundColor DarkGray
    Write-Host ""

    # --- hard round clamp (applied first so even a blocked run reports the real ceiling) ---
    if ($MaxRounds -lt 1) { $MaxRounds = 1 }
    if ($MaxRounds -gt $script:HARD_MAX_ROUNDS) {
        Write-Warn2 "MaxRounds $MaxRounds exceeds the hard ceiling; clamping to $script:HARD_MAX_ROUNDS."
        $MaxRounds = $script:HARD_MAX_ROUNDS
    }
    $script:State.max_rounds = $MaxRounds

    # --- objective validation (malformed task must be rejected) ---
    if ([string]::IsNullOrWhiteSpace($Task)) {
        $script:State.status = "BLOCKED"
        Stop-Loop -Status "BLOCKED" -Reason "No -Task objective supplied. Provide a single clear engineering objective."
    }
    $trimmed = $Task.Trim()
    if ($trimmed.Length -lt 12) {
        Stop-Loop -Status "BLOCKED" -Reason "Objective is too short to be actionable (minimum 12 characters)."
    }
    if ($trimmed.Length -gt 2000) {
        Stop-Loop -Status "BLOCKED" -Reason "Objective exceeds 2000 characters."
    }
    $script:State.objective = $trimmed
    $script:State.task_id = New-TaskId -Objective $trimmed

    $script:State.status = "TASK_ACCEPTED"
    Write-Good "TASK_ACCEPTED  task_id=$($script:State.task_id)  max_rounds=$MaxRounds"

    $script:DeepSeekSecretMissing = $false
    $script:TestEvidence = @()

    Test-Preflight
    Test-GitHubAuth
    Update-Base
    Test-WriteLock
    Initialize-Branch

    $blockingText = "NONE"

    # ---- BOUNDED ROUND LOOP: strictly `for`, never `while ($true)` ----
    for ($round = 1; $round -le $script:State.max_rounds; $round++) {
        $script:State.round = $round
        Write-Host ""
        Write-Host "---------- ROUND $round / $($script:State.max_rounds) ----------" -ForegroundColor Magenta

        $claude = Invoke-ClaudeRound -BlockingFindings $blockingText

        if ($claude.Status -eq "BLOCKED") {
            Stop-Loop -Status "BLOCKED" -Reason ("CLAUDE_LOCAL reported BLOCKED: " + (@($claude.Blockers) -join "; "))
        }
        if ($claude.SafetyInvariants -eq "FAIL") {
            Stop-Loop -Status "BLOCKED" -Reason "CLAUDE_LOCAL reported SAFETY_INVARIANTS=FAIL. Refusing to proceed."
        }

        $testsPass = Invoke-DeterministicTests
        $evidenceFile = Write-EvidenceFile
        Write-Info "evidence: $evidenceFile"

        if (-not $testsPass) {
            # Tests failing can never reach review success. Next round, or stop.
            Write-Bad "Deterministic tests FAILED - not pushing, not requesting reviews."
            $script:State.status = "FIX_REQUIRED"
            $failed = @($script:TestEvidence | Where-Object { -not $_.Pass } | ForEach-Object { "Test failed: $($_.Command)" })
            $script:State.blocking_findings = $failed
            $blockingText = ($failed -join "`n")
            if ($round -ge $script:State.max_rounds) {
                Stop-Loop -Status "MAX_ROUNDS_REACHED" -Reason "Deterministic tests still failing after $round round(s)."
            }
            continue
        }
        Write-Good "Deterministic tests PASS"

        $pushed = Publish-Round
        if ($DryRun) {
            $script:State.status = "AWAITING_REVIEWS"
            Write-Warn2 "DRY RUN - stopping before live reviewer interaction."
            break
        }
        if (-not $pushed -and $null -eq $script:State.pr_number) {
            Stop-Loop -Status "BLOCKED" -Reason "Nothing was committed and no PR exists; there is nothing to review."
        }

        Sync-PullRequest
        Request-DeepSeekReview
        Request-CodexReview

        $approved = Wait-ForReviews
        if ($approved) {
            $script:State.status = "READY_TO_MERGE"
            $script:State.next_actor = "HUMAN"
            Stop-Loop -Status "READY_TO_MERGE" -Reason "Tests PASS, checks PASS, DeepSeek ACCEPT and Codex ACCEPT on $($script:State.head_sha). A human must perform the merge."
        }

        if ($script:State.deepseek_verdict -eq "BLOCKED") {
            Stop-Loop -Status "BLOCKED" -Reason ("DeepSeek review could not complete: " + (@($script:State.blocking_findings) -join "; "))
        }

        $script:State.status = "FIX_REQUIRED"
        $findings = @($script:State.blocking_findings | Where-Object { $_ })
        if ($findings.Count -eq 0) { $findings = @("Reviewers did not accept this head; re-inspect the PR conversation.") }
        $blockingText = ($findings -join "`n")
        Write-Warn2 "FIX_REQUIRED - $($findings.Count) blocking finding(s) carried into the next round."

        if ($round -ge $script:State.max_rounds) {
            Stop-Loop -Status "MAX_ROUNDS_REACHED" -Reason "Reviewers still had blocking findings after $round round(s)."
        }
    }

    if ($script:State.status -ne "READY_TO_MERGE") {
        if ($DryRun) {
            $script:State.next_action = "Dry run complete. Re-run without -DryRun to execute a live loop."
            Write-Summary
            exit 0
        }
        Stop-Loop -Status "MAX_ROUNDS_REACHED" -Reason "Loop ended without reviewer acceptance."
    }
}

# Run only when executed. Dot-sourcing (. .\ai-loop.ps1) loads the functions without
# starting a loop, so the parser and quoting helpers can be unit-tested directly.
if ($MyInvocation.InvocationName -ne '.') { Main }
