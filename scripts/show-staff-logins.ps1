# Показать staff_user_id и телефоны для входа (из Google Sheets).
$ErrorActionPreference = 'Stop'
$repoRoot = Resolve-Path (Join-Path $PSScriptRoot '..')
Set-Location $repoRoot

docker compose -f docker-compose.yml -f docker-compose.dev.yml exec -T api `
    sh -c "cd /app && PYTHONPATH=/app python -m packages.sheets.list_staff"
