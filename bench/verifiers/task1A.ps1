# Verifier: Task 1A
# Pass if: stats.py exists, runs cleanly, and produces all 5 required stat lines
param([Parameter(Mandatory)][string]$TrialDir)

$script = Get-ChildItem $TrialDir -Filter 'stats.py' -Recurse | Select-Object -First 1
if (-not $script) { Write-Host "FAIL: stats.py not found"; return $false }

try {
    $out = & python $script.FullName 2>&1
    if ($LASTEXITCODE -ne 0) { Write-Host "FAIL: exit $LASTEXITCODE"; return $false }
} catch {
    Write-Host "FAIL: script threw: $_"
    return $false
}

$text = ($out -join "`n").ToLower()
$required = @('mean', 'median', 'mode', 'range', 'stdev')
$missing = @()
foreach ($stat in $required) {
    if ($text -notmatch "${stat}\s*:") { $missing += $stat }
}

if ($missing.Count -gt 0) {
    Write-Host "FAIL: missing stat lines: $($missing -join ', ')"
    return $false
}

Write-Host "PASS: all 5 stats present"
return $true
