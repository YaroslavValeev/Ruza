# Проверка доступа к API/dashboard с LAN IP (как с телефона).
$ErrorActionPreference = 'Stop'
$repoRoot = Split-Path -Parent $PSScriptRoot
Set-Location $repoRoot

function Get-LanIPv4 {
    $skipAdapter = 'vEthernet|WSL|Docker|Loopback|Hyper-V|Default Switch|Teredo|isatap|Npcap|VirtualBox|VMware'
    $preferAdapter = 'Wi-Fi|WiFi|WLAN|Wireless|Ethernet|Беспровод|Ethernet|LAN'
    $candidates = @()
    foreach ($addr in Get-NetIPAddress -AddressFamily IPv4) {
        if ($addr.IPAddress -like '127.*' -or $addr.IPAddress -like '169.254.*') { continue }
        $adapter = Get-NetAdapter -InterfaceIndex $addr.InterfaceIndex -ErrorAction SilentlyContinue
        $name = if ($adapter) { $adapter.Name } else { '' }
        if ($name -match $skipAdapter) { continue }
        $score = 0
        if ($name -match $preferAdapter) { $score += 10 }
        if ($addr.IPAddress -like '192.168.*') { $score += 5 }
        $candidates += [pscustomobject]@{ IP = $addr.IPAddress; Score = $score; Metric = $addr.InterfaceMetric }
    }
    $best = $candidates | Sort-Object @{ Expression = 'Score'; Descending = $true }, Metric | Select-Object -First 1
    return $best.IP
}

$ip = Get-LanIPv4
if (-not $ip) {
    Write-Host 'LAN IP не найден.' -ForegroundColor Red
    exit 1
}

Write-Host "=== LAN preflight ($ip) ===" -ForegroundColor Cyan
$ok = $true

foreach ($pair in @(
        @{ Label = 'API :8000/health'; Url = "http://${ip}:8000/health" },
        @{ Label = 'Dashboard :5173'; Url = "http://${ip}:5173/" }
    )) {
    try {
        $resp = Invoke-WebRequest -Uri $pair.Url -UseBasicParsing -TimeoutSec 6
        Write-Host "[OK] $($pair.Label) → $($resp.StatusCode)" -ForegroundColor Green
    } catch {
        Write-Host "[FAIL] $($pair.Label) → $($_.Exception.Message)" -ForegroundColor Red
        $ok = $false
    }
}

Write-Host ''
if (-not $ok) {
    Write-Host 'С телефона будет «API недоступно». Чаще всего — брандмауэр Windows.' -ForegroundColor Yellow
    Write-Host 'Запустите PowerShell **от администратора**:' -ForegroundColor Yellow
    Write-Host '  .\scripts\open-lan-firewall.ps1' -ForegroundColor White
    exit 1
}

Write-Host 'С ПК по LAN всё доступно. На телефоне откройте (та же Wi‑Fi, не мобильный интернет):' -ForegroundColor Green
Write-Host "  http://${ip}:5173/login?next=/m/owner"
exit 0
