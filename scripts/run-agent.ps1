param(
  [Parameter(Mandatory = $true)]
  [ValidateSet('preflight_guard', 'late_marker', 'shift_snapshot', 'ops_alert', 'daily_brief', 'intake_sync', 'shift_reminders')]
  [string]$Agent,
  [ValidateSet('morning', 'evening')]
  [string]$Mode = 'morning'
)

$ErrorActionPreference = 'Stop'
$RepoRoot = Split-Path $PSScriptRoot -Parent
$IcebeachRoot = Join-Path $RepoRoot 'icebeach-wakeclub'
$PreviousPythonPath = $env:PYTHONPATH

Push-Location $IcebeachRoot
try {
  $env:PYTHONPATH = '.'
  if ($Agent -eq 'daily_brief') {
    python -m apps.agents.cli run --agent $Agent --mode $Mode
  } else {
    python -m apps.agents.cli run --agent $Agent
  }
  if ($LASTEXITCODE -ne 0) {
    throw "Agent $Agent failed with exit code $LASTEXITCODE"
  }
} finally {
  $env:PYTHONPATH = $PreviousPythonPath
  Pop-Location
}
