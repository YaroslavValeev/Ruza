$ErrorActionPreference = 'Stop'

$repoRoot = Resolve-Path (Join-Path $PSScriptRoot '..\icebeach-wakeclub')
$apiDir = Join-Path $repoRoot 'apps\api'
$apiSupervisorPidFile = Join-Path $apiDir '.runlogs\api-supervisor.pid'

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

Stop-ProcessByPidFile -PathToPidFile $apiSupervisorPidFile -Label 'API watchdog'
Start-Sleep -Seconds 1
Stop-PortIfBusy 8000
Stop-PortIfBusy 5173
