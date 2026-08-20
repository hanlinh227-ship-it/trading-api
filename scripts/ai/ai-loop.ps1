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
# Checks that must actually report for this head before the rollup may read PASS. A
# required workflow that never starts produces no check run, so absence must not be
# mistaken for success.
$script:REQUIRED_CHECKS      = @("validate", "DeepSeek adversarial review", "AI loop safety selftest")
# Only set when reusing an existing PR (-PrNumber). Declared here so Set-StrictMode does
# not throw on the -Branch path, where there is no advertised PR head to compare against.
$script:ExpectedPrHead      = ""
# One definition of "blocking" for Codex findings, applied identically to inline comments
# and to the review summary. Asymmetry here would let the same defect block in one place
# and pass in the other. P3 is informational and deliberately excluded.
$script:CODEX_BLOCKING_PATTERN = '(?i)(\bP0\b|\bP1\b|\bP2\b|\bblocking\b|\bmust[- ]fix\b|\bcritical\b|\bbug:)'
# The independent reviewer's exact identity. A substring match on "codex" would let any
# collaborator or bot named e.g. "codex-reviewer" manufacture an ACCEPT.
$script:CODEX_BOT_LOGIN      = "chatgpt-codex-connector[bot]"
# The account the DeepSeek reviewer posts under. MUST match BOT_LOGIN in
# scripts/ai/deepseek_reviewer.py (same AI_LOOP_BOT_LOGIN override), or the reviewer
# would post a verdict the controller then refuses to admit, stalling at PENDING.
$script:REVIEW_BOT_LOGIN     = if ($env:AI_LOOP_BOT_LOGIN) { $env:AI_LOOP_BOT_LOGIN } else { "github-actions[bot]" }
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
    checks_other_failing = @()
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

    [void]$proc.Start()

    # Read both pipes with ReadToEndAsync rather than Register-ObjectEvent. The event
    # approach needs a cross-runspace callback, appends to a StringBuilder from the
    # threadpool without synchronisation, and can only be drained by sleeping after exit -
    # a race that silently truncates output and can fake a test failure. Kicking off both
    # async reads before waiting is deadlock-free (neither pipe can fill while the other
    # blocks) and each Task returns the complete stream text.
    $outTask = $proc.StandardOutput.ReadToEndAsync()
    $errTask = $proc.StandardError.ReadToEndAsync()

    if ($StdInFile -and (Test-Path $StdInFile)) {
        $content = Get-Content -Path $StdInFile -Raw -Encoding UTF8
        $proc.StandardInput.Write($content)
    }
    $proc.StandardInput.Close()

    $exited = $proc.WaitForExit($TimeoutSec * 1000)
    if (-not $exited) {
        try { $proc.Kill() } catch { }
        # Killing closes the pipes, so the readers complete; bound the wait regardless.
        $partialOut = ""
        try { if ($outTask.Wait(5000)) { $partialOut = $outTask.Result } } catch { }
        Remove-Item $outFile, $errFile -ErrorAction SilentlyContinue
        return [pscustomobject]@{ ExitCode = 124; StdOut = $partialOut; StdErr = "TIMEOUT after ${TimeoutSec}s"; TimedOut = $true }
    }

    # Process has exited; both reads are complete or about to be. Bounded, never infinite.
    $stdOut = ""
    $stdErr = ""
    if ($outTask.Wait(15000)) { $stdOut = $outTask.Result }
    else { Write-Warn2 "stdout capture did not complete within 15s for '$File'; output may be incomplete" }
    if ($errTask.Wait(15000)) { $stdErr = $errTask.Result }
    else { Write-Warn2 "stderr capture did not complete within 15s for '$File'; output may be incomplete" }
    Remove-Item $outFile, $errFile -ErrorAction SilentlyContinue

    return [pscustomobject]@{
        ExitCode = $proc.ExitCode
        StdOut   = $stdOut
        StdErr   = $stdErr
        TimedOut = $false
    }
}

function Invoke-GhJsonLines {
    <#
      gh --paginate emits ONE JSON document per page. With an array-producing --jq that
      means several concatenated arrays, and ConvertFrom-Json silently fuses them into a
      single object whose scalar properties become space-joined lists - so `.login` came
      back as every author at once and no author check could ever match.

      Asking jq for one object PER LINE instead gives newline-delimited JSON, which stays
      correct across any number of pages. Each line is parsed independently.
    #>
    param(
        [Parameter(Mandatory = $true)][string]$Path,
        [Parameter(Mandatory = $true)][string]$JqObject,
        [int]$TimeoutSec = 120
    )
    $r = Invoke-Gh -Arguments @("api", $Path, "--paginate", "--jq", ".[] | $JqObject") -TimeoutSec $TimeoutSec
    if ($r.ExitCode -ne 0) { return $null }
    $out = @()
    foreach ($line in ($r.StdOut -split "`r?`n")) {
        $t = $line.Trim()
        if (-not $t -or -not $t.StartsWith("{")) { continue }
        try { $out += ($t | ConvertFrom-Json) } catch { }
    }
    return ,$out
}

function Get-RemoteBranchSha {
    # ls-remote asks the server directly, so a locally reset ref cannot hide a push.
    $r = Invoke-Git -Arguments @("ls-remote", "origin", "refs/heads/$($script:State.branch)") -TimeoutSec 90
    if ($r.ExitCode -ne 0) { return $null }
    $line = @($r.StdOut -split "`r?`n" | Where-Object { $_ }) | Select-Object -First 1
    if (-not $line) { return "" }
    return ($line -split "\s+")[0].Trim()
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

    # `gh auth status` also fails on a transient network blip while the token is perfectly
    # valid. Reporting that as "not authenticated" would send the user to re-login for no
    # reason, so distinguish the two and retry the transient case a bounded number of times.
    $combined = ""
    $authOk = $false
    $lastReason = "unknown"
    for ($attempt = 1; $attempt -le 3; $attempt++) {
        $r = Invoke-Gh -Arguments @("auth", "status") -TimeoutSec 60
        $combined = "$($r.StdOut)$($r.StdErr)"
        if ($r.ExitCode -eq 0 -and $combined -match "Logged in to") { $authOk = $true; break }

        if ($combined -match "(?i)not logged (in|into)|no accounts|gh auth login") {
            Stop-Loop -Status "BLOCKED" -Reason "GitHub CLI is not authenticated. Run: gh auth login"
        }
        if ($combined -match "(?i)dial tcp|connection|timeout|temporary failure|network is unreachable|EOF") {
            $lastReason = "network"
            Write-Warn2 "gh auth status attempt $attempt/3 hit a network error; retrying"
        } else {
            $lastReason = "unexpected output (exit $($r.ExitCode))"
            Write-Warn2 "gh auth status attempt $attempt/3 was inconclusive; retrying"
        }
        if ($attempt -lt 3) { Start-Sleep -Seconds (2 * $attempt) }
    }
    if (-not $authOk) {
        Stop-Loop -Status "BLOCKED" -Reason "Could not verify GitHub authentication after 3 attempts ($lastReason). If you are online, check: gh auth status"
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

    # A released lock is NOT write authorization. A freed lock usually keeps its previous
    # Allowed scope text, so continuing here would let the loop implement and commit
    # against stale authorization without ever acquiring ownership - straight through the
    # repository's one-writer rule.
    if (-not $locked) {
        Stop-Loop -Status "BLOCKED" -Reason "WRITE_LOCK.md says LOCKED: false. A free lock is not write authorization; acquire the lock for this scope (LOCKED: true / OWNER: CLAUDE_LOCAL) before running the loop."
    }
    Write-Info "LOCKED: true / OWNER: $owner"
    Write-Info "SCOPE : $scope"
    if ($owner -ne "CLAUDE_LOCAL") {
        Stop-Loop -Status "BLOCKED" -Reason "WRITE_LOCK is held by '$owner', not CLAUDE_LOCAL. Refusing to write."
    }
    Write-Good "Lock held by CLAUDE_LOCAL"

    # Parse the enumerated allowed-path list. A free lock is NOT write authorization, and
    # owner-only verification is not enough either: Publish-Round runs `git add -A`, so an
    # erroneous round could otherwise commit arbitrary out-of-scope files, up to and
    # including Trading business source.
    # Parse ONLY the allowed-scope section. Scanning the whole file would also harvest
    # backticked bullets from the Protocol prose (it previously picked up
    # `--dangerously-skip-permissions`), and a prose bullet naming a real path would then
    # silently authorise it.
    $script:AllowedPaths = @()
    $inScopeSection = $false
    foreach ($line in ($lock -split "`r?`n")) {
        if ($line -match '^\s*#{1,6}\s') {
            $inScopeSection = ($line -match '(?i)allowed\s+scope')
            continue
        }
        if (-not $inScopeSection) { continue }
        $m = [regex]::Match($line, '^\s*-\s+`([^`]+)`')
        if ($m.Success) {
            $p = $m.Groups[1].Value.Trim()
            # A path, not prose: reject anything that looks like a flag or has no path shape.
            if ($p -and $p -notmatch '^-' -and $p -notmatch '\s') {
                $script:AllowedPaths += ($p -replace '\\', '/')
            }
        }
    }
    # Fail CLOSED on an empty scope. Treating "no paths parsed" as "everything allowed"
    # would silently disable the guard whenever the Allowed scope section is renamed,
    # malformed or missing - and Publish-Round's `git add -A` would then be free to stage
    # Trading business source. A free lock is not write authorization either.
    if ($script:AllowedPaths.Count -gt 0) {
        Write-Good "Lock scope enumerates $($script:AllowedPaths.Count) allowed path(s)"
    } else {
        Stop-Loop -Status "BLOCKED" -Reason "WRITE_LOCK declares no enumerated allowed paths, so this round cannot be bounded. Add an 'Allowed scope' section listing each writable path as a backticked bullet before running the loop."
    }
}

function Test-PathInLockScope {
    param([Parameter(Mandatory = $true)][string]$RelativePath)
    # No implicit allow-all: an unparsed scope is a blocker raised in Test-WriteLock, and
    # if execution ever reaches here without one, nothing is in scope.
    if (@($script:AllowedPaths).Count -eq 0) { return $false }
    $p = ($RelativePath -replace '\\', '/').Trim()
    foreach ($allowed in $script:AllowedPaths) {
        if ($p -eq $allowed) { return $true }
        # A directory entry authorises everything beneath it.
        if ($allowed.EndsWith('/') -and $p.StartsWith($allowed)) { return $true }
        if ($p.StartsWith($allowed.TrimEnd('/') + '/')) { return $true }
    }
    return $false
}

function Assert-ChangesInLockScope {
    # Runs BEFORE tests and BEFORE staging, so an out-of-scope edit can never be committed.
    $changed = @(Get-ChangedFiles)
    if ($changed.Count -eq 0) { return }

    # CI definitions are never loop-writable, whatever the lock says. For a same-repository
    # pull_request event GitHub loads the workflow from the PR HEAD, so a run that can edit
    # its own workflow can replace the review step with one that posts a forged current-SHA
    # ACCEPT using the job's `pull-requests: write` token. Checking out a trusted base pins
    # the worktree but NOT the job definition, so the only effective control is refusing to
    # author the change at all and leaving CI edits to a human.
    $workflowEdits = @($changed | Where-Object { ($_ -replace '\\', '/') -match '^\.github/workflows/' })
    if ($workflowEdits.Count -gt 0) {
        Stop-Loop -Status "BLOCKED" -Reason ("Round modified CI workflow definition(s): " + ($workflowEdits -join ", ") + ". A run that can rewrite its own CI can forge its own review verdict, so workflow changes require human authorship and review and are never made by the loop.")
    }

    $outside = @($changed | Where-Object { -not (Test-PathInLockScope -RelativePath $_) })
    if ($outside.Count -gt 0) {
        Stop-Loop -Status "BLOCKED" -Reason ("Round modified file(s) outside the declared WRITE_LOCK scope; refusing to test or stage them: " + ($outside -join ", "))
    }
    Write-Good "All $($changed.Count) changed file(s) are within the declared lock scope"
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

    # Switching branches with uncommitted work either fails obscurely or silently carries
    # edits onto the wrong branch. Refuse up front with an actionable message instead.
    $dirty = (Invoke-Git -Arguments @("status", "--porcelain")).StdOut
    if (-not [string]::IsNullOrWhiteSpace($dirty)) {
        $files = @($dirty -split "`r?`n" | Where-Object { $_ } | ForEach-Object { $_.Trim() })
        $shown = ($files | Select-Object -First 10) -join "; "
        $more = ""
        if ($files.Count -gt 10) { $more = " (+$($files.Count - 10) more)" }
        Stop-Loop -Status "BLOCKED" -Reason "Working tree is not clean; refusing to switch branches and risk carrying or losing edits. Commit or stash first. Pending: $shown$more"
    }
    Write-Good "Working tree is clean"

    if ($PrNumber -gt 0) {
        $r = Invoke-Gh -Arguments @("pr", "view", "$PrNumber", "--repo", $Repo, "--json", "headRefName,headRefOid,state")
        if ($r.ExitCode -ne 0) { Stop-Loop -Status "BLOCKED" -Reason "PR #$PrNumber could not be read." }
        $pr = $r.StdOut | ConvertFrom-Json
        if ($pr.state -ne "OPEN") { Stop-Loop -Status "BLOCKED" -Reason "PR #$PrNumber is $($pr.state), not OPEN." }
        $script:State.branch = $pr.headRefName
        $script:State.pr_number = $PrNumber
        $script:ExpectedPrHead = "$($pr.headRefOid)".Trim()
        Write-Good "Reusing PR #$PrNumber on branch $($pr.headRefName) at $($script:ExpectedPrHead)"
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

    # A reused local branch can sit AHEAD of the PR head - leftover commits from an earlier
    # run, or anything else. Checking it out unverified means the eventual push publishes
    # those pre-existing commits too, while Assert-ChangesInLockScope only ever sees
    # working-tree changes, so out-of-scope commits would bypass the declared lock
    # entirely. Require the local tip to equal the head the PR actually advertises.
    if ($script:ExpectedPrHead) {
        $localHead = (Invoke-Git -Arguments @("rev-parse", "HEAD")).StdOut.Trim()
        if ($localHead -ne $script:ExpectedPrHead) {
            Write-Warn2 "local $($script:State.branch) is at $localHead but PR #$($script:State.pr_number) advertises $($script:ExpectedPrHead); resetting to the PR head"
            [void](Invoke-Git -Arguments @("fetch", "origin", $script:State.branch))
            $reset = Invoke-Git -Arguments @("reset", "--hard", $script:ExpectedPrHead)
            if ($reset.ExitCode -ne 0) {
                Stop-Loop -Status "BLOCKED" -Reason "Local branch $($script:State.branch) is at $localHead, not the advertised PR head $($script:ExpectedPrHead), and could not be reset. Refusing to run: a later push would publish commits this round never reviewed."
            }
            $localHead = (Invoke-Git -Arguments @("rev-parse", "HEAD")).StdOut.Trim()
            if ($localHead -ne $script:ExpectedPrHead) {
                Stop-Loop -Status "BLOCKED" -Reason "Local branch $($script:State.branch) still differs from the advertised PR head after reset."
            }
        }
        Write-Good "Local branch matches the advertised PR head"
    }

    # Assert-ChangesInLockScope only inspects what THIS round changed, so a branch - or a
    # reused PR via -PrNumber - whose head already carries a workflow edit would sail past
    # it. That matters because GitHub runs the PR HEAD's workflow definition for a
    # same-repo pull_request, so such a branch could post a forged same-SHA TRUST=trusted
    # verdict the controller would then admit.
    #
    # PRIMARY CHECK: the whole commit HISTORY, not the net tree diff.
    #
    # A net tree diff is not sufficient. A workflow edited in one commit and reverted in a
    # later one nets to nothing in `git diff BASE...HEAD`, yet the branch still ran CI at
    # that intermediate head with an attacker-controlled workflow definition, and those
    # check runs remain attached to the PR where the rollup can still see them. Any commit
    # in the range is disqualifying, reverted or not.
    # --full-history is REQUIRED, not decorative. By default `git log -- <path>` applies
    # history simplification and prunes TREESAME sides of a merge. So incorporating a
    # malicious workflow commit as the second parent of a `git merge -s ours` commit leaves
    # it fully reachable in the range while `git log -- .github/workflows` prints nothing,
    # and the net tree diff is empty too. Reproduced locally: rev-list finds the commit,
    # both simplified probes return 0, --full-history returns it.
    $historyScan = Invoke-Git -Arguments @("log", "--full-history", "--format=%H", "origin/$BaseBranch..HEAD", "--", ".github/workflows")
    if ($historyScan.ExitCode -ne 0) {
        Stop-Loop -Status "BLOCKED" -Reason "Could not scan the origin/$BaseBranch..HEAD commit history for CI workflow changes. Refusing to run without that evidence."
    }
    $offendingCommits = @($historyScan.StdOut -split "`r?`n" | Where-Object { $_.Trim() })
    if ($offendingCommits.Count -gt 0) {
        $shown = (@($offendingCommits | Select-Object -First 5 | ForEach-Object { $_.Substring(0, [Math]::Min(12, $_.Length)) })) -join ", "
        $more = ""
        if ($offendingCommits.Count -gt 5) { $more = " (+$($offendingCommits.Count - 5) more)" }
        Stop-Loop -Status "BLOCKED" -Reason ("This branch's history contains $($offendingCommits.Count) commit(s) touching .github/workflows/: $shown$more. GitHub runs the PR head's workflow definition, and an intermediate head already ran CI with that definition, so the loop cannot trust its own review on this branch - even if the change was later reverted. A human must review and merge CI changes.")
    }

    # SECONDARY CHECK: the net tree diff. Strictly weaker than the history scan above and
    # kept only as defence in depth, for the case where history is shallow or grafted and
    # the log could under-report.
    $rangeDiff = Invoke-Git -Arguments @("diff", "--name-only", "origin/$BaseBranch...HEAD")
    if ($rangeDiff.ExitCode -ne 0) {
        Stop-Loop -Status "BLOCKED" -Reason "Could not diff origin/$BaseBranch...HEAD to check for committed CI workflow changes. Refusing to run without that evidence."
    }
    $committedWorkflowEdits = @($rangeDiff.StdOut -split "`r?`n" |
        Where-Object { $_ } |
        Where-Object { ($_ -replace '\\', '/') -match '^\.github/workflows/' })
    if ($committedWorkflowEdits.Count -gt 0) {
        Stop-Loop -Status "BLOCKED" -Reason ("This branch already contains committed CI workflow change(s): " + ($committedWorkflowEdits -join ", ") + ". GitHub runs the PR head's workflow definition, so the loop cannot trust its own review on this branch. A human must review and merge CI changes.")
    }
    Write-Good "No CI workflow changes anywhere in this branch's history"

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
        # `node --check` only PARSES a file; it never executes it, so it is safe even on a
        # file Claude just wrote.
        "Bash(node --check:*)"
        # Deliberately NOT granted, and this is the whole point of the list:
        #  - Bash(npm test:*)            an npm script is arbitrary code from package.json.
        #  - Bash(node scripts/ai/:*)    Claude can EDIT those scripts, so permission to run
        #                                them is permission to run anything it just wrote -
        #                                including code that shells out to `git commit` and
        #                                `git push`. A self-commit would then vanish from
        #                                Get-ChangedFiles (which compares the working tree
        #                                to the NEW HEAD), so both scope assertions would
        #                                pass while unauthorised content was already
        #                                committed.
        #  - Bash(node cloudflare-worker/validate-worker.mjs)  same escape, same reason.
        # The controller runs every deterministic test itself, so Claude never needs to
        # execute anything.
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
        "node --check <each changed .js/.mjs file>",
        "python -m py_compile <each changed .py file>",
        "git diff --check"
    )
}

function Invoke-DeterministicTests {
    Write-Step "STEP 7/12  Running deterministic tests"
    $script:State.status = "TESTING"
    $results = @()
    $allPass = $true

    # @() is required: a function returning zero or one item unrolls to $null / a bare
    # string, and under Set-StrictMode neither exposes .Count.
    $changed = @(Get-ChangedFiles)
    if ($changed.Count -gt 0) { Write-Info "changed files: $($changed -join ', ')" }
    else { Write-Info "no working-tree changes detected" }

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

    # Re-assert scope immediately before `git add -A`. Assert-ChangesInLockScope already
    # ran before the tests, but a test step can itself create files, and staging is the
    # last moment at which an out-of-scope file can still be stopped.
    Assert-ChangesInLockScope

    # Re-assert HEAD too. Removing executable paths from Claude's allowedTools does not by
    # itself close the escape: the CONTROLLER executes repo-resident validators, and those
    # files are writable under the active lock. A rewritten validator could shell out and
    # commit out-of-scope work, which would then vanish from the working tree and satisfy
    # the scope check above. Comparing HEAD to the value sampled before the round catches
    # any commit the controller did not author, whoever created it.
    if ($script:HeadBeforeRound) {
        $headNow = (Invoke-Git -Arguments @("rev-parse", "HEAD")).StdOut.Trim()
        if ($headNow -ne $script:HeadBeforeRound) {
            Stop-Loop -Status "BLOCKED" -Reason "HEAD moved from $($script:HeadBeforeRound) to $headNow during the round or its tests. Only the controller may create commits; refusing to stage on a history it did not author."
        }
    }

    # A local-only comparison is defeatable: a rewritten validator can commit, push with the
    # controller's credentials, then reset the local branch and worktree back to the saved
    # SHA before returning success. The unauthorised commit is already on the remote by
    # then, and every local check passes. So verify the REMOTE ref has not moved either.
    # $null means the probe failed; "" means the branch does not exist on the remote yet.
    # A truthiness test treats "" as "skip", which disables this guard on exactly the
    # common case - a freshly created branch. And an UNAVAILABLE probe, before or after,
    # must be a blocker rather than a skip: if ls-remote fails transiently while a
    # rewritten validator pushes and restores local HEAD, skipping leaves the unauthorised
    # remote write completely undetected. No probe, no evidence, no staging.
    if ($null -eq $script:RemoteBeforeRound) {
        Stop-Loop -Status "BLOCKED" -Reason "Could not read the remote tip of $($script:State.branch) before the round, so an unauthorised push during it cannot be ruled out. Refusing to stage without that evidence."
    }
    $remoteNow = Get-RemoteBranchSha
    if ($null -eq $remoteNow) {
        Stop-Loop -Status "BLOCKED" -Reason "Could not read the remote tip of $($script:State.branch) after the round, so an unauthorised push during it cannot be ruled out. Refusing to stage without that evidence."
    }
    if ($remoteNow -ne $script:RemoteBeforeRound) {
        Stop-Loop -Status "BLOCKED" -Reason "Remote branch $($script:State.branch) moved from '$($script:RemoteBeforeRound)' to '$remoteNow' during the round. The controller did not push; refusing to continue on a remote it did not author."
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
    # started_at and id are needed to identify the LATEST attempt per check name. Without
    # them, an old successful run keeps satisfying the gate after a rerun concluded
    # neutral/skipped/stale.
    $r = Invoke-Gh -Arguments @("api", "repos/$Repo/commits/$($script:State.head_sha)/check-runs", "--jq", "[.check_runs[] | {name, status, conclusion, started_at, id, suite: .check_suite.id}]")
    if ($r.ExitCode -ne 0) { return [pscustomobject]@{ Status = "UNKNOWN"; Failing = @() } }
    $runs = @()
    try { $runs = @($r.StdOut | ConvertFrom-Json) } catch { return [pscustomobject]@{ Status = "UNKNOWN"; Failing = @() } }
    if ($runs.Count -eq 0) { return [pscustomobject]@{ Status = "UNKNOWN"; Failing = @(); OtherFailing = @() } }

    # STEP 1 - collapse superseded attempts FIRST. Scanning every historical run before
    # this would let a cancelled earlier attempt report FAIL even though a later attempt
    # succeeded, and an unrelated in-progress run hold the rollup at PENDING forever. Two
    # workflows can also publish the same check NAME (this repo has two `validate`), so the
    # identity is (name, check_suite) and only the newest attempt in each is authoritative.
    $effective = @()
    foreach ($group in ($runs | Group-Object -Property { "$($_.name)|$($_.suite)" })) {
        $effective += @($group.Group | Sort-Object -Property @{Expression = { $_.started_at }}, @{Expression = { $_.id }} -Descending)[0]
    }

    # STEP 2 - the gate is the REQUIRED set, per the contract's "required GitHub checks
    # PASS". Every required check must be present and its latest attempt must have
    # concluded success.
    # Overlapping triggers (a pull_request run cancelled by a later workflow_dispatch)
    # produce SEPARATE check suites, so requiring every suite to succeed would let the
    # cancelled one veto the head forever. Distinguish supersede signals from real
    # failures: `cancelled`/`skipped`/`stale`/`neutral` mean "this attempt was replaced",
    # while `failure`/`timed_out`/`action_required` are genuine and must gate even if some
    # other suite of the same name went green.
    $supersededConclusions = @("cancelled", "skipped", "stale", "neutral")
    $hardFailConclusions   = @("failure", "timed_out", "action_required")

    $absent = @(); $notSuccessful = @()
    foreach ($required in $script:REQUIRED_CHECKS) {
        $matching = @($effective | Where-Object { "$($_.name)" -eq $required })
        if ($matching.Count -eq 0) { $absent += $required; continue }

        $hard    = @($matching | Where-Object { $_.status -eq "completed" -and $hardFailConclusions -contains $_.conclusion })
        $succeed = @($matching | Where-Object { $_.status -eq "completed" -and $_.conclusion -eq "success" })
        $running = @($matching | Where-Object { $_.status -ne "completed" })

        if ($hard.Count -gt 0) {
            $notSuccessful += "$required (concluded $($hard[0].conclusion))"
        } elseif ($succeed.Count -gt 0) {
            # At least one suite genuinely succeeded and nothing genuinely failed.
            continue
        } elseif ($running.Count -gt 0) {
            $notSuccessful += "$required (still $($running[0].status))"
        } else {
            $only = @($matching | ForEach-Object { "$($_.conclusion)" } | Select-Object -Unique) -join "/"
            $notSuccessful += "$required (no successful attempt; saw $only)"
        }
    }

    # STEP 3 - non-required checks are reported but do not gate. Surfacing them keeps a
    # genuine failure visible instead of silently ignored; blocking on them would let an
    # unrelated provider-side check (e.g. the Cloudflare Workers Build tracked in issue
    # #62) veto every PR in the repository forever.
    $otherFailing = @($effective |
        Where-Object { $script:REQUIRED_CHECKS -notcontains "$($_.name)" } |
        Where-Object { $_.status -eq "completed" -and @("failure", "timed_out", "cancelled", "action_required") -contains $_.conclusion } |
        ForEach-Object { "$($_.name)" } | Select-Object -Unique)
    if ($otherFailing.Count -gt 0) {
        Write-Warn2 "non-required check(s) failing (reported, not gating): $($otherFailing -join ', ')"
    }

    if ($absent.Count -gt 0) {
        Write-Warn2 "required check(s) never reported for this head: $($absent -join ', ')"
        return [pscustomobject]@{ Status = "PENDING"; Failing = @(); OtherFailing = $otherFailing }
    }
    if ($notSuccessful.Count -gt 0) {
        $stillRunning = @($notSuccessful | Where-Object { $_ -match 'still ' })
        if ($stillRunning.Count -eq $notSuccessful.Count) {
            Write-Info "required check(s) still running: $($notSuccessful -join ', ')"
            return [pscustomobject]@{ Status = "PENDING"; Failing = @(); OtherFailing = $otherFailing }
        }
        Write-Warn2 "required check(s) did not conclude success: $($notSuccessful -join ', ')"
        return [pscustomobject]@{ Status = "FAIL"; Failing = $notSuccessful; OtherFailing = $otherFailing }
    }
    return [pscustomobject]@{ Status = "PASS"; Failing = @(); OtherFailing = $otherFailing }
}

function Get-DeepSeekVerdict {
    # Authenticate the verdict. Any PR participant can write a comment containing
    # DEEPSEEK_REVIEW_BEGIN and the current SHA; without an author check a human (or a
    # compromised bot) could forge VERDICT=ACCEPT and walk the loop straight to
    # READY_TO_MERGE. Only a comment authored by the Actions bot AND carrying the
    # reviewer's own marker is admissible.
    $comments = Invoke-GhJsonLines -Path "repos/$Repo/issues/$($script:State.pr_number)/comments" -JqObject "{body, login: .user.login, type: .user.type}"
    if ($null -eq $comments) { return [pscustomobject]@{ Verdict = "PENDING"; Sha = $null; Blockers = @() } }

    $best = [pscustomobject]@{ Verdict = "PENDING"; Sha = $null; Blockers = @() }
    foreach ($c in $comments) {
        $b = $c.body
        if ($null -eq $b -or $b -notmatch "DEEPSEEK_REVIEW_BEGIN") { continue }
        if ($c.login -ne $script:REVIEW_BOT_LOGIN) {
            Write-Warn2 "ignoring a DEEPSEEK_REVIEW block from '$($c.login)' - only $($script:REVIEW_BOT_LOGIN) may issue a verdict"
            continue
        }
        if ($b -notmatch [regex]::Escape("<!-- ai-loop:deepseek-review -->")) {
            Write-Warn2 "ignoring a DEEPSEEK_REVIEW block without the reviewer comment marker"
            continue
        }
        $block = ($b -split "DEEPSEEK_REVIEW_BEGIN", 2)[1]
        $block = ($block -split "DEEPSEEK_REVIEW_END", 2)[0]
        $sha = $null; $verdict = "PENDING"; $blockers = @(); $cur = ""; $trust = "trusted"
        foreach ($line in ($block -split "`r?`n")) {
            $t = $line.Trim()
            if ([string]::IsNullOrWhiteSpace($t)) { continue }
            if ($t -match '^(HEAD_SHA|VERDICT|TRUST|BLOCKERS|NON_BLOCKING)\s*=\s*(.*)$') {
                $cur = $Matches[1]; $val = $Matches[2].Trim()
                if ($cur -eq "HEAD_SHA") { $sha = $val.ToLowerInvariant() }
                elseif ($cur -eq "TRUST") { $trust = $val.ToLowerInvariant() }
                elseif ($cur -eq "VERDICT") { $verdict = $val.ToUpperInvariant() }
                elseif ($cur -eq "BLOCKERS" -and $val -and $val.ToUpperInvariant() -ne "NONE") { $blockers += $val }
            }
            elseif ($cur -eq "BLOCKERS" -and $t.ToUpperInvariant() -ne "NONE") { $blockers += $t }
        }
        # Contract rule: ACCEPT with blockers is a contradiction; downgrade to REJECT.
        if ($verdict -eq "ACCEPT" -and $blockers.Count -gt 0) { $verdict = "REJECT" }
        # An untrusted (bootstrap) review was produced by a reviewer supplied by the very
        # change under review, so it cannot vouch for it. Findings still count against the
        # change; an acceptance does not count for it.
        if ($trust -ne "trusted" -and $verdict -eq "ACCEPT") {
            Write-Warn2 "DeepSeek review for this head is UNTRUSTED (reviewer bootstrapped from the PR head); not counting it as an acceptance"
            $verdict = "PENDING"
        }
        if ($sha -eq $script:State.head_sha.ToLowerInvariant()) {
            $best = [pscustomobject]@{ Verdict = $verdict; Sha = $sha; Blockers = $blockers }
        }
    }
    return $best
}

function Get-CodexInlineFindings {
    param([Parameter(Mandatory = $true)][string]$Sha)
    # Codex reports its actual findings as INLINE review comments, not in the review body.
    # A COMMENTED review with a bland summary can still carry several P1 defects, so the
    # inline set must be read or the controller would accept a rejected change.
    # Fail closed on an unreadable inline set. Returning the same empty array used for
    # "no findings" would let a transient GitHub error convert a bland same-head COMMENTED
    # review into ACCEPT while unread P1/P2 findings sit in the API.
    $out = @()
    $items = Invoke-GhJsonLines -Path "repos/$Repo/pulls/$($script:State.pr_number)/comments" -JqObject "{login: .user.login, type: .user.type, commit_id: .original_commit_id, current: .commit_id, path, line, body}"
    if ($null -eq $items) { return [pscustomobject]@{ Available = $false; Findings = @() } }
    foreach ($c in $items) {
        # Exact identity, not a substring: a collaborator or bot named e.g. "codex-reviewer"
        # must not be able to speak for the independent reviewer.
        if ($c.login -ne $script:CODEX_BOT_LOGIN) { continue }
        # original_commit_id is the commit the finding was actually written against.
        # Falling back to commit_id would also match a comment merely carried forward onto
        # a newer head, which is not the same claim, so require the exact original.
        $cid = $c.commit_id
        if ([string]::IsNullOrWhiteSpace($cid)) { continue }
        if ($cid.ToLowerInvariant() -ne $Sha.ToLowerInvariant()) { continue }
        $body = "$($c.body)"
        # Severity set must match Get-CodexVerdict's body scan exactly, or the same finding
        # would block when inline and pass when in the summary. P1/P2 block; P3 is
        # informational and does not.
        if ($body -match $script:CODEX_BLOCKING_PATTERN) {
            $first = ($body -split "`r?`n" | Where-Object { $_.Trim() } | Select-Object -First 2) -join " "
            $first = ($first -replace '!\[[^\]]*\]\([^)]*\)', '' -replace '<[^>]+>', '').Trim()
            $where = "$($c.path)"
            if ($c.line) { $where = "$where`:$($c.line)" }
            $out += "Codex [$where] $first"
        }
    }
    return [pscustomobject]@{ Available = $true; Findings = $out }
}

function Get-CodexVerdict {
    $reviews = Invoke-GhJsonLines -Path "repos/$Repo/pulls/$($script:State.pr_number)/reviews" -JqObject "{login: .user.login, state, commit_id, body}"
    if ($null -eq $reviews) { return [pscustomobject]@{ Verdict = "PENDING"; Sha = $null; Blockers = @() } }
    $reviews = @($reviews)

    # Aggregate EVERY same-head review before deciding. Returning on the first match let an
    # older bland COMMENTED/APPROVED entry win over a later CHANGES_REQUESTED for the same
    # SHA. Any rejection anywhere in the same-head set takes precedence.
    $sameHead = @($reviews | Where-Object {
        $_.login -eq $script:CODEX_BOT_LOGIN -and
        $null -ne $_.commit_id -and
        $_.commit_id.ToLowerInvariant() -eq $script:State.head_sha.ToLowerInvariant()
    })
    if ($sameHead.Count -eq 0) { return [pscustomobject]@{ Verdict = "PENDING"; Sha = $null; Blockers = @() } }

    $sha = $script:State.head_sha
    $inlineResult = Get-CodexInlineFindings -Sha $sha
    if (-not $inlineResult.Available) {
        Write-Warn2 "Codex inline comments could not be read; holding the verdict at PENDING rather than assuming there are none"
        return [pscustomobject]@{ Verdict = "PENDING"; Sha = $null; Blockers = @() }
    }
    $blockers = @($inlineResult.Findings)

    foreach ($rev in $sameHead) {
        if ($rev.state -eq "CHANGES_REQUESTED") {
            $summary = "Codex requested changes"
            if ($rev.body) { $summary = ($rev.body -split "`r?`n" | Where-Object { $_.Trim() } | Select-Object -First 4) -join " " }
            $blockers = @($summary) + $blockers
        }
        elseif ($rev.body -and $rev.body -match $script:CODEX_BLOCKING_PATTERN) {
            $blockers += (($rev.body -split "`r?`n" | Where-Object { $_.Trim() } | Select-Object -First 4) -join " ")
        }
    }
    if ($blockers.Count -gt 0) {
        return [pscustomobject]@{ Verdict = "REJECT"; Sha = $sha; Blockers = @($blockers | Select-Object -Unique) }
    }
    return [pscustomobject]@{ Verdict = "ACCEPT"; Sha = $sha; Blockers = @() }
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
        # Non-required failures do not gate, but the contract promises they stay visible.
        $script:State.checks_other_failing = @($checks.OtherFailing)

        # A skipped reviewer is NEVER synthesised into an acceptance. -SkipDeepSeek /
        # -SkipCodex are rehearsal switches, rejected outside -DryRun at startup; if one is
        # somehow set here the verdict stays PENDING so the READY gate cannot be satisfied
        # without the contractually required independent review.
        $ds = Get-DeepSeekVerdict
        if ($SkipDeepSeek) { $ds = [pscustomobject]@{ Verdict = "PENDING"; Sha = $null; Blockers = @() } }
        $script:State.deepseek_verdict = $ds.Verdict
        $script:State.deepseek_review_sha = $ds.Sha

        $cx = Get-CodexVerdict
        if ($SkipCodex) { $cx = [pscustomobject]@{ Verdict = "PENDING"; Sha = $null; Blockers = @() } }
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
        # Both reviewer SHAs are always required to equal the head. No skip switch may
        # relax this - the switches are rehearsal-only and already force PENDING above.
        $shaFresh = $true
        if ($null -eq $ds.Sha -or $ds.Sha.ToLowerInvariant() -ne $script:State.head_sha.ToLowerInvariant()) { $shaFresh = $false }
        if ($null -eq $cx.Sha -or $cx.Sha.ToLowerInvariant() -ne $script:State.head_sha.ToLowerInvariant()) { $shaFresh = $false }

        if ($bothAccepted -and $shaFresh -and $checks.Status -eq "PASS" -and $script:State.tests -eq "PASS") {
            # Revalidate the live PR head before declaring readiness. If another push landed
            # while we were polling, everything above describes an obsolete commit, and
            # returning READY would hand the human a newer, entirely unreviewed head.
            $live = Invoke-Gh -Arguments @("pr", "view", "$($script:State.pr_number)", "--repo", $Repo, "--json", "headRefOid", "--jq", ".headRefOid")
            $liveSha = $live.StdOut.Trim()
            if ($live.ExitCode -ne 0 -or [string]::IsNullOrWhiteSpace($liveSha)) {
                Write-Warn2 "could not revalidate the live PR head; refusing to declare readiness on an unconfirmed head"
                $script:State.blocking_findings = @("Could not confirm the live PR head before declaring READY_TO_MERGE.")
                return $false
            }
            if ($liveSha.ToLowerInvariant() -ne $script:State.head_sha.ToLowerInvariant()) {
                Write-Warn2 "PR head advanced to $liveSha during polling; the reviews above describe $($script:State.head_sha)"
                $script:State.blocking_findings = @("PR head advanced to $liveSha while reviews were being collected; $($script:State.head_sha) is no longer the head.")
                return $false
            }
            return $true
        }
        if ($checks.Status -eq "FAIL") {
            $script:State.blocking_findings = @("Failing GitHub checks: " + ($checks.Failing -join ", "))
            return $false
        }
        # Clamp the wait so a fixed interval can never overshoot the deadline.
        $remaining = [int]([Math]::Ceiling(($deadline - (Get-Date)).TotalSeconds))
        if ($remaining -le 0) { break }
        Start-Sleep -Seconds ([Math]::Min($PollIntervalSec, $remaining))
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
    if (@($script:State.checks_other_failing).Count -gt 0) {
        Write-Host "CHECKS_OTHER_FAILING=$(@($script:State.checks_other_failing) -join ', ') (reported, not gating)"
    }
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
        # Serialise in the shape AI_LOOP_STATE.schema.json declares: `tests` and `checks`
        # are objects with a `status` property, not bare strings. Emitting strings would
        # make every persisted state file fail validation against its own contract.
        $serialisable = [ordered]@{}
        foreach ($k in $script:State.Keys) { $serialisable[$k] = $script:State[$k] }
        $serialisable["tests"] = [ordered]@{
            status   = $script:State.tests
            commands = @(@($script:TestEvidence) | Where-Object { $_ } | ForEach-Object {
                [ordered]@{ command = $_.Command; exit_code = $(if ($_.Pass) { 0 } else { 1 }) }
            })
        }
        # Nested under `checks`, not a new top-level key: the schema is
        # additionalProperties:false, so an extra top-level field would invalidate every
        # persisted state file.
        $serialisable.Remove("checks_other_failing") | Out-Null
        $serialisable["checks"] = [ordered]@{
            status        = $script:State.checks
            other_failing = @($script:State.checks_other_failing)
        }
        # blocking_findings are accumulated as plain strings by Stop-Loop, test failures,
        # check failures and reviewer findings alike, but the schema requires each item to
        # be an object with `source` and `summary`. Classify on the way out so a persisted
        # rejected/blocked run still validates against its own contract.
        $serialisable["blocking_findings"] = @(@($script:State.blocking_findings) | Where-Object { $_ } | ForEach-Object {
            $text = "$_"
            $source = "CONTROLLER"
            if ($text -match '^Codex ')                  { $source = "CODEX" }
            elseif ($text -match '(?i)^deepseek|DeepSeek review') { $source = "DEEPSEEK" }
            elseif ($text -match '(?i)^test failed')     { $source = "TESTS" }
            elseif ($text -match '(?i)^failing github checks|required check') { $source = "CHECKS" }
            [ordered]@{ source = $source; summary = $text }
        })
        ($serialisable | ConvertTo-Json -Depth 6) | Set-Content -Path $statePath -Encoding UTF8
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

    # Rehearsal switches must not exist on a live run: skipping a reviewer there would
    # remove a contractually required independent review from the READY gate.
    if (-not $DryRun) {
        if ($SkipDeepSeek) { Stop-Loop -Status "BLOCKED" -Reason "-SkipDeepSeek is a rehearsal switch and may only be used with -DryRun. A live loop requires the adversarial review." }
        if ($SkipCodex)    { Stop-Loop -Status "BLOCKED" -Reason "-SkipCodex is a rehearsal switch and may only be used with -DryRun. A live loop requires the independent review." }
    }

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

        # Claude must never create a commit. If HEAD moves during its round, something
        # executed a git write on its behalf and the scope assertions - which compare the
        # working tree to the CURRENT HEAD - would no longer see the smuggled change.
        # Script-scoped so Publish-Round can re-check it after the tests have run, which is
        # where the controller executes repo-resident (and therefore editable) validators.
        $script:HeadBeforeRound = (Invoke-Git -Arguments @("rev-parse", "HEAD")).StdOut.Trim()
        $script:RemoteBeforeRound = Get-RemoteBranchSha

        $claude = Invoke-ClaudeRound -BlockingFindings $blockingText

        $headAfterRound = (Invoke-Git -Arguments @("rev-parse", "HEAD")).StdOut.Trim()
        if ($headAfterRound -ne $script:HeadBeforeRound) {
            Stop-Loop -Status "BLOCKED" -Reason "HEAD moved from $($script:HeadBeforeRound) to $headAfterRound during the implementation round. Only the controller may create commits; refusing to continue on a self-committed history."
        }

        # Fail closed on the implementer's report. An absent or malformed result block
        # leaves Status/SafetyInvariants as UNKNOWN, which is NOT a pass: it means the
        # round is unverified. Blockers must also stop the loop even when the model
        # neglected to set STATUS=BLOCKED alongside them.
        if ($claude.Status -eq "BLOCKED") {
            Stop-Loop -Status "BLOCKED" -Reason ("CLAUDE_LOCAL reported BLOCKED: " + (@($claude.Blockers) -join "; "))
        }
        if ($claude.SafetyInvariants -ne "PASS") {
            Stop-Loop -Status "BLOCKED" -Reason "CLAUDE_LOCAL did not affirm SAFETY_INVARIANTS=PASS (got '$($claude.SafetyInvariants)'). An unverified safety claim is treated as a failure."
        }
        if (@($claude.Blockers).Count -gt 0) {
            Stop-Loop -Status "BLOCKED" -Reason ("CLAUDE_LOCAL reported blocker(s): " + (@($claude.Blockers) -join "; "))
        }
        if (-not $DryRun -and @("IMPLEMENTED", "NO_CHANGE_NEEDED") -notcontains $claude.Status) {
            Stop-Loop -Status "BLOCKED" -Reason "CLAUDE_LOCAL returned an unverified round (STATUS='$($claude.Status)'). Expected IMPLEMENTED or NO_CHANGE_NEEDED."
        }

        # Bound the round to the declared lock scope BEFORE anything is tested or staged.
        Assert-ChangesInLockScope

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
