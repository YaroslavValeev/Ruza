param(
  [switch]$Lan
)
$ErrorActionPreference = 'Stop'

$repoRoot = Resolve-Path (Join-Path $PSScriptRoot '..')
$icebeach = Join-Path $repoRoot 'icebeach-wakeclub'
$apiDir = Join-Path $icebeach 'apps\api'
$dashboardDir = Join-Path $icebeach 'apps\dashboard'
$apiLogs = Join-Path $apiDir '.runlogs'
$dashboardLogs = Join-Path $dashboardDir '.runlogs'
$apiOut = Join-Path $apiLogs 'api-8000.out.log'
$apiErr = Join-Path $apiLogs 'api-8000.err.log'
$apiPidFile = Join-Path $apiLogs 'api-supervisor.pid'
$dashOut = Join-Path $dashboardLogs 'dashboard.out.log'
$dashErr = Join-Path $dashboardLogs 'dashboard.err.log'
$bindHost = if ($Lan) { '0.0.0.0' } else { '127.0.0.1' }
$dashboardHostArg = if ($Lan) { '0.0.0.0' } else { '127.0.0.1' }

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

New-Item -ItemType Directory -Force -Path $apiLogs | Out-Null
New-Item -ItemType Directory -Force -Path $dashboardLogs | Out-Null
Stop-PortIfBusy 8000
Stop-PortIfBusy 5173
Start-Sleep -Seconds 1

if (-not (Test-Path (Join-Path $dashboardDir 'node_modules'))) {
  Push-Location $dashboardDir
  npm ci
  Pop-Location
}

$env:PYTHONPATH = "$icebeach"
Set-Content -Path $apiOut -Value '' -Encoding utf8
Set-Content -Path $apiErr -Value '' -Encoding utf8

$demoScript = Join-Path $repoRoot 'scripts\demo_local.py'
$quotedScript = '"' + $demoScript + '"'
$apiProc = Start-Process -FilePath $python -ArgumentList @('-u', $quotedScript) -WorkingDirectory "$repoRoot" -PassThru -WindowStyle Hidden -RedirectStandardOutput $apiOut -RedirectStandardError $apiErr
Set-Content -Path $apiPidFile -Value $apiProc.Id -Encoding ascii

$healthOk = $false
for ($attempt = 1; $attempt -le 25; $attempt += 1) {
  Start-Sleep -Seconds 1
  if ($apiProc.HasExited) {
    break
  }
  try {
    $body = Invoke-WebRequest -UseBasicParsing 'http://127.0.0.1:8000/health' | Select-Object -ExpandProperty Content
    if ($body -match 'ok') {
      $healthOk = $true
      break
    }
  } catch {}
}

if (-not $healthOk) {
  $errTail = ''
  if (Test-Path $apiErr) { $errTail = (Get-Content -Path $apiErr -ErrorAction SilentlyContinue | Select-Object -Last 30) -join "`n" }
  $outTail = ''
  if (Test-Path $apiOut) { $outTail = (Get-Content -Path $apiOut -ErrorAction SilentlyContinue | Select-Object -Last 30) -join "`n" }
  Write-Error "Demo API failed. Python=$python Script=$demoScript Exited=$($apiProc.HasExited)`nERR:`n$errTail`nOUT:`n$outTail"
}

$pwshExe = if (Test-Path 'C:\Program Files\PowerShell\7\pwsh.exe') {
  'C:\Program Files\PowerShell\7\pwsh.exe'
} else {
  'powershell.exe'
}
$dashCommand = "Set-Location -LiteralPath '$dashboardDir'; npm run dev -- --host $dashboardHostArg --port 5173"
$dashProc = Start-Process -FilePath $pwshExe -ArgumentList @('-NoProfile', '-ExecutionPolicy', 'Bypass', '-Command', $dashCommand) -PassThru -WindowStyle Hidden -RedirectStandardOutput $dashOut -RedirectStandardError $dashErr
Start-Sleep -Seconds 5
if ($dashProc.HasExited) {
  Write-Error "Dashboard failed to start. Check $dashErr"
}

Write-Output 'Demo without Google Sheets'
Write-Output 'Dashboard: http://127.0.0.1:5173'
Write-Output 'API:       http://127.0.0.1:8000/health'
Write-Output 'Login: Admin / Operator / Pilot buttons, then request code'
Write-Output 'Stop: .\scripts\stop-local.ps1'
Write-Output "API PID: $($apiProc.Id)"
Write-Output "Dashboard PID: $($dashProc.Id)"
if ($Lan) {
  Write-Output "Dashboard bind: $bindHost"
}
