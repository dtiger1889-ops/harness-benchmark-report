# run-trial.ps1 -- Harness Benchmark Trial Runner
# Usage: .\run-trial.ps1 -Task 1A -Condition H0 -TrialNum 1

param(
    [Parameter(Mandatory)][ValidateSet('1A','1B','2A','2B','3','4A','4B','4C')]
    [string]$Task,

    [Parameter(Mandatory)][ValidateSet('H0','H1')]
    [string]$Condition,

    [Parameter(Mandatory)][int]$TrialNum,

    [string]$Model = 'claude-sonnet-4-6',
    [int]$WallTimeLimitSeconds = 900,
    [switch]$DryRun,

    # Root of the bench tree. Defaults to the folder this script lives in, so the
    # bench is portable -- clone it anywhere and the paths below resolve.
    [string]$BenchRoot = $PSScriptRoot
)

$ErrorActionPreference = 'Stop'
$ResultsCsv = "$BenchRoot\results.csv"
$TrialName  = "trial-$TrialNum-$Condition-task$Task"
$TrialDir   = "$BenchRoot\trials\$TrialName"
$SessionLog = "$TrialDir\session.jsonl"

if ($DryRun) { Write-Host "[DRY RUN] $TrialName -- results.csv will NOT be updated" -ForegroundColor Yellow }

# --- 1. Materialize trial directory ---
if (Test-Path $TrialDir) { Remove-Item $TrialDir -Recurse -Force }

$TemplateBase = if ($Condition -eq 'H0') {
    "$BenchRoot\templates\H0-task$Task"
} else {
    "$BenchRoot\templates\H1-task$Task"
}

if (-not (Test-Path $TemplateBase)) {
    $GenericBase = if ($Condition -eq 'H0') {
        "$BenchRoot\templates\H0-empty"
    } else {
        "$BenchRoot\templates\H1-base"
    }
    Copy-Item $GenericBase $TrialDir -Recurse
    $SeedDir = "$BenchRoot\templates\seeds\task$Task"
    if (Test-Path $SeedDir) {
        Copy-Item "$SeedDir\*" $TrialDir -Recurse -Force
    }
} else {
    Copy-Item $TemplateBase $TrialDir -Recurse
}

# --- 2. Read prompt ---
$PromptFile = "$BenchRoot\prompts\task$Task.txt"
if (-not (Test-Path $PromptFile)) {
    Write-Error "Prompt file not found: $PromptFile"
    exit 1
}
$Prompt = Get-Content $PromptFile -Raw

# --- 3. Capture environment metadata ---
$ClaudeVersion = (claude --version 2>$null) -join ' '
$StartTime     = [System.DateTime]::UtcNow
$StartIso      = $StartTime.ToString('yyyy-MM-ddTHH:mm:ssZ')
Write-Host "[$StartIso] Starting $TrialName  model=$Model"

# --- 4. Run claude headlessly ---
$env:CLAUDE_MODEL = $Model
$ExitCode = 0

$ScriptBlock = {
    param($ClaudeExe, $TrialDir, $Prompt, $SessionLog, $Model)
    $env:CLAUDE_MODEL = $Model
    Set-Location -LiteralPath $TrialDir
    $args_list = @(
        '--add-dir', $TrialDir,
        '--permission-mode', 'acceptEdits',
        '--allowedTools', 'Read,Edit,Write,Bash,Glob,Grep',
        '--output-format', 'stream-json',
        '--verbose',
        '--no-session-persistence',
        '-p', $Prompt
    )
    & $ClaudeExe @args_list | Out-File -FilePath $SessionLog -Encoding utf8
}

$Job = Start-Job -ScriptBlock $ScriptBlock `
    -ArgumentList 'claude', $TrialDir, $Prompt, $SessionLog, $Model

$Finished = Wait-Job $Job -Timeout $WallTimeLimitSeconds
if (-not $Finished) {
    Stop-Job $Job
    Remove-Job $Job -Force
    Write-Warning "[$TrialName] Wall-time limit ($WallTimeLimitSeconds s) reached -- failed"
    $ExitCode = 99
} else {
    Receive-Job $Job | Out-Null
    Remove-Job $Job -Force
    $ExitCode = 0
}

$EndTime   = [System.DateTime]::UtcNow
$DurationS = [int]($EndTime - $StartTime).TotalSeconds

# --- 5. Run verifier ---
$VerifierScript = "$BenchRoot\verifiers\task$Task.ps1"
$Passed = 0
if (Test-Path $VerifierScript) {
    try {
        $result = & $VerifierScript -TrialDir $TrialDir
        if ($result -eq $true -or $result -eq 'PASS') {
            $Passed = 1
        } else {
            $Passed = 0
        }
    } catch {
        $Passed = 0
        Write-Warning "Verifier threw: $_"
    }
} else {
    Write-Warning "No verifier for task $Task -- marking unchecked (-1)"
    $Passed = -1
}

Write-Host "[$TrialName] done in ${DurationS}s  passed=$Passed"

# --- 6. Parse token metrics from JSONL ---
$TotalInput       = 0
$TotalOutput      = 0
$TotalCacheRead   = 0
$TotalCacheCreate = 0
$PeakContext      = 0
$TurnCount        = 0   # = turn_blocks: every usage-bearing jsonl row (raw count)
$TurnLogical      = 0   # distinct message.id values; collapses multi-block responses (text + tool_use) to one turn
$MessageIds       = New-Object 'System.Collections.Generic.HashSet[string]'
$CompactionEvents = 0

if (Test-Path $SessionLog) {
    foreach ($line in (Get-Content $SessionLog)) {
        try {
            $obj = $line | ConvertFrom-Json
        } catch {
            continue
        }

        $msg = $null
        if ($obj.message) {
            $msg = $obj.message
        } elseif ($obj.type -eq 'assistant') {
            $msg = $obj
        }
        if (-not $msg) { continue }

        if ($msg.usage) {
            $u   = $msg.usage
            $inp = [int]($u.input_tokens -as [int])
            $out = [int]($u.output_tokens -as [int])
            $cr  = [int]($u.cache_read_input_tokens -as [int])
            $cc  = [int]($u.cache_creation_input_tokens -as [int])

            $TotalInput       += $inp
            $TotalOutput      += $out
            $TotalCacheRead   += $cr
            $TotalCacheCreate += $cc
            $TurnCount++
            if ($msg.id) { [void]$MessageIds.Add([string]$msg.id) }

            $ctx = $inp + $cr + $cc
            if ($ctx -gt $PeakContext) { $PeakContext = $ctx }
        }

        if ($msg.content -is [array]) {
            foreach ($block in $msg.content) {
                if ($block.type -eq 'text' -and $block.text -match 'compacted|summarized') {
                    $CompactionEvents++
                }
            }
        }
    }
}

$TurnLogical = $MessageIds.Count

# --- 7. Append row to results.csv ---
# Schema note: turn_count is the raw usage-row count (a.k.a. turn_blocks);
# turn_logical dedupes by message.id so multi-block responses collapse to one
# turn. Older rows pre-2026-05-22 have turn_count populated but turn_logical
# blank -- analyze.py treats missing values as None.
$Header = 'trial_name,task,condition,trial_num,model,claude_version,start_iso,duration_s,' +
          'total_input,total_output,cache_read,cache_create,peak_context,turn_count,' +
          'compaction_events,passed,turn_logical'

if (-not (Test-Path $ResultsCsv)) {
    $Header | Out-File $ResultsCsv -Encoding utf8
}

$Row = "$TrialName,$Task,$Condition,$TrialNum,$Model,`"$ClaudeVersion`",$StartIso,$DurationS," +
       "$TotalInput,$TotalOutput,$TotalCacheRead,$TotalCacheCreate,$PeakContext,$TurnCount," +
       "$CompactionEvents,$Passed,$TurnLogical"

if ($DryRun) {
    Write-Host "[DRY RUN] Skipping CSV append. Row would have been: $Row" -ForegroundColor Yellow
} else {
    $Row | Out-File $ResultsCsv -Append -Encoding utf8
    Write-Host "Row appended to $ResultsCsv"
}

# --- 8. Archive session JSONL before cleanup ---
$ArchiveDir = "$BenchRoot\sessions-archive"
if (-not (Test-Path $ArchiveDir)) { mkdir $ArchiveDir | Out-Null }
if (Test-Path $SessionLog) {
    Copy-Item $SessionLog "$ArchiveDir\$TrialName.jsonl" -Force
    Write-Host "Archived: $ArchiveDir\$TrialName.jsonl"
}

# --- 9. Archive full trial folder before cleanup ---
$TrialArchiveDir = "$BenchRoot\trials-archive"
if (-not (Test-Path $TrialArchiveDir)) { mkdir $TrialArchiveDir | Out-Null }
if (Test-Path $TrialDir) {
    $DestPath = "$TrialArchiveDir\$TrialName"
    if (Test-Path $DestPath) { Remove-Item $DestPath -Recurse -Force }
    Copy-Item $TrialDir $DestPath -Recurse -Force
    Write-Host "Archived folder: $DestPath"
}

# --- 10. Clean up trial directory (optional: set to $false to keep trials) ---
$CleanupTrials = $true
if ($CleanupTrials -and (Test-Path $TrialDir)) {
    Remove-Item $TrialDir -Recurse -Force
}
