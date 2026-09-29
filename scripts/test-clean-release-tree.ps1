param(
  [string]$Guard = '.\scripts\server\assert-clean-release-tree.ps1'
)

$ErrorActionPreference = 'Stop'

$RepoRoot = Resolve-Path (Join-Path $PSScriptRoot '..')
$GuardPath = Resolve-Path (Join-Path $RepoRoot $Guard)
$TempRoot = Join-Path $env:TEMP ("ruza-clean-tree-guard-" + [guid]::NewGuid().ToString('N'))

try {
  Write-Output '=== TEST CLEAN RELEASE TREE GUARD (PowerShell) ==='
  New-Item -ItemType Directory -Path (Join-Path $TempRoot 'scripts\server') -Force | Out-Null
  Copy-Item -LiteralPath $GuardPath -Destination (Join-Path $TempRoot 'scripts\server\assert-clean-release-tree.ps1')

  Push-Location $TempRoot
  try {
    git init | Out-Null
    git config user.email 'ci@example.invalid'
    git config user.name 'CI'
    'clean' | Set-Content -LiteralPath 'README.md' -Encoding UTF8
    git add README.md scripts
    git commit -m 'initial' | Out-Null
  } finally {
    Pop-Location
  }

  & powershell -ExecutionPolicy Bypass -File (Join-Path $TempRoot 'scripts\server\assert-clean-release-tree.ps1')
  if ($LASTEXITCODE -ne 0) {
    throw "clean release tree was rejected with exit code $LASTEXITCODE"
  }
  Write-Output '[PASS] clean tree accepted'

  'dirty' | Set-Content -LiteralPath (Join-Path $TempRoot 'dirty.txt') -Encoding UTF8
  & powershell -ExecutionPolicy Bypass -File (Join-Path $TempRoot 'scripts\server\assert-clean-release-tree.ps1')
  if ($LASTEXITCODE -eq 0) {
    throw 'dirty release tree was accepted'
  }
  Write-Output '[PASS] dirty tree blocked'
} finally {
  Remove-Item -LiteralPath $TempRoot -Recurse -Force -ErrorAction SilentlyContinue
}
