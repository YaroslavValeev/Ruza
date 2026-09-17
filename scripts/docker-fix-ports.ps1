# Освобождает порт 5173 и перезапускает dashboard-контейнер Ruza.
$ErrorActionPreference = 'Stop'
$repoRoot = Resolve-Path (Join-Path $PSScriptRoot '..')
Set-Location $repoRoot

$port = 5173

Write-Output "=== Port $port listeners ==="
$listeners = Get-NetTCPConnection -LocalPort $port -State Listen -ErrorAction SilentlyContinue
if ($listeners) {
    foreach ($conn in $listeners) {
        $proc = Get-Process -Id $conn.OwningProcess -ErrorAction SilentlyContinue
        $name = if ($proc) { $proc.ProcessName } else { 'unknown' }
        Write-Output "PID $($conn.OwningProcess) ($name) on $($conn.LocalAddress)"
    }
    Write-Output ''
    Write-Output 'Если это не Ruza dashboard — остановите процесс вручную, например:'
    Write-Output "  Stop-Process -Id <PID> -Force"
    Write-Output 'Или закройте другой `npm run dev` / старый Docker-проект на :5173.'
} else {
    Write-Output "Port $port свободен."
}

Write-Output ''
Write-Output '=== Ruza dashboard container ==='
docker compose -f docker-compose.yml -f docker-compose.dev.yml rm -sf dashboard 2>$null | Out-Null
docker compose -f docker-compose.yml -f docker-compose.dev.yml up -d dashboard

Start-Sleep -Seconds 3
$status = docker compose -f docker-compose.yml -f docker-compose.dev.yml ps dashboard --format '{{.Status}}' 2>$null
Write-Output "dashboard status: $status"

try {
    Invoke-WebRequest -Uri "http://127.0.0.1:$port/" -TimeoutSec 5 -UseBasicParsing | Out-Null
    Write-Output "OK: http://127.0.0.1:$port/ отвечает"
} catch {
    Write-Output "FAIL: dashboard не отвечает на :$port — см. .\scripts\docker-logs.ps1 -Dev"
    exit 1
}
