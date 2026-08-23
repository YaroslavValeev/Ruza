$ErrorActionPreference = 'Stop'

$repoRoot = Resolve-Path (Join-Path $PSScriptRoot '..')
$icebeach = Join-Path $repoRoot 'icebeach-wakeclub'
$dashboardDir = Join-Path $icebeach 'apps\dashboard'

$env:PYTHONPATH = $icebeach

$python = $null
foreach ($name in @('python', 'python3', 'py')) {
  $cmd = Get-Command $name -ErrorAction SilentlyContinue
  if ($cmd) {
    $python = $cmd.Source
    break
  }
}
if (-not $python) {
  throw 'Python not found. Install Python 3.11+ and retry.'
}

& $python -m pytest (Join-Path $icebeach 'apps\api\tests') -v
if ($LASTEXITCODE -ne 0) {
  exit $LASTEXITCODE
}

Set-Location $dashboardDir
if (-not (Test-Path 'node_modules')) {
  npm ci
}
npx tsc --noEmit
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
npm run build
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }

Write-Output ''
Write-Output 'OK: tests + dashboard build'
