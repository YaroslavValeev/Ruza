param(
  [switch]$Dev
)
$ErrorActionPreference = 'Stop'
$repoRoot = Resolve-Path (Join-Path $PSScriptRoot '..')
Set-Location $repoRoot

$args = @('compose', 'down')
if ($Dev) {
  $args = @('compose', '-f', 'docker-compose.yml', '-f', 'docker-compose.dev.yml', 'down')
}
& docker @args
Write-Output 'Docker stack stopped.'
