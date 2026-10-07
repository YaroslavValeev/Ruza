param(
  [Parameter(Mandatory = $true)]
  [string]$BackupDir,
  [string]$TargetSpreadsheetId = "",
  [switch]$Write,
  # Disaster recovery only: allow -Write into SPREADSHEET_ID / INTAKE_SPREADSHEET_ID.
  # The Python script still asks to type 'OVERWRITE <ENV_NAME>' interactively.
  [switch]$AllowProdTarget
)

$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent $PSScriptRoot
Set-Location $Root
$env:PYTHONPATH = Join-Path $Root "icebeach-wakeclub"

$argsList = @("scripts/restore_sheets_backup.py", "--backup-dir", $BackupDir)
if ($TargetSpreadsheetId.Trim()) {
  $argsList += @("--target-spreadsheet-id", $TargetSpreadsheetId.Trim())
}
if ($Write) {
  $argsList += "--write"
}
if ($AllowProdTarget) {
  $argsList += "--allow-prod-target"
}

python @argsList
exit $LASTEXITCODE
