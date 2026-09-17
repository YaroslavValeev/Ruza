# Создаёт недостающие вкладки Google Sheets (checkins, kpi_targets).
$ErrorActionPreference = 'Stop'
$repoRoot = Resolve-Path (Join-Path $PSScriptRoot '..')
Set-Location $repoRoot

if (-not (Test-Path 'service-account.json')) {
    Write-Error "Нужен service-account.json в корне репозитория."
}

Write-Output '=== Sheets bootstrap (via Docker API container) ==='
docker compose -f docker-compose.yml -f docker-compose.dev.yml exec -T api `
    sh -c "cd /app && PYTHONPATH=/app python -m packages.sheets.bootstrap_tabs"

Write-Output ''
Write-Output 'Проверка: .\scripts\smoke-local.ps1'
