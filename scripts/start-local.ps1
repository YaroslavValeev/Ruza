param(
  [switch]$Lan
)
$ErrorActionPreference = 'Stop'

$repoRoot = Resolve-Path (Join-Path $PSScriptRoot '..\icebeach-wakeclub')
$apiDir = Join-Path $repoRoot 'apps\api'
$dashboardDir = Join-Path $repoRoot 'apps\dashboard'
$apiLogs = Join-Path $apiDir '.runlogs'
$dashboardLogs = Join-Path $dashboardDir '.runlogs'
$apiWatchdogScript = Join-Path $PSScriptRoot 'api-watchdog.ps1'
$apiOut = Join-Path $apiLogs 'api-8000.out.log'
$apiErr = Join-Path $apiLogs 'api-8000.err.log'
$apiSupervisorLog = Join-Path $apiLogs 'api-supervisor.log'
$apiSupervisorPidFile = Join-Path $apiLogs 'api-supervisor.pid'
$dashOut = Join-Path $dashboardLogs 'dashboard.out.log'
$dashErr = Join-Path $dashboardLogs 'dashboard.err.log'
$bindHost = if ($Lan) { '0.0.0.0' } else { '127.0.0.1' }
$displayHost = '127.0.0.1'
$dashboardHostArg = if ($Lan) { '0.0.0.0' } else { '127.0.0.1' }

function Get-LanIPv4() {
  $preferred = Get-NetIPConfiguration -ErrorAction SilentlyContinue |
    Where-Object {
      $_.IPv4Address -and $_.IPv4DefaultGateway -and $_.NetAdapter.Status -eq 'Up' -and
      $_.IPv4Address.IPAddress -match '^(192\.168\.|10\.|172\.(1[6-9]|2\d|3[0-1])\.)' -and
      $_.InterfaceAlias -notmatch 'vEthernet|WSL|Default Switch|wintun|Hyper-V'
    } |
    Select-Object @{Name='IPAddress';Expression={$_.IPv4Address.IPAddress}}, InterfaceAlias
  if ($preferred) {
    return ($preferred | Select-Object -First 1 -ExpandProperty IPAddress)
  }

  $fallback = Get-NetIPAddress -AddressFamily IPv4 -ErrorAction SilentlyContinue |
    Where-Object {
      $_.IPAddress -match '^(192\.168\.|10\.|172\.(1[6-9]|2\d|3[0-1])\.)' -and
      $_.IPAddress -ne '127.0.0.1' -and
      $_.IPAddress -notmatch '^169\.254\.'
    } |
    Sort-Object -Property InterfaceMetric
  return ($fallback | Select-Object -First 1 -ExpandProperty IPAddress)
}

function Stop-ProcessByPidFile([string]$PathToPidFile, [string]$Label) {
  if (-not (Test-Path $PathToPidFile)) { return }
  $pidRaw = Get-Content -Path $PathToPidFile -ErrorAction SilentlyContinue | Select-Object -First 1
  $pidText = if ($null -eq $pidRaw) { '' } else { $pidRaw.ToString().Trim() }
  if ($pidText -match '^\d+$') {
    try {
      Stop-Process -Id ([int]$pidText) -Force -ErrorAction Stop
      Write-Output "Stopped $Label PID $pidText"
    } catch {}
  }
  Remove-Item -Path $PathToPidFile -Force -ErrorAction SilentlyContinue
}

function Stop-PortIfBusy([int]$Port) {
  $procIds = netstat -ano -p TCP | Select-String ":$Port" |
    ForEach-Object {
      $parts = (($_.ToString() -replace '\s+', ' ').Trim()).Split(' ')
      if ($parts.Length -ge 5 -and $parts[3] -eq 'LISTENING' -and $parts[4] -match '^\d+$') { $parts[4] }
    } |
    Sort-Object -Unique

  foreach ($procId in $procIds) {
    try {
      Stop-Process -Id ([int]$procId) -Force -ErrorAction Stop
      Write-Output "Stopped PID $procId on port $Port"
    } catch {}
  }
}

New-Item -ItemType Directory -Force -Path $apiLogs | Out-Null
New-Item -ItemType Directory -Force -Path $dashboardLogs | Out-Null

Stop-ProcessByPidFile -PathToPidFile $apiSupervisorPidFile -Label 'API watchdog'
Stop-PortIfBusy 8000
Stop-PortIfBusy 5173
Start-Sleep -Seconds 1

Set-Content -Path $apiOut -Value '' -Encoding UTF8
Set-Content -Path $apiErr -Value '' -Encoding UTF8
Set-Content -Path $apiSupervisorLog -Value '' -Encoding UTF8
Set-Content -Path $dashOut -Value '' -Encoding UTF8
Set-Content -Path $dashErr -Value '' -Encoding UTF8

$watchdogCommand = "& '$apiWatchdogScript' -ApiDir '$apiDir' -OutLog '$apiOut' -ErrLog '$apiErr' -SupervisorLog '$apiSupervisorLog' -PidFile '$apiSupervisorPidFile' -Port 8000 -BindHost '$bindHost'"
$apiWatchdogProc = Start-Process -FilePath 'C:\Program Files\PowerShell\7\pwsh.exe' -ArgumentList '-NoProfile', '-ExecutionPolicy', 'Bypass', '-Command', $watchdogCommand -PassThru -WindowStyle Hidden

$healthOk = $false
for ($attempt = 1; $attempt -le 20; $attempt += 1) {
  Start-Sleep -Seconds 1
  try {
    $body = Invoke-WebRequest -UseBasicParsing "http://$displayHost`:8000/health" | Select-Object -ExpandProperty Content
    if ($body) {
      $healthOk = $true
      break
    }
  } catch {}
}

if (-not $healthOk) {
  Write-Error "API failed to become healthy. Check $apiErr and $apiSupervisorLog"
}

$dashProc = Start-Process -FilePath 'C:\Program Files\PowerShell\7\pwsh.exe' -ArgumentList '-Command', "Set-Location '$dashboardDir'; npm run dev -- --host $dashboardHostArg --port 5173" -PassThru -WindowStyle Hidden -RedirectStandardOutput $dashOut -RedirectStandardError $dashErr
Start-Sleep -Seconds 6
if ($dashProc.HasExited) {
  Write-Error "Dashboard failed to start. Check $dashErr"
}

Write-Output "API Watchdog PID: $($apiWatchdogProc.Id)"
Write-Output "API: http://127.0.0.1:8000"
Write-Output "Dashboard: http://127.0.0.1:5173"
if ($Lan) {
  $lanIp = Get-LanIPv4
  if ($lanIp) {
    Write-Output "LAN API: http://$lanIp`:8000"
    Write-Output "LAN Dashboard: http://$lanIp`:5173"
  } else {
    Write-Output 'LAN IP not detected automatically.'
  }
}
Write-Output "API log: $apiOut"
Write-Output "API supervisor log: $apiSupervisorLog"
Write-Output "Dashboard log: $dashOut"