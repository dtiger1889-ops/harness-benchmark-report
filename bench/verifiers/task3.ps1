# Verifier: Task 3 — half-finished script must be completed and pass its functional check
# The seed directory contains a verify_task3.py that raises SystemExit(0) on success.
param([Parameter(Mandatory)][string]$TrialDir)

$verifyScript = Get-ChildItem $TrialDir -Filter 'verify_task3.py' -Recurse | Select-Object -First 1
if (-not $verifyScript) {
    # Fall back: just check that main script runs without error
    $scripts = Get-ChildItem $TrialDir -Filter 'main.py' -Recurse | Select-Object -First 1
    if (-not $scripts) { $scripts = Get-ChildItem $TrialDir -Filter '*.py' -Recurse | Select-Object -First 1 }
    if (-not $scripts) { Write-Host "FAIL: no python script found"; return $false }
    try {
        $out = & python $scripts.FullName 2>&1
        $exit = $LASTEXITCODE
        if ($exit -eq 0) { Write-Host "PASS: script exited 0"; return $true }
        else { Write-Host "FAIL: exit code $exit"; return $false }
    } catch {
        Write-Host "FAIL: $_"; return $false
    }
}

try {
    & python $verifyScript.FullName 2>&1 | Write-Host
    if ($LASTEXITCODE -eq 0) { Write-Host "PASS"; return $true }
    else { Write-Host "FAIL: verify_task3.py exited $LASTEXITCODE"; return $false }
} catch {
    Write-Host "FAIL: $_"; return $false
}
