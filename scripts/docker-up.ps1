param(
  [string]$EnvFile = ".env.docker"
)
$ErrorActionPreference = 'Stop'
$repoRoot = Resolve-Path (Join-Path $PSScriptRoot '..')
Set-Location $repoRoot
docker compose --env-file $EnvFile up --build -d
Write-Output "API: http://127.0.0.1:8000/health"
Write-Output "Dashboard: http://127.0.0.1:5173"
