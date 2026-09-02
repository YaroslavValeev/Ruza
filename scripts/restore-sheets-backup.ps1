param(
  [Parameter(Mandatory = $true)]
  [string]$BackupDir,
  [string]$TargetSpreadsheetId = "",
  [switch]$Write
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

python @argsList
