# Verifier: Task 4B — same checks as 4A
param([Parameter(Mandatory)][string]$TrialDir)
& "$PSScriptRoot\task4A.ps1" -TrialDir $TrialDir
