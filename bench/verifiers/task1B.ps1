# Verifier: Task 1B -- same check as 1A
param([Parameter(Mandatory)][string]$TrialDir)
& "$PSScriptRoot\task1A.ps1" -TrialDir $TrialDir
