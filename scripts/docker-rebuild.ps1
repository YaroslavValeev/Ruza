param(
  [switch]$Dev,
  [ValidateSet('all', 'api', 'dashboard')]
  [string]$Target = 'all'
)
$ErrorActionPreference = 'Stop'
$repoRoot = Resolve-Path (Join-Path $PSScriptRoot '..')
Set-Location $repoRoot

& (Join-Path $PSScriptRoot 'docker-sync-env.ps1') -Force

$compose = @('compose', '--env-file', '.env.docker')
if ($Dev) {
  $compose += @('-f', 'docker-compose.yml', '-f', 'docker-compose.dev.yml')
} else {
  $compose += @('-f', 'docker-compose.yml')
}

if ($Target -eq 'all' -or $Target -eq 'api') {
  & docker @compose build api --no-cache
}
if ($Target -eq 'all' -or $Target -eq 'dashboard') {
  & docker @compose build dashboard --no-cache
}

& docker @compose up -d
Write-Output "Rebuilt: $Target"
