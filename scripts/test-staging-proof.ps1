param()

$ErrorActionPreference = 'Stop'
$RepoRoot = Resolve-Path (Join-Path $PSScriptRoot '..')

python (Join-Path $RepoRoot 'scripts\test_staging_proof.py')
exit $LASTEXITCODE
