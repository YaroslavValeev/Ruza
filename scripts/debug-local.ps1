$ErrorActionPreference = 'Stop'

$repoRoot = Resolve-Path (Join-Path $PSScriptRoot '..\icebeach-wakeclub')
$apiDir = Join-Path $repoRoot 'apps\api'
$apiOut = Join-Path $apiDir '.runlogs\api-8000.out.log'
$apiErr = Join-Path $apiDir '.runlogs\api-8000.err.log'
$debugPy = Join-Path $PSScriptRoot 'debug_local.py'

Write-Output '=== PORTS ==='
netstat -ano | Select-String ':8000|:5173'

Write-Output "`n=== HEALTH ==="
try {
  Invoke-WebRequest -UseBasicParsing 'http://127.0.0.1:8000/health' | Select-Object -ExpandProperty Content
} catch {
  Write-Output $_.Exception.Message
}

Write-Output "`n=== API OUT (tail 40) ==="
if (Test-Path $apiOut) {
  Get-Content $apiOut -Tail 40
} else {
  Write-Output 'api out log not found'
}

Write-Output "`n=== API ERR (tail 40) ==="
if (Test-Path $apiErr) {
  Get-Content $apiErr -Tail 40
} else {
  Write-Output 'api err log not found'
}

Write-Output "`n=== DUPLICATE BOOKINGS ==="
python $debugPy
