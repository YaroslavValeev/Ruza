param(
  [int]$Tail = 20,
  [int]$ApiPort = 8000
)
$ErrorActionPreference = 'Stop'

$repoRoot = Resolve-Path (Join-Path $PSScriptRoot '..\icebeach-wakeclub')
$apiDir = Join-Path $repoRoot 'apps\api'
$dashboardDir = Join-Path $repoRoot 'apps\dashboard'
$apiOut = Join-Path $apiDir ".runlogs\api-$ApiPort.out.log"
$apiErr = Join-Path $apiDir ".runlogs\api-$ApiPort.err.log"
$apiSupervisorLog = Join-Path $apiDir '.runlogs\api-supervisor.log'
$apiSupervisorPidFile = Join-Path $apiDir '.runlogs\api-supervisor.pid'
$dashOut = Join-Path $dashboardDir '.runlogs\dashboard.out.log'
$dashErr = Join-Path $dashboardDir '.runlogs\dashboard.err.log'

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

function Get-PortListeners([int]$Port) {
  $lines = netstat -ano -p TCP | Select-String ":$Port"
  $items = @()
  foreach ($line in $lines) {
    $text = ($line.ToString() -replace '\s+', ' ').Trim()
    $parts = $text.Split(' ')
    if ($parts.Length -lt 5) { continue }
    if ($parts[3] -ne 'LISTENING') { continue }
    $procId = $parts[4]
    $processName = ''
    if ($procId -match '^\d+$') {
      try {
        $processName = (Get-Process -Id ([int]$procId) -ErrorAction Stop).ProcessName
      } catch {
        $processName = 'unknown'
      }
    }
    $items += [pscustomobject]@{
      LocalAddress = $parts[1]
      PID = $procId
      Process = $processName
    }
  }
  return $items
}

function Show-PortBlock([string]$Label, [int]$Port) {
  Write-Output "=== $Label ($Port) ==="
  $listeners = Get-PortListeners -Port $Port
  if (-not $listeners -or $listeners.Count -eq 0) {
    Write-Output 'DOWN'
    return
  }
  foreach ($listener in $listeners) {
    Write-Output ("UP  {0}  PID={1}  PROC={2}" -f $listener.LocalAddress, $listener.PID, $listener.Process)
  }
}

function Show-PidFileBlock([string]$Label, [string]$PathToPidFile) {
  Write-Output "=== $Label ==="
  if (-not (Test-Path $PathToPidFile)) {
    Write-Output 'DOWN'
    return
  }
  $pidText = (Get-Content -Path $PathToPidFile -ErrorAction SilentlyContinue | Select-Object -First 1).ToString().Trim()
  if ($pidText -notmatch '^\d+$') {
    Write-Output "STALE pid_file=$PathToPidFile"
    return
  }
  try {
    $proc = Get-Process -Id ([int]$pidText) -ErrorAction Stop
    Write-Output ("UP  PID={0}  PROC={1}" -f $proc.Id, $proc.ProcessName)
  } catch {
    Write-Output ("STALE PID={0}" -f $pidText)
  }
}

function Show-Health([string]$Url) {
  Write-Output "=== HEALTH ==="
  try {
    $body = Invoke-WebRequest -UseBasicParsing $Url | Select-Object -ExpandProperty Content
    Write-Output $body
  } catch {
    Write-Output $_.Exception.Message
  }
}

function Show-LogTail([string]$Label, [string]$PathToLog, [int]$TailLines) {
  Write-Output "=== $Label (tail $TailLines) ==="
  if (Test-Path $PathToLog) {
    Get-Content $PathToLog -Tail $TailLines
  } else {
    Write-Output 'log not found'
  }
}

$lanIp = Get-LanIPv4
if ($lanIp) {
  Write-Output "=== LAN ==="
  Write-Output "IP: $lanIp"
  Write-Output "API: http://$lanIp`:$ApiPort"
  Write-Output "Dashboard: http://$lanIp`:5173"
  Write-Output ''
}

Show-PidFileBlock -Label 'API Watchdog' -PathToPidFile $apiSupervisorPidFile
Show-PortBlock -Label 'API' -Port $ApiPort
Show-Health -Url "http://127.0.0.1:$ApiPort/health"
Write-Output ''
Show-PortBlock -Label 'Dashboard' -Port 5173
Write-Output ''
Show-LogTail -Label 'API Supervisor' -PathToLog $apiSupervisorLog -TailLines $Tail
Write-Output ''
Show-LogTail -Label 'API OUT' -PathToLog $apiOut -TailLines $Tail
Write-Output ''
Show-LogTail -Label 'API ERR' -PathToLog $apiErr -TailLines $Tail
Write-Output ''
Show-LogTail -Label 'Dashboard OUT' -PathToLog $dashOut -TailLines $Tail
Write-Output ''
Show-LogTail -Label 'Dashboard ERR' -PathToLog $dashErr -TailLines $Tail
