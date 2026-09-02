param(
  [switch]$Dev,
  [int]$Tail = 50
)
$ErrorActionPreference = 'Stop'
$repoRoot = Resolve-Path (Join-Path $PSScriptRoot '..')
Set-Location $repoRoot

Write-Output '=== docker compose ps ==='
if ($Dev) {
  docker compose -f docker-compose.yml -f docker-compose.dev.yml ps
} else {
  docker compose ps
}

Write-Output ''
Write-Output '=== API health ==='
try {
  Invoke-RestMethod 'http://127.0.0.1:8000/health' | ConvertTo-Json -Compress
} catch {
  Write-Output $_.Exception.Message
}

Write-Output ''
Write-Output "=== logs (tail $Tail) ==="
if ($Dev) {
  docker compose -f docker-compose.yml -f docker-compose.dev.yml logs --tail=$Tail
} else {
  docker compose logs --tail=$Tail
}
