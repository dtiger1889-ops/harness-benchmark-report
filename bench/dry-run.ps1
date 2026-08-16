# dry-run.ps1 — Smoke test for the benchmark pipeline
# Runs one H0 and one H1 trial of Task 1A, then calls analyze.py.
# If this succeeds end-to-end, the measurement pipeline is working.

$ErrorActionPreference = 'Stop'
$BenchRoot = $PSScriptRoot

Write-Host "=== Benchmark Dry-Run ===" -ForegroundColor Cyan
Write-Host "Running H0 Task 1A (trial 0)..."
& "$BenchRoot\run-trial.ps1" -Task 1A -Condition H0 -TrialNum 0

Write-Host ""
Write-Host "Running H1 Task 1A (trial 0)..."
& "$BenchRoot\run-trial.ps1" -Task 1A -Condition H1 -TrialNum 0

Write-Host ""
Write-Host "Checking results.csv..."
$csv = Import-Csv "$BenchRoot\results.csv"
Write-Host "  Rows: $($csv.Count)"
foreach ($row in $csv) {
    Write-Host "  $($row.trial_name): input=$($row.total_input) passed=$($row.passed)"
}

Write-Host ""
Write-Host "Running analyze.py..."
python "$BenchRoot\analyze.py" --csv "$BenchRoot\results.csv"

Write-Host ""
Write-Host "=== Dry-run complete ===" -ForegroundColor Green
Write-Host "If both trials show token counts > 0 and analyze.py ran without errors, you are ready for Phase 1."
