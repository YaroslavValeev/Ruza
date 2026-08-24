param(
  [switch]$Dev,
  [switch]$Smoke,
  [switch]$ForceEnv
)
$ErrorActionPreference = 'Stop'

$repoRoot = Resolve-Path (Join-Path $PSScriptRoot '..')
Set-Location $repoRoot

if ($ForceEnv) {
  & (Join-Path $PSScriptRoot 'docker-sync-env.ps1') -Force
} else {
  & (Join-Path $PSScriptRoot 'docker-sync-env.ps1')
}

if (-not (Test-Path 'service-account.json')) {
  Write-Error "Place service-account.json in repo root: $repoRoot\service-account.json"
}

$composeArgs = @('compose', '--env-file', '.env.docker')
if ($Dev) {
  $composeArgs += @('-f', 'docker-compose.yml', '-f', 'docker-compose.dev.yml')
  Write-Output 'Mode: DEV (hot reload API + Vite dashboard)'
} else {
  $composeArgs += @('-f', 'docker-compose.yml')
  Write-Output 'Mode: PROD-like (nginx dashboard, rebuild on frontend changes)'
}

$composeArgs += @('up', '--build', '-d')
& docker @composeArgs

Write-Output 'Waiting for API health...'
$healthOk = $false
for ($i = 1; $i -le 30; $i++) {
  Start-Sleep -Seconds 2
  try {
    $body = Invoke-RestMethod -Uri 'http://127.0.0.1:8000/health' -TimeoutSec 5
    if ($body.status -eq 'ok') {
      $healthOk = $true
      break
    }
  } catch {}
}

if (-not $healthOk) {
  Write-Error 'API not healthy. Run: .\scripts\docker-logs.ps1'
}

$dashOk = $false
for ($i = 1; $i -le 15; $i++) {
  try {
    Invoke-WebRequest -Uri 'http://127.0.0.1:5173/' -TimeoutSec 4 -UseBasicParsing | Out-Null
    $dashOk = $true
    break
  } catch {
    Start-Sleep -Seconds 2
  }
}

if (-not $dashOk) {
  Write-Host ''
  Write-Host 'WARNING: Dashboard :5173 не отвечает (часто порт занят другим процессом).' -ForegroundColor Yellow
  Write-Host 'Fix: .\scripts\docker-fix-ports.ps1' -ForegroundColor Yellow
  $listeners = Get-NetTCPConnection -LocalPort 5173 -State Listen -ErrorAction SilentlyContinue
  if ($listeners) {
    foreach ($conn in $listeners) {
      $proc = Get-Process -Id $conn.OwningProcess -ErrorAction SilentlyContinue
      Write-Host "  Port 5173: PID $($conn.OwningProcess) ($($proc.ProcessName))" -ForegroundColor DarkYellow
    }
  }
}

Write-Output ''
Write-Output '=== Docker stack UP ==='
Write-Output 'API:       http://127.0.0.1:8000/health'
Write-Output 'Dashboard: http://127.0.0.1:5173'
Write-Output ''
Write-Output 'Commands:'
Write-Output '  .\scripts\docker-status.ps1'
Write-Output '  .\scripts\docker-logs.ps1'
Write-Output '  .\scripts\docker-down.ps1'
if ($Dev) {
  Write-Output '  .\scripts\docker-up.ps1 -Dev   # after code changes API reloads auto; dashboard HMR'
} else {
  Write-Output '  .\scripts\docker-rebuild.ps1     # after frontend changes'
}

if ($Smoke) {
  Write-Output ''
  & (Join-Path $PSScriptRoot 'smoke-local.ps1')
}
