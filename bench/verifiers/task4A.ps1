# Verifier: Task 4A + 4B
# Pass if: a new project folder was created AND a script exists in it that
# imports or references data from the two relevant sibling projects.
param([Parameter(Mandatory)][string]$TrialDir)

# New project folder must exist (not one of the 5 seed folders)
$seedFolders = @('proj-alpha','proj-beta','proj-gamma','proj-relevant-1','proj-relevant-2')
$allFolders  = Get-ChildItem $TrialDir -Directory
$newFolders  = $allFolders | Where-Object { $_.Name -notin $seedFolders }

if (-not $newFolders) {
    Write-Host "FAIL: no new project folder created"
    return $false
}

# A python script must exist in the new folder
$script = $newFolders | ForEach-Object {
    Get-ChildItem $_.FullName -Filter '*.py' -Recurse
} | Select-Object -First 1

if (-not $script) {
    Write-Host "FAIL: no .py script found in new folder ($($newFolders.Name -join ', '))"
    return $false
}

# Script must reference relevant project data (loose check: mentions 'relevant' or reads a file from those dirs)
$content = Get-Content $script.FullName -Raw
if ($content -match 'relevant|proj.relevant') {
    Write-Host "PASS: script in $($script.Directory.Name) references relevant project data"
    return $true
}

# Also try running it
try {
    $out = & python $script.FullName 2>&1
    if ($LASTEXITCODE -eq 0 -and ($out -join '').Trim().Length -gt 0) {
        Write-Host "PASS: script ran successfully"
        return $true
    }
} catch {}

Write-Host "FAIL: script exists but doesn't reference relevant projects and failed to run cleanly"
return $false
