param(
  [string]$Date = (Get-Date -Format 'yyyy-MM-dd'),
  [int]$ApiPort = 8000
)
$ErrorActionPreference = 'Stop'

$checkScript = Join-Path $PSScriptRoot 'preflight_check.py'

Write-Output "=== PREFLIGHT DATE ==="
Write-Output $Date
Write-Output ''
Write-Output "=== HEALTH ==="
try {
  $health = Invoke-RestMethod -Uri "http://127.0.0.1:$ApiPort/health" -TimeoutSec 5
  $health | ConvertTo-Json -Compress
  if ($health.status -ne 'ok' -or $health.app -ne 'icebeach-wakeclub-api') {
    throw "Unexpected API health payload. Expected icebeach-wakeclub-api on port $ApiPort."
  }
} catch {
  Write-Output $_.Exception.Message
  exit 1
}
Write-Output ''
Write-Output "=== PREFLIGHT CHECK ==="
python $checkScript --date $Date
