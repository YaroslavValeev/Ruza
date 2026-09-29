# Показывает URL для установки PWA на телефонах в локальной сети.
$ErrorActionPreference = "Stop"
$repoRoot = Split-Path -Parent $PSScriptRoot
Set-Location $repoRoot

function Get-LanIPv4Candidates {
    $skipAdapter = 'vEthernet|WSL|Docker|Loopback|Hyper-V|Default Switch|Teredo|isatap|Npcap|VirtualBox|VMware|wintun|tun2socks'
    $preferAdapter = 'Ethernet|Wi-Fi|WiFi|WLAN|Wireless|Беспровод|Ethernet|LAN|Realtek'

    $candidates = @()
    $upIndexes = @(Get-NetAdapter | Where-Object { $_.Status -eq 'Up' } | Select-Object -ExpandProperty InterfaceIndex)

    foreach ($addr in Get-NetIPAddress -AddressFamily IPv4) {
        if ($addr.IPAddress -like '127.*') { continue }
        if ($addr.IPAddress -like '169.254.*') { continue }
        if ($addr.IPAddress -like '172.*') { continue }
        if ($addr.IPAddress -like '10.255.*') { continue }
        if ($addr.PrefixOrigin -eq 'WellKnown') { continue }
        if ($upIndexes -notcontains $addr.InterfaceIndex) { continue }

        $adapter = Get-NetAdapter -InterfaceIndex $addr.InterfaceIndex -ErrorAction SilentlyContinue
        $name = if ($adapter) { $adapter.Name } else { '' }
        if ($name -match $skipAdapter) { continue }

        $score = 0
        if ($name -match 'Ethernet') { $score += 12 }
        if ($name -match $preferAdapter) { $score += 8 }
        if ($addr.IPAddress -like '192.168.*') { $score += 5 }

        $candidates += [pscustomobject]@{
            IP = $addr.IPAddress
            Adapter = $name
            Score = $score
            Metric = $addr.InterfaceMetric
        }
    }

    return ($candidates | Sort-Object @{ Expression = 'Score'; Descending = $true }, Metric | Group-Object IP | ForEach-Object { $_.Group[0] })
}

function Test-DashboardUp([string]$BaseUrl) {
    try {
        $r = Invoke-WebRequest -Uri "$BaseUrl/" -UseBasicParsing -TimeoutSec 4
        return $r.StatusCode -ge 200
    } catch {
        return $false
    }
}

$candidates = @(Get-LanIPv4Candidates)
if ($candidates.Count -eq 0) {
    Write-Host "LAN IPv4 не найден. Подключите Ethernet или Wi‑Fi к роутеру." -ForegroundColor Yellow
    exit 1
}

$primary = $candidates[0]
$base = "http://$($primary.IP):5173"

Write-Host ""
Write-Host "Ice Beach — ссылки для телефонов (та же Wi‑Fi / домашняя сеть)" -ForegroundColor Cyan
Write-Host "ПК сейчас: $($primary.Adapter) → $($primary.IP)" -ForegroundColor DarkGray
Write-Host ""
Write-Host "Owner:     $base/login?next=/m/owner"
Write-Host "Пилот:     $base/login?next=/m/pilot"
Write-Host "Установка: $base/m/install"
Write-Host ""

if ($candidates.Count -gt 1) {
    Write-Host "Другие IP (если основной не откроется на телефоне):" -ForegroundColor DarkGray
    foreach ($alt in $candidates | Select-Object -Skip 1) {
        Write-Host "  http://$($alt.IP):5173/  ($($alt.Adapter))" -ForegroundColor DarkGray
    }
    Write-Host ""
}

if (-not (Test-DashboardUp $base)) {
    Write-Host "ВНИМАНИЕ: Dashboard на $base не отвечает с ПК." -ForegroundColor Yellow
    Write-Host "  .\scripts\docker-status.ps1 -Dev" -ForegroundColor DarkGray
} else {
    $apiOk = $false
    try {
        Invoke-RestMethod "$base/api/health" -TimeoutSec 4 | Out-Null
        $apiOk = $true
    } catch {}
    if ($apiOk) {
        Write-Host "OK: dashboard + /api/health отвечают с ПК." -ForegroundColor Green
    } else {
        Write-Host "Dashboard открывается, но /api/health не ответил — перезапустите Docker." -ForegroundColor Yellow
    }
}

Write-Host ""
Write-Host "Если телефон пишет «не удаётся установить соединение»:" -ForegroundColor Yellow
Write-Host "  1) Телефон в той же Wi‑Fi, не гостевая сеть, VPN выключен" -ForegroundColor Yellow
Write-Host "  2) Попробуйте другой IP из списка выше" -ForegroundColor Yellow
Write-Host "  3) Роутер: отключите «изоляцию клиентов / AP isolation»" -ForegroundColor Yellow
Write-Host "  4) Админ PowerShell: .\scripts\open-lan-firewall.ps1" -ForegroundColor Yellow
Write-Host ""
Write-Host "ПК (localhost): http://127.0.0.1:5173" -ForegroundColor DarkGray
