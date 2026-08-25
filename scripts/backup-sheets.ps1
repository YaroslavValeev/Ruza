param(
  [string]$SpreadsheetId = "",
  [string]$OutDir = "backups/sheets"
)

$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent $PSScriptRoot
Set-Location $Root
$env:PYTHONPATH = Join-Path $Root "icebeach-wakeclub"

$argsList = @("scripts/backup_sheets.py", "--out-dir", $OutDir)
if ($SpreadsheetId.Trim()) {
  $argsList += @("--spreadsheet-id", $SpreadsheetId.Trim())
}

python @argsList
