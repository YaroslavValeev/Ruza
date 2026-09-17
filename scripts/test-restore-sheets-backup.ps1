param()

$ErrorActionPreference = 'Stop'
$RepoRoot = Resolve-Path (Join-Path $PSScriptRoot '..')

python (Join-Path $RepoRoot 'scripts\test_restore_sheets_backup.py')
exit $LASTEXITCODE
