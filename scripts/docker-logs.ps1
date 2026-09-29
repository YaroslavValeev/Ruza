param(
  [switch]$Dev,
  [switch]$Follow
)
$ErrorActionPreference = 'Stop'
$repoRoot = Resolve-Path (Join-Path $PSScriptRoot '..')
Set-Location $repoRoot

$args = @('compose')
if ($Dev) {
  $args += @('-f', 'docker-compose.yml', '-f', 'docker-compose.dev.yml')
}
$args += 'logs'
if ($Follow) { $args += '-f' }

& docker @args
