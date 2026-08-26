param(
  [string]$ExternalRecordId = '',
  [string]$FullName = 'Smoke Intake E2E',
  [string]$Phone = ''
)

$ErrorActionPreference = 'Stop'
$RepoRoot = Split-Path $PSScriptRoot -Parent
$IcebeachRoot = Join-Path $RepoRoot 'icebeach-wakeclub'

$argsList = @()
if ($ExternalRecordId) {
  $argsList += @('--external-record-id', $ExternalRecordId)
}
if ($FullName) {
  $argsList += @('--full-name', $FullName)
}
if ($Phone) {
  $argsList += @('--phone', $Phone)
}

Push-Location $RepoRoot
try {
  $env:PYTHONPATH = $IcebeachRoot
  python (Join-Path $RepoRoot 'scripts\intake_e2e.py') @argsList
  if ($LASTEXITCODE -ne 0) {
    throw "intake E2E failed with exit code $LASTEXITCODE"
  }
} finally {
  Pop-Location
}
