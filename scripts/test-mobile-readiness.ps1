param()

$ErrorActionPreference = 'Stop'
$RepoRoot = Resolve-Path (Join-Path $PSScriptRoot '..')

python (Join-Path $RepoRoot 'scripts\mobile_readiness.py')
exit $LASTEXITCODE
