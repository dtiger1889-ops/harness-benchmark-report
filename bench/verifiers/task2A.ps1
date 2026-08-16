# Verifier: Task 2A + 2B
# Pass if: a .csv file exists with populated rows (>1 row = header + data) and
# headers match the template headers.
param([Parameter(Mandatory)][string]$TrialDir)

# Find the template CSV to compare headers
$template = Get-ChildItem $TrialDir -Filter '*template*' -Recurse | Select-Object -First 1
if (-not $template) {
    # Fall back: look for any CSV named 'template'
    $template = Get-ChildItem $TrialDir -Filter '*.csv' -Recurse |
                Where-Object { $_.Name -match 'template' } | Select-Object -First 1
}

# Find the output CSV (non-template)
$outputCsv = Get-ChildItem $TrialDir -Filter '*.csv' -Recurse |
             Where-Object { $_.Name -notmatch 'template' } | Select-Object -First 1

if (-not $outputCsv) { Write-Host "FAIL: no output CSV found"; return $false }

$rows = Import-Csv $outputCsv.FullName
if ($rows.Count -lt 1) { Write-Host "FAIL: CSV is empty (no data rows)"; return $false }

if ($template) {
    $tHeaders = (Get-Content $template.FullName -TotalCount 1) -split ','
    $oHeaders = (Get-Content $outputCsv.FullName -TotalCount 1) -split ','
    $missing = $tHeaders | Where-Object { $_ -notin $oHeaders }
    if ($missing) {
        Write-Host "FAIL: output CSV missing template headers: $($missing -join ', ')"
        return $false
    }
}

Write-Host "PASS: $($rows.Count) data rows in $($outputCsv.Name)"
return $true
