param(
  [string]$Date = (Get-Date -Format 'yyyy-MM-dd')
)
$ErrorActionPreference = 'Stop'

$checkScript = Join-Path $PSScriptRoot 'preflight_check.py'

Write-Output "=== PREFLIGHT DATE ==="
Write-Output $Date
Write-Output ''
Write-Output "=== HEALTH ==="
try {
  Invoke-WebRequest -UseBasicParsing 'http://127.0.0.1:8000/health' | Select-Object -ExpandProperty Content
} catch {
  Write-Output $_.Exception.Message
}
Write-Output ''
Write-Output "=== PREFLIGHT CHECK ==="
python $checkScript --date $Date
